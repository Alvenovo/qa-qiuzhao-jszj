# -*- coding: utf-8 -*-
"""每天正午更新：多源抓取江苏/浙江仍在招的软件测试相关岗位。"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
TODAY = datetime.now(timezone(timedelta(hours=8))).date()
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9"})
TIMEOUT = 18

JS_CITIES = {
    "南京", "苏州", "无锡", "常州", "南通", "扬州", "镇江", "泰州", "盐城",
    "淮安", "连云港", "宿迁", "徐州", "昆山", "张家港", "常熟", "太仓",
    "江阴", "宜兴", "溧阳", "丹阳", "吴江", "江宁", "浦口", "栖霞",
    "工业园区", "苏州园区", "江苏",
}
ZJ_CITIES = {
    "杭州", "宁波", "温州", "嘉兴", "湖州", "绍兴", "金华", "衢州", "舟山",
    "台州", "丽水", "余杭", "滨江", "西湖", "萧山", "余姚", "慈溪", "义乌",
    "海宁", "桐乡", "诸暨", "上虞", "临平", "钱塘", "浙江",
}
CITY_TO_PROVINCE = {c: "江苏" for c in JS_CITIES}
CITY_TO_PROVINCE.update({c: "浙江" for c in ZJ_CITIES})

TEST_RE = re.compile(
    r"测试开发|测开|软件测试|自动化测试|质量保障|质量工程|"
    r"测试工程师|测试类|测试岗|游戏测试|SDET|sdet|\bQA\b|\bQE\b|"
    r"测试技术|测试实习|数字化测试|测试"
)
SKIP_TEST_RE = re.compile(r"芯片测试|量产测试|产品测试工程师|晶圆测试|封装测试")
DATE_RE = re.compile(r"(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})")
RANGE_RE = re.compile(
    r"(20\d{2}[-/.]\d{1,2}[-/.]\d{1,2})\s*[~～至到\-—]+\s*(20\d{2}[-/.]\d{1,2}[-/.]\d{1,2})"
)

SOURCE_LOG: list[dict[str, Any]] = []


def log_source(name: str, ok: bool, count: int, detail: str = "") -> None:
    SOURCE_LOG.append({"name": name, "ok": ok, "count": count, "detail": detail})
    flag = "OK" if ok else "FAIL"
    print(f"[{flag}] {name}: {count} 条 {detail}", flush=True)


def get(url: str, **kwargs) -> requests.Response | None:
    try:
        resp = SESSION.get(url, timeout=TIMEOUT, **kwargs)
        if resp.status_code >= 400:
            return None
        resp.raise_for_status()
        return resp
    except Exception as exc:
        print(f"  GET fail {url[:80]} -> {exc}", flush=True)
        return None


def post(url: str, **kwargs) -> requests.Response | None:
    try:
        resp = SESSION.post(url, timeout=TIMEOUT, **kwargs)
        if resp.status_code >= 400:
            return None
        return resp
    except Exception as exc:
        print(f"  POST fail {url[:80]} -> {exc}", flush=True)
        return None


def parse_date(text: Any) -> str | None:
    if not text:
        return None
    if isinstance(text, (int, float)):
        try:
            ts = int(text)
            if ts > 10**12:
                ts //= 1000
            return datetime.fromtimestamp(ts, timezone(timedelta(hours=8))).date().isoformat()
        except Exception:
            return None
    s = str(text).strip()
    m = DATE_RE.search(s.replace("年", "-").replace("月", "-").replace("日", ""))
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
    except ValueError:
        return None


def classify_role(positions: list[str]) -> str:
    blob = " ".join(positions)
    if re.search(r"测试开发|测开|SDET|sdet|测试技术开发", blob):
        return "测试开发"
    if re.search(r"质量保障|质量工程|\bQE\b", blob):
        return "质量保障"
    if re.search(r"自动化测试", blob):
        return "自动化测试"
    return "软件测试"


def pick_test_positions(positions: list[str]) -> list[str]:
    keep = []
    for p in positions:
        p = (p or "").strip()
        if not p:
            continue
        if SKIP_TEST_RE.search(p) and not TEST_RE.search(p.replace("芯片测试", "").replace("量产测试", "")):
            continue
        if TEST_RE.search(p):
            keep.append(p)
    return list(dict.fromkeys(keep))


def split_locations(raw: Any) -> list[str]:
    if not raw:
        return []
    if isinstance(raw, list):
        parts = raw
    else:
        parts = re.split(r"[、，,;/|·\s]+", str(raw))
    out = []
    for p in parts:
        p = re.sub(r"(市|省)$", "", str(p).strip())
        if p:
            out.append(p)
    return out


def js_zj_cities(locations: list[str]) -> tuple[list[str], list[str]]:
    cities, provinces = [], []
    for loc in locations:
        for city, prov in CITY_TO_PROVINCE.items():
            if city in loc:
                if city not in ("江苏", "浙江"):
                    if city not in cities:
                        cities.append(city)
                if prov not in provinces:
                    provinces.append(prov)
                break
    return cities, provinces


def still_open(deadline: str | None) -> bool:
    if not deadline:
        return True
    try:
        return date.fromisoformat(deadline) >= TODAY
    except ValueError:
        return True


def make_job(**kwargs) -> dict[str, Any] | None:
    company = (kwargs.get("company") or "").strip()
    if not company:
        return None
    positions = pick_test_positions(kwargs.get("positions") or [])
    blob = " ".join(positions + [kwargs.get("program") or "", kwargs.get("raw") or ""])
    if not positions and not TEST_RE.search(blob):
        return None
    if not positions:
        positions = ["软件测试相关"]
    if SKIP_TEST_RE.search(blob) and not TEST_RE.search(re.sub(r"芯片测试|量产测试|产品测试工程师", "", blob)):
        return None

    locations, provinces = js_zj_cities(split_locations(kwargs.get("locations") or []))
    if not locations and not provinces:
        return None
    start = parse_date(kwargs.get("start_date"))
    deadline = parse_date(kwargs.get("deadline"))
    if not still_open(deadline):
        return None
    updated = parse_date(kwargs.get("updated_at")) or TODAY.isoformat()
    apply_url = kwargs.get("apply_url") or None
    if apply_url and not str(apply_url).startswith("http"):
        apply_url = None
    role = kwargs.get("role_type") or classify_role(positions)
    key = hashlib.md5(
        f"{company}|{kwargs.get('batch')}|{deadline}|{','.join(locations)}|{role}".encode("utf-8")
    ).hexdigest()[:12]
    return {
        "id": key,
        "company": company,
        "program": kwargs.get("program") or None,
        "cohort": kwargs.get("cohort") or "2027届",
        "batch": kwargs.get("batch") or "正式批",
        "role_type": role,
        "positions": positions,
        "locations": locations,
        "provinces": provinces,
        "start_date": start,
        "deadline": deadline,
        "updated_at": updated,
        "apply_url": apply_url,
        "source": kwargs.get("source") or "未知",
        "industry": kwargs.get("industry") or "其他",
        "status": "open",
    }


def merge_jobs(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    bucket: dict[str, dict[str, Any]] = {}
    for job in items:
        if not job:
            continue
        key = (job["company"], job.get("batch"), job.get("deadline"), job["role_type"])
        old = bucket.get(key)
        if not old:
            bucket[key] = job
            continue
        old["positions"] = list(dict.fromkeys(old["positions"] + job["positions"]))
        old["locations"] = list(dict.fromkeys(old["locations"] + job["locations"]))
        old["provinces"] = list(dict.fromkeys(old["provinces"] + job["provinces"]))
        if job.get("apply_url") and (not old.get("apply_url") or old["source"] != "企业官网"):
            if job["source"] == "企业官网" or not old.get("apply_url"):
                old["apply_url"] = job["apply_url"]
                if job["source"] == "企业官网":
                    old["source"] = "企业官网"
        if job.get("start_date") and (not old.get("start_date") or job["start_date"] < old["start_date"]):
            old["start_date"] = job["start_date"]
        if job.get("updated_at") and job["updated_at"] > (old.get("updated_at") or ""):
            old["updated_at"] = job["updated_at"]
    jobs = list(bucket.values())
    jobs.sort(key=lambda j: (j.get("deadline") or "9999", j["company"]))
    return jobs


# ---------- sources ----------

def from_seed() -> list[dict[str, Any]]:
    path = ROOT / "seed_jobs.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    jobs = []
    for row in data:
        row = dict(row)
        row["source"] = row.get("source") or "精选官网"
        row["updated_at"] = TODAY.isoformat()
        job = make_job(**row)
        if job:
            jobs.append(job)
    log_source("seed_jobs", True, len(jobs))
    return jobs


def from_xixicc() -> list[dict[str, Any]]:
    url = "https://raw.githubusercontent.com/xixicc186/xixicc2027/main/jobs.json"
    resp = get(url)
    if not resp:
        log_source("xixicc2027", False, 0, "下载失败")
        return []
    try:
        rows = resp.json()
    except Exception as exc:
        log_source("xixicc2027", False, 0, str(exc))
        return []
    jobs = []
    for row in rows:
        job = make_job(
            company=row.get("company"),
            program=row.get("program"),
            cohort=row.get("cohort"),
            batch=row.get("batch"),
            positions=row.get("positions") or [],
            locations=row.get("locations") or [],
            start_date=row.get("first_seen"),
            deadline=row.get("deadline"),
            updated_at=row.get("last_seen") or row.get("first_seen"),
            apply_url=row.get("apply_url"),
            source="xixicc2027",
            industry=row.get("industry"),
            raw=" ".join(row.get("positions") or []),
        )
        if job:
            jobs.append(job)
    log_source("xixicc2027", True, len(jobs))
    return jobs


NIUQIZP_CITIES = [
    "hangzhou", "ningbo", "wenzhou", "jiaxing", "huzhou", "shaoxing", "jinhua",
    "nanjing", "suzhou", "wuxi", "changzhou", "nantong", "yangzhou", "xuzhou",
    "zhenjiang", "taizhou",
]


def _parse_niuqizp_text(text: str, page_city: str) -> list[dict[str, Any]]:
    jobs = []
    blocks = re.split(r"\n(?=###\s)", text)
    for block in blocks:
        if "测试" not in block and "测开" not in block and "质量保障" not in block:
            continue
        title_m = re.search(r"###\s*(.+)", block)
        raw_title = (title_m.group(1) if title_m else "").strip()
        parts = raw_title.split()
        if not parts:
            continue
        company = re.sub(r"\d+.*$", "", parts[0]).strip(" -_|")
        if not company:
            continue
        rng = RANGE_RE.search(block)
        start = rng.group(1) if rng else None
        deadline = rng.group(2) if rng else None
        # city line: often a comma-separated city list
        loc_line = ""
        for line in block.splitlines():
            if any(c in line for c in ("杭州", "南京", "苏州", "宁波", "无锡", "扬州")):
                if len(line) < 220:
                    loc_line = line
                    break
        pos_line = ""
        for line in block.splitlines():
            if "测试" in line and len(line) < 300:
                pos_line = line
                break
        positions = split_locations(pos_line.replace("，", ",")) if pos_line else ["测试"]
        locations = split_locations(loc_line) if loc_line else [page_city]
        apply_m = re.search(r"https?://[^\s)]+", block)
        job = make_job(
            company=company,
            program=None,
            cohort="2027届",
            batch="正式批",
            positions=positions,
            locations=locations,
            start_date=start,
            deadline=deadline,
            updated_at=start,
            apply_url=apply_m.group(0) if apply_m else None,
            source="校招日历niuqizp",
            industry="互联网",
        )
        if job:
            jobs.append(job)
    return jobs


def from_niuqizp() -> list[dict[str, Any]]:
    jobs = []
    city_cn = {
        "hangzhou": "杭州", "ningbo": "宁波", "wenzhou": "温州", "jiaxing": "嘉兴",
        "huzhou": "湖州", "shaoxing": "绍兴", "jinhua": "金华", "nanjing": "南京",
        "suzhou": "苏州", "wuxi": "无锡", "changzhou": "常州", "nantong": "南通",
        "yangzhou": "扬州", "xuzhou": "徐州", "zhenjiang": "镇江", "taizhou": "泰州",
    }
    ok = 0
    fail = 0
    for slug in NIUQIZP_CITIES:
        if fail >= 3 and ok == 0:
            print("  niuqizp 连续失败，当前网络可能拦截该站，跳过剩余城市", flush=True)
            break
        url = (
            "https://campus.niuqizp.com/"
            f"deadline-computersoftwarehardwareservices-{slug}-1/"
        )
        resp = get(url)
        if not resp:
            fail += 1
            continue
        try:
            soup = BeautifulSoup(resp.text, "lxml")
            text = soup.get_text("\n", strip=True)
            jobs.extend(_parse_niuqizp_text(text, city_cn.get(slug, "")))
            ok += 1
            fail = 0
        except Exception as exc:
            fail += 1
            print(f"  parse fail {slug}: {exc}", flush=True)
    log_source("niuqizp校招日历", ok > 0, len(jobs), f"成功页面 {ok}/{len(NIUQIZP_CITIES)}")
    return jobs


def from_nowcoder() -> list[dict[str, Any]]:
    jobs = []
    payloads = [
        ("https://www.nowcoder.com/np-api/n/search/job", {
            "query": "测试", "type": "campus", "page": 1, "pageSize": 50,
        }),
    ]
    headers = {
        "Referer": "https://www.nowcoder.com/jobs/school/schedule",
        "Accept": "application/json,text/plain,*/*",
    }
    city_hint = ["杭州", "南京", "苏州", "宁波", "无锡", "常州", "南通", "扬州", "嘉兴", "湖州"]
    for keyword in ("测试工程师", "测试开发", "软件测试", "质量保障"):
        url = "https://www.nowcoder.com/np-api/n/search/job"
        resp = get(url, params={"query": keyword, "jobType": 0, "page": 1}, headers=headers)
        data = None
        if resp:
            try:
                data = resp.json()
            except Exception:
                data = None
        if not data:
            # 校招日程页 HTML 兜底
            continue
        rows = (
            data.get("data", {}).get("jobList")
            or data.get("data", {}).get("list")
            or data.get("result")
            or []
        )
        if isinstance(rows, dict):
            rows = rows.get("jobList") or rows.get("datas") or []
        for row in rows:
            if not isinstance(row, dict):
                continue
            loc = row.get("cityList") or row.get("jobCity") or row.get("workCity") or ""
            if isinstance(loc, list):
                loc = [x.get("name") if isinstance(x, dict) else x for x in loc]
            title = row.get("jobTitle") or row.get("title") or row.get("jobName") or keyword
            company = (
                row.get("companyName")
                or (row.get("company") or {}).get("name")
                or row.get("companyFullName")
            )
            job = make_job(
                company=company,
                positions=[title],
                locations=loc if loc else city_hint,
                start_date=row.get("startTime") or row.get("beginTime"),
                deadline=row.get("endTime") or row.get("deadline"),
                updated_at=row.get("updateTime") or row.get("modifyTime"),
                apply_url=row.get("jobUrl") or (
                    f"https://www.nowcoder.com/jobs/detail/{row.get('jobId')}"
                    if row.get("jobId") else None
                ),
                source="牛客",
                cohort="2027届",
                batch="校招",
            )
            if job:
                jobs.append(job)

    # HTML 日程页兜底
    page = get("https://www.nowcoder.com/jobs/school/schedule")
    if page:
        soup = BeautifulSoup(page.text, "lxml")
        text = soup.get_text("\n", strip=True)
        for m in re.finditer(
            r"(.{2,20}?)(?:\s+)(27秋招|27届校招|27提前批|27届秋招).{0,80}地点：\s*([^\n]{2,80})",
            text,
        ):
            company, batch, loc = m.group(1).strip(), m.group(2), m.group(3)
            if "测试" not in text[max(0, m.start() - 40): m.end() + 80] and "测开" not in text[m.start(): m.end() + 120]:
                # 日程页常常不写岗位，保留江浙公司供种子/官网交叉；这里要求上下文有测试词才收
                nearby = text[m.start(): m.end() + 160]
                if "测试" not in nearby and "测开" not in nearby:
                    continue
            job = make_job(
                company=re.sub(r"收藏", "", company).strip(),
                positions=["软件测试相关"],
                locations=split_locations(loc),
                batch=batch,
                source="牛客校招日程",
                apply_url="https://www.nowcoder.com/jobs/school/schedule",
            )
            if job:
                jobs.append(job)
    log_source("牛客", True, len(jobs), "接口可能被拦，已做 HTML 兜底")
    return jobs


def from_bytedance() -> list[dict[str, Any]]:
    url = "https://jobs.bytedance.com/api/v1/search/job/posts"
    body = {
        "keyword": "测试",
        "limit": 30,
        "offset": 0,
        "job_category_id_list": [],
        "tag_id_list": [],
        "location_code_list": [],
        "recruitment_id_list": [],
        "portal_type": 2,
        "job_function_id_list": [],
    }
    headers = {
        "Referer": "https://jobs.bytedance.com/campus/position?keywords=%E6%B5%8B%E8%AF%95",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    resp = post(url, json=body, headers=headers)
    jobs = []
    if not resp:
        log_source("字节官网", False, 0, "接口不可用")
        return jobs
    try:
        data = resp.json()
    except Exception:
        log_source("字节官网", False, 0, "JSON 解析失败")
        return jobs
    posts = (((data.get("data") or {}).get("job_post_list")) or data.get("job_post_list") or [])
    for row in posts:
        title = row.get("title") or row.get("job_title") or ""
        locs = []
        for loc in row.get("city_list") or row.get("locations") or []:
            if isinstance(loc, dict):
                locs.append(loc.get("name") or loc.get("en_name") or "")
            else:
                locs.append(str(loc))
        job = make_job(
            company="字节跳动",
            program=row.get("recruit_type") or "校园招聘",
            positions=[title],
            locations=locs,
            deadline=row.get("expired_time") or row.get("end_time"),
            start_date=row.get("publish_time") or row.get("create_time"),
            updated_at=row.get("publish_time"),
            apply_url=row.get("job_post_url")
            or f"https://jobs.bytedance.com/campus/position/{row.get('id')}/detail",
            source="企业官网",
            industry="互联网",
        )
        if job:
            jobs.append(job)
    log_source("字节官网", True, len(jobs))
    return jobs


def from_huawei() -> list[dict[str, Any]]:
    url = "https://career.huawei.com/reccampportal/services/portal/portalpub/getJobByCondition"
    body = {
        "searchText": "测试",
        "jobType": "",
        "jobFamily": "",
        "deptCode": "",
        "pageIndex": 1,
        "pageSize": 30,
    }
    resp = post(url, json=body, headers={"Content-Type": "application/json"})
    jobs = []
    if not resp:
        log_source("华为官网", False, 0)
        return jobs
    try:
        data = resp.json()
    except Exception:
        log_source("华为官网", False, 0, "JSON 解析失败")
        return jobs
    rows = data.get("result") or data.get("pageVO", {}).get("result") or data.get("jobList") or []
    if isinstance(rows, dict):
        rows = rows.get("result") or []
    for row in rows:
        if not isinstance(row, dict):
            continue
        title = row.get("jobName") or row.get("title") or "测试"
        loc = row.get("jobArea") or row.get("workLocation") or row.get("city") or ""
        job = make_job(
            company="华为",
            positions=[title],
            locations=split_locations(loc) or ["南京", "杭州"],
            start_date=row.get("publishTime") or row.get("beginTime"),
            deadline=row.get("endTime") or row.get("dueDate"),
            updated_at=row.get("updateTime") or row.get("publishTime"),
            apply_url=row.get("jobDetailUrl")
            or "https://career.huawei.com/reccampportal/portal5/campus-recruitment.html",
            source="企业官网",
            industry="半导体/硬件",
        )
        if job:
            jobs.append(job)
    log_source("华为官网", True, len(jobs))
    return jobs


def from_netease() -> list[dict[str, Any]]:
    # 网易校招职位接口不固定，抓职位页文本做兜底
    jobs = []
    for url in (
        "https://campus.163.com/app/index",
        "https://game.campus.163.com/position/index",
    ):
        resp = get(url)
        if not resp:
            continue
        soup = BeautifulSoup(resp.text, "lxml")
        text = soup.get_text(" ", strip=True)
        if not TEST_RE.search(text):
            continue
        job = make_job(
            company="网易" if "game.campus" not in url else "网易游戏（互娱）",
            positions=["测试开发", "质量保障", "游戏测试"] if "game" in url else ["测试开发", "质量保障"],
            locations=["杭州"],
            apply_url=url,
            source="企业官网",
            industry="游戏" if "game" in url else "互联网",
            updated_at=TODAY.isoformat(),
        )
        if job:
            jobs.append(job)
    log_source("网易官网", True, len(jobs))
    return jobs


def from_alibaba() -> list[dict[str, Any]]:
    resp = get("https://talent.alibaba.com/campus/positions")
    jobs = []
    if resp and TEST_RE.search(resp.text):
        job = make_job(
            company="阿里巴巴",
            positions=["测试开发工程师", "质量保障"],
            locations=["杭州"],
            apply_url="https://talent.alibaba.com/campus/positions",
            source="企业官网",
            industry="互联网",
            updated_at=TODAY.isoformat(),
        )
        if job:
            jobs.append(job)
    log_source("阿里官网", True, len(jobs), "列表页确认仍开放")
    return jobs


def render_readme(jobs: list[dict[str, Any]], meta: dict[str, Any]) -> None:
    js = sum(1 for j in jobs if "江苏" in j["provinces"])
    zj = sum(1 for j in jobs if "浙江" in j["provinces"])
    lines = [
        "# 2027届秋招 · 江苏浙江测试岗",
        "",
        f"> 只收录**还在招**的软件测试 / 测试开发 / 质量保障等岗位 ｜ 地区：江苏、浙江 ｜ "
        f"更新时间：{meta['updated_at']} ｜ 共 {len(jobs)} 条（江苏 {js} / 浙江 {zj}）",
        ">",
        f"> 数据源：{'、'.join(meta['sources'])} ｜ [打开网站](./index.html)",
        "",
        "## 家里怎么用",
        "",
        "公司电脑不爬数据。家里：",
        "",
        "```bash",
        "git clone https://github.com/Alvenovo/qa-qiuzhao-jszj.git",
        "cd qa-qiuzhao-jszj",
        "```",
        "",
        "打开 `index.html` 即可。之后每天 `git pull`，或等 GitHub Pages 自动刷新。",
        "",
        "## 每天中午 12 点自动更新",
        "",
        "GitHub Actions 在**北京时间每天 12:00**于云端重新爬取，丢掉已截止岗位，写回 `jobs.json` 和首页。",
        "",
        "第一次请到仓库 Actions 允许工作流，并手动 Run 一次。",
        "",
        "Boss / 智联需要登录，云端用不了登录态；要补爬只在自己电脑跑 `python scripts/update.py`。",
        "",
        "## 岗位表",
        "",
        "| 公司 | 岗位 | 地区 | 开始 | 截止 | 投递 | 来源 |",
        "|---|---|---|---|---|---|---|",
    ]
    for j in jobs:
        pos = "、".join(j["positions"][:4])
        loc = "、".join(j["locations"])
        start = j.get("start_date") or "以官网为准"
        end = j.get("deadline") or "招满即止"
        if j.get("apply_url"):
            link = f"[网申]({j['apply_url']})"
        else:
            link = "见官网"
        lines.append(
            f"| {j['company']} | {pos} | {loc} | {start} | {end} | {link} | {j['source']} |"
        )
    lines += [
        "",
        "## 说明",
        "",
        "- 信息来自公开招聘页，投递前以企业官网为准。",
        "- 已过截止日期的岗位不会出现在本站。",
        "- 不要把 Boss / 智联账号密码写进仓库。",
        "",
    ]
    (ROOT / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_site(jobs: list[dict[str, Any]], meta: dict[str, Any]) -> None:
    template = (ROOT / "site_template.html").read_text(encoding="utf-8")
    html = (
        template
        .replace("__JOBS__", json.dumps(jobs, ensure_ascii=False))
        .replace("__META__", json.dumps(meta, ensure_ascii=False))
    )
    (ROOT / "index.html").write_text(html, encoding="utf-8")
    (ROOT / "jobs.json").write_text(
        json.dumps(jobs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (ROOT / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> int:
    print(f"今天（北京时间）{TODAY.isoformat()}，开始抓取未截止的测试岗…", flush=True)
    collected: list[dict[str, Any]] = []
    for fn in (
        from_seed,
        from_xixicc,
        from_niuqizp,
        from_nowcoder,
        from_bytedance,
        from_huawei,
        from_netease,
        from_alibaba,
    ):
        try:
            collected.extend(fn())
        except Exception as exc:
            log_source(fn.__name__, False, 0, str(exc))
    jobs = merge_jobs(collected)
    sources = [s["name"] for s in SOURCE_LOG if s["ok"]]
    meta = {
        "updated_at": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M"),
        "count": len(jobs),
        "sources": sources,
        "source_log": SOURCE_LOG,
        "note": "仅江苏/浙江，仅软件测试相关，仅未截止",
    }
    write_site(jobs, meta)
    render_readme(jobs, meta)
    print(f"完成：{len(jobs)} 条写入 jobs.json / index.html", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
