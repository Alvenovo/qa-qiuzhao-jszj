# -*- coding: utf-8 -*-
"""每天正午更新：多源抓取江苏/浙江/安徽/上海仍在招的软件测试相关岗位。"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import time
import os
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from normalize import (
    normalize_job_name, job_category, normalize_for_dedup, normalize_url,
    norm_company, source_type, source_rank, jd_source_rank,
    classify_status, compute_quality, same_job, similar_position,
    infer_batch, extract_jd_core, classify_job_domain,
    jd_year_matches_cohort, jd_is_software_testing,
)

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
AH_CITIES = {
    "合肥", "芜湖", "蚌埠", "淮南", "马鞍山", "淮北", "铜陵", "安庆", "黄山",
    "滁州", "阜阳", "宿州", "六安", "亳州", "池州", "宣城", "安徽",
}
SH_CITIES = {
    "上海", "浦东", "徐汇", "闵行", "松江", "嘉定", "杨浦", "静安", "黄浦",
    "虹口", "宝山", "青浦", "奉贤", "金山", "崇明",
}
CITY_TO_PROVINCE = {c: "江苏" for c in JS_CITIES}
CITY_TO_PROVINCE.update({c: "浙江" for c in ZJ_CITIES})
CITY_TO_PROVINCE.update({c: "安徽" for c in AH_CITIES})
CITY_TO_PROVINCE.update({c: "上海" for c in SH_CITIES})

COMPANY_HQ = {
    "杰华特": ["杭州"], "同花顺": ["杭州"], "海康威视": ["杭州"], "大华股份": ["杭州"],
    "大华": ["杭州"], "新华三": ["杭州"], "中控技术": ["杭州"], "群核科技": ["杭州"],
    "涂鸦智能": ["杭州"], "宇树科技": ["杭州"], "当虹科技": ["杭州"], "有赞": ["杭州"],
    "满帮集团": ["南京", "苏州"], "中新赛克": ["南京"], "天锐星通": ["南京"],
    "焦点科技": ["南京"], "途牛": ["南京"], "南瑞集团": ["南京"], "思必驰": ["苏州"],
    "拼多多": ["上海"], "携程": ["上海"], "哔哩哔哩": ["上海"], "米哈游": ["上海"],
    "科大讯飞": ["合肥", "南京", "苏州", "杭州", "上海"],
    "蔚来": ["合肥"], "阳光电源": ["合肥"],
    "绿盟科技": ["南京"], "国家电网": ["南京"], "航天科工": ["南京", "上海"],
    "中国电信": ["南京", "杭州", "上海"], "长鑫存储": ["合肥"], "零跑汽车": ["杭州"],
    "帆软": ["南京"], "网易雷火": ["杭州"],
    "恒生电子": ["杭州"], "医科达": ["上海"], "思特威": ["上海"], "声网": ["上海"],
    "华勤技术": ["上海"], "微创医疗机器人": ["上海"], "术锐机器人": ["上海"],
    "国睿信维": ["南京"], "姚记集团": ["上海"],
    "南京熊猫电子": ["南京"], "龙旗集团": ["上海", "合肥", "苏州"], "快手": ["杭州"],
    "宇视科技": ["杭州"],
}

BIG_FIRMS = (
    "阿里", "蚂蚁", "字节", "华为", "腾讯", "百度", "网易", "美团", "京东",
    "小米", "荣耀", "中兴", "海康", "大华", "DeepSeek", "滴滴", "微软", "三星", "博世",
    "拼多多", "携程", "哔哩", "米哈游", "蔚来", "大疆", "联想",
    "国家电网", "中国电信", "工商银行", "农业银行", "航天科工", "Shopee", "网商银行", "中国移动",
)
MID_FIRMS = (
    "浪潮", "地平线", "招银", "海信", "讯飞", "华泰", "北方华创", "新华三", "中控",
    "南瑞", "同花顺", "宇视", "微步", "有赞", "涂鸦", "满帮", "苏宁", "金蝶", "歌尔",
    "乐鑫", "Momenta", "思必驰", "天翼", "星环", "商汤", "阳光电源", "奇瑞", "江淮",
    "绿盟", "帆软", "零跑", "长鑫", "远景", "南京银行", "招商银行", "航发", "电科",
    "恒生", "华勤", "思特威", "声网", "微创", "熊猫", "龙旗", "快手", "宇视",
)


APPLY_CHANNELS: dict[str, dict[str, str]] = {}
_channels_path = ROOT / "apply_channels.json"
if _channels_path.exists():
    raw_ch = json.loads(_channels_path.read_text(encoding="utf-8"))
    APPLY_CHANNELS = {k: v for k, v in raw_ch.items() if not str(k).startswith("_") and isinstance(v, dict)}


def default_search_hint(company: str) -> str:
    name = (company or "公司").strip()
    return (
        f"百度搜「{name} 2027校招 测试」；微信搜「{name}招聘」；"
        "国聘网 iguopin.com 搜公司名+测试；Boss/智联搜「软件测试」并筛南京/杭州/上海/苏州/合肥"
    )


def lookup_channel(company: str) -> dict[str, str]:
    name = company or ""
    for key, row in APPLY_CHANNELS.items():
        if key and key in name:
            return row
    return {}


def is_job_detail_url(url: str | None) -> bool:
    if not url or not str(url).startswith("http"):
        return False
    u = str(url).lower()
    if any(x in u for x in ("/sou/", "keyword=", "/search", "/schedule", "/campus/position?")):
        return False
    if "iguopin.com/job/detail" in u or "/jobs/detail/" in u:
        return True
    if re.search(r"/(detail|job|position|post)/[a-z0-9_-]{6,}", u):
        return True
    if re.search(r"(job[_-]?id|post[_-]?id|position[_-]?id|jid|[?&]id)=\w{6,}", u):
        return True
    return False


def official_apply(company: str, fallback: str | None) -> str | None:
    # 职位详情链接优先于公司招聘首页，否则后面抽不到原文 JD。
    if is_job_detail_url(fallback):
        return fallback
    ch = lookup_channel(company)
    url = (ch.get("url") or "").strip()
    if url.startswith("http"):
        return url
    if ch and not url:
        return None
    return fallback


def classify_scale(company: str) -> str:
    name = company or ""
    if any(k in name for k in BIG_FIRMS):
        return "大厂"
    if any(k in name for k in MID_FIRMS):
        return "中厂"
    return "小厂"

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
            print(f"  GET {resp.status_code} {url[:80]}", flush=True)
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
            print(f"  POST {resp.status_code} {url[:80]}", flush=True)
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


JD_SKILL_TERMS = [
    ("Python", ["Python", "python3", "Python3"]),
    ("pytest", ["pytest", "py.test"]),
    ("接口测试", ["接口测试", "API测试", "API 测试", "接口自动化"]),
    ("自动化测试", ["自动化测试"]),
    ("Selenium", ["Selenium"]),
    ("Playwright", ["Playwright"]),
    ("Appium", ["Appium"]),
    ("JMeter", ["JMeter", "jmeter"]),
    ("Postman", ["Postman"]),
    ("requests", ["requests"]),
    ("Allure", ["Allure"]),
    ("MySQL", ["MySQL", "mysql"]),
    ("PostgreSQL", ["PostgreSQL", "Postgres"]),
    ("SQL", ["SQL"]),
    ("Linux", ["Linux"]),
    ("Git", ["Git"]),
    ("HTTP/HTTPS", ["HTTP", "HTTPS", "http协议"]),
    ("Java", ["Java"]),
    ("Jenkins", ["Jenkins"]),
    ("CI/CD", ["CI/CD", "持续集成"]),
    ("Docker", ["Docker"]),
    ("用例设计", ["用例设计", "测试用例"]),
    ("缺陷跟踪", ["禅道", "Jira", "缺陷跟踪"]),
    ("性能测试", ["性能测试"]),
    ("unittest", ["unittest"]),
    ("JUnit", ["JUnit"]),
    ("YAML", ["YAML"]),
]
SALARY_RE = re.compile(
    r"(?:薪资|月薪|年薪|薪酬|工资)[:：是为]{0,4}\s*(面议|待议|薪资待定|[^\n。；;]{1,24})"
    r"|((?:\d{1,3}(?:\.\d+)?\s*[-~～到至]\s*\d{1,3}(?:\.\d+)?)\s*[kKwW千万元]{1,3}(?:/月|/年|·月)?"
    r"|(?:\d{4,6}\s*[-~～到至]\s*\d{4,6})\s*(?:元)?(?:/月|/年)?)"
)


def as_text(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, str):
        return v.strip()
    if isinstance(v, dict):
        return as_text(v.get("name") or v.get("zh_name") or v.get("en_name") or v.get("content") or "")
    if isinstance(v, list):
        return "\n".join(x for x in (as_text(i) for i in v) if x)
    return str(v).strip()


def soup_of(html: str) -> BeautifulSoup:
    try:
        return BeautifulSoup(html or "", "lxml")
    except Exception:
        return BeautifulSoup(html or "", "html.parser")


def html_to_text(html: str) -> str:
    soup = soup_of(html)
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    return soup.get_text("\n", strip=True)


def looks_like_salary_text(s: str) -> bool:
    s = re.sub(r"\s+", "", (s or "").strip())
    if not s or len(s) > 40:
        return False
    if re.search(r"成立|周年|年假|注册资本|员工\d|粉丝", s):
        return False
    if re.fullmatch(r"0+万?", s):
        return False
    if re.search(r"面议|待议|薪资待定", s):
        return True
    if re.search(r"\d+(?:\.\d+)?\s*[-~～到至]\s*\d+(?:\.\d+)?\s*[kKwW千万元]", s):
        return True
    if re.search(r"\d{4,6}\s*[-~～到至]\s*\d{4,6}", s):
        return True
    if re.search(r"(月薪|年薪|薪资|薪酬).{0,12}\d", s):
        return True
    if re.search(r"\d+(?:\.\d+)?[kK万]\s*[-~～到至]\s*\d+(?:\.\d+)?[kK万]", s):
        return True
    return False


def extract_salary(text: str) -> str:
    blob = text or ""
    for m in SALARY_RE.finditer(blob):
        raw = next((g for g in m.groups() if g), "").strip(" :：-|")
        if not looks_like_salary_text(raw):
            continue
        return re.sub(r"\s+", " ", raw).strip()
    return ""


def salary_from_posting(row: dict[str, Any], extra_text: str = "") -> str:
    """岗位上怎么写就怎么存，不换算、不编造。"""
    for key in ("salary", "salaryDesc", "salary_range", "salaryRange", "wage_cn", "pay"):
        raw = as_text(row.get(key))
        if looks_like_salary_text(raw):
            return re.sub(r"\s+", " ", raw).strip()
    labeled = extract_salary(extra_text or as_text(row.get("contents")))
    if labeled:
        return labeled
    if row.get("is_negotiable") in (True, 1, "1", "true", "True"):
        return "面议"
    lo, hi = row.get("min_wage") or 0, row.get("max_wage") or 0
    try:
        lo, hi = int(lo), int(hi)
    except (TypeError, ValueError):
        lo, hi = 0, 0
    unit = as_text(row.get("wage_unit_cn")) or "元/月"
    if lo <= 0 and hi <= 0:
        return "面议"
    if unit == "元/天":
        text = f"{lo}~{hi}元/天" if hi and lo != hi else f"{lo}元/天"
    elif unit in ("元/月", "") and lo >= 1000:
        a, b = lo // 1000, (hi or lo) // 1000
        text = f"{a}~{b}K" if b and a != b else f"{a}K"
    else:
        text = f"{lo}~{hi}{unit}" if hi and lo != hi else f"{lo or hi}{unit}"
    try:
        months = int(row.get("months") or 0)
    except (TypeError, ValueError):
        months = 0
    if months and months not in (0, 12):
        text += f"·{months}薪"
    return text


def extract_skills_from_blob(text: str) -> list[str]:
    t = text or ""
    out = []
    for name, aliases in JD_SKILL_TERMS:
        if any(a in t for a in aliases + [name]):
            out.append(name)
    return list(dict.fromkeys(out))


def _cut_section(text: str, heads: str) -> str:
    m = re.search(heads, text)
    if not m:
        return ""
    start = m.end()
    nxt = re.search(
        r"\n\s*(?:任职要求|任职资格|岗位要求|职位要求|任职条件|岗位职责|工作职责|"
        r"加分项|福利待遇|薪资待遇|工作地点|职位描述)\s*[:：]?",
        text[start:],
    )
    end = start + nxt.start() if nxt else min(len(text), start + 1800)
    return text[start:end].strip(" \n:：")


def split_jd_items(block: str) -> list[str]:
    items = []
    for line in re.split(r"[\n；;]", block or ""):
        line = re.sub(r"^[\s\d一二三四五六七八九十]+[\.、．\)）]\s*", "", line)
        line = line.strip(" -•·*、")
        if 6 <= len(line) <= 180:
            items.append(line)
    return items[:12]


def parse_jd_text(*parts: Any) -> dict[str, Any]:
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(as_text(p) for p in parts if as_text(p))).strip()
    if len(text) < 24:
        return {"description": "", "responsibilities": [], "requirements": [], "skills": [], "salary": ""}
    resp = split_jd_items(_cut_section(text, r"(?:岗位职责|工作职责|工作内容|职位描述)\s*[:：]?"))
    req = split_jd_items(_cut_section(text, r"(?:任职要求|任职资格|岗位要求|职位要求|任职条件)\s*[:：]?"))
    if not resp and not req:
        return {
            "description": "",
            "responsibilities": [],
            "requirements": [],
            "skills": extract_skills_from_blob(text) if re.search(r"岗位职责|任职要求", text) else [],
            "salary": extract_salary(text),
        }
    desc = "；".join(resp[:4]) if resp else text[:500]
    if len(desc) > 600:
        desc = desc[:600].rstrip() + "…"
    return {
        "description": desc,
        "responsibilities": resp,
        "requirements": req,
        "skills": extract_skills_from_blob(text),
        "salary": extract_salary(text),
    }


def merge_jd_into(job: dict[str, Any], parsed: dict[str, Any] | None) -> None:
    if not parsed:
        return
    if looks_real_jd(parsed):
        desc = as_text(parsed.get("description"))
        if desc and len(desc) > len(as_text(job.get("description"))):
            job["description"] = desc[:800]
        for key in ("responsibilities", "requirements", "skills"):
            old = [x for x in (job.get(key) or []) if x]
            new = [x for x in (parsed.get(key) or []) if x]
            job[key] = list(dict.fromkeys(old + new))[:16]
    sal = as_text(parsed.get("salary"))
    if looks_real_salary(sal) and (not job.get("salary") or job.get("salary") == "面议"):
        job["salary"] = sal


def job_has_jd(job: dict[str, Any]) -> bool:
    return bool(
        as_text(job.get("description"))
        or job.get("responsibilities")
        or job.get("requirements")
        or job.get("skills")
    )


def should_fetch_jd(url: str | None) -> bool:
    if not url or not str(url).startswith("http"):
        return False
    u = str(url).lower()
    skip = (
        "baidu.com", "google.com", "weixin.qq.com", "mp.weixin",
        "iguopin.com/job?", "zhipin.com/web/geek/job",
        "nowcoder.com/jobs/school/schedule", "zhiye.com/login",
        "zhaopin.com/sou/", "xiaoyuan.zhaopin.com", "lagou.com",
    )
    if any(s in u for s in skip) and "job/detail" not in u:
        return False
    return is_job_detail_url(url)


def _jsonld_jobs(html: str) -> list[dict[str, Any]]:
    soup = soup_of(html or "")
    out = []
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = tag.string or tag.get_text() or ""
        try:
            data = json.loads(raw)
        except Exception:
            continue
        rows = data if isinstance(data, list) else [data]
        if isinstance(data, dict) and isinstance(data.get("@graph"), list):
            rows = data["@graph"]
        for row in rows:
            if not isinstance(row, dict):
                continue
            typ = str(row.get("@type") or "")
            if "JobPosting" not in typ and "job" not in typ.lower():
                continue
            salary = ""
            base = row.get("baseSalary") or {}
            if isinstance(base, dict):
                val = base.get("value") or {}
                if isinstance(val, dict):
                    lo, hi, cur = val.get("minValue"), val.get("maxValue"), val.get("unitText") or ""
                    if lo and hi:
                        salary = f"{lo}-{hi}{cur}"
                    elif lo:
                        salary = f"{lo}{cur}"
                elif isinstance(val, (int, float, str)):
                    salary = str(val)
            out.append({
                "description": as_text(row.get("description")),
                "responsibilities": split_jd_items(as_text(row.get("responsibilities"))),
                "requirements": split_jd_items(as_text(row.get("qualifications") or row.get("experienceRequirements"))),
                "skills": extract_skills_from_blob(as_text(row.get("skills")) + as_text(row.get("description"))),
                "salary": salary or extract_salary(as_text(row.get("description"))),
            })
    return out


def _fetch_iguopin_jd_api(url: str) -> dict[str, Any] | None:
    """通过国聘详情 API 获取 JD（SPA 页面无法直接抓 HTML）。"""
    m = re.search(r"[?&]id=(\d+)", url)
    if not m:
        return None
    jid = m.group(1)
    api = f"https://gp-api.iguopin.com/api/jobs/v1/info?id={jid}"
    headers = {
        "Device": "pc", "Subsite": "iguopin", "Version": "5.2.300",
        "Origin": "https://www.iguopin.com", "Referer": "https://www.iguopin.com/",
    }
    resp = get(api, headers=headers)
    if not resp or not resp.text:
        return None
    try:
        data = resp.json()
    except Exception:
        return None
    job_data = (data.get("data") or {}) if isinstance(data, dict) else {}
    contents = as_text(job_data.get("contents"))
    if not contents:
        return None
    if "<" in contents:
        contents = html_to_text(contents)
    parsed = parse_jd_text(contents)
    # 国聘 API 返回的结构化薪资字段
    salary = ""
    lo = job_data.get("min_wage")
    hi = job_data.get("max_wage")
    if lo and hi:
        unit = as_text(job_data.get("wage_unit_cn")) or ""
        salary = f"{lo}-{hi}{unit}"
    if salary and not looks_like_salary_text(salary):
        salary = ""
    if salary:
        parsed["salary"] = salary
    if not job_has_jd(parsed) and not parsed.get("salary"):
        return None
    return parsed


def fetch_jd_from_url(url: str) -> dict[str, Any] | None:
    # 国聘详情页是 SPA，HTML 不含 JD；优先改用 API 获取
    if "iguopin.com/job/detail" in url.lower():
        api_result = _fetch_iguopin_jd_api(url)
        if api_result:
            return api_result
    resp = get(url)
    if not resp or not resp.text:
        return None
    html = resp.text
    parsed = parse_jd_text(html_to_text(html))
    for block in _jsonld_jobs(html):
        merge_jd_into(parsed, block)
    if not looks_real_jd(parsed):
        parsed["description"] = ""
        parsed["responsibilities"] = []
        parsed["requirements"] = []
        parsed["skills"] = []
    if parsed.get("salary") and not looks_like_salary_text(as_text(parsed.get("salary"))):
        parsed["salary"] = ""
    if not job_has_jd(parsed) and not parsed.get("salary"):
        return None
    return parsed


def looks_real_jd(job: dict[str, Any]) -> bool:
    blob = as_text(job.get("description")) + " " + " ".join(job.get("responsibilities") or []) + " " + " ".join(job.get("requirements") or [])
    if len(blob) < 30:
        return False
    if _is_search_page_noise(blob):
        return False
    if re.search(r"射线衍射|随钻测量|pick你的心仪岗位|多种方式", blob):
        return False
    return bool(re.search(
        r"岗位职责|任职要求|工作职责|职位描述|测试用例|接口测试|自动化测试|"
        r"质量保障|缺陷跟踪|pytest|软件测试|测试开发|测开",
        blob,
    ) or blob.count("测试") >= 2)


_NOISE_LINE_RE = re.compile(r".{2,15}招聘(信息|网)?$")


def _is_search_page_noise(text: str) -> bool:
    """检测是否为搜索页/列表页噪音（多个不相关「xxx招聘」标题拼接）。

    真实 JD 可能提到「招聘」一词，但不会由多条不相关招聘标题拼接而成。
    """
    if not text or len(text) < 30:
        return False
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    noise_lines = sum(1 for l in lines if _NOISE_LINE_RE.search(l))
    # 3 行以上「xxx招聘」模式 → 搜索页噪音
    if noise_lines >= 3:
        return True
    # 5 行以上且无 JD 结构标题 + 2 行噪音 → 噪音
    if len(lines) >= 5 and noise_lines >= 2 and not re.search(r"岗位职责|任职要求|工作职责|职位描述", text):
        return True
    return False


def looks_real_salary(s: str) -> bool:
    return looks_like_salary_text(s)


def scrub_false_jd(jobs: list[dict[str, Any]]) -> None:
    for job in jobs:
        if job.get("description") or job.get("responsibilities") or job.get("skills"):
            blob = as_text(job.get("description")) + " " + " ".join(job.get("responsibilities") or []) + " " + " ".join(job.get("requirements") or [])
            if not looks_real_jd(job) or not jd_is_software_testing(blob) or not jd_year_matches_cohort(blob, job.get("cohort")):
                job["description"] = ""
                job["responsibilities"] = []
                job["requirements"] = []
                job["skills"] = []
        if job.get("salary") and not looks_real_salary(as_text(job.get("salary"))):
            job["salary"] = ""


PORTAL_HOSTS = ("mokahr.com", "jobs.feishu.cn", "hotjob.cn", "zhiye.com")


def _is_portal_url(url: str | None) -> bool:
    """判断 URL 是否为已知 SPA 招聘门户（可能含 SSR/JSON-LD 数据）。"""
    if not url or not str(url).startswith("http"):
        return False
    u = str(url).lower()
    return any(h in u for h in PORTAL_HOSTS)


def _jd_passes_guards(job: dict[str, Any], parsed: dict[str, Any]) -> bool:
    """年份 + 方向双守卫：merge 前拦截旧年份 JD 和非软件测试 JD。"""
    blob = " ".join([
        as_text(parsed.get("description")),
        " ".join(parsed.get("responsibilities") or []),
        " ".join(parsed.get("requirements") or []),
    ]).strip()
    if not blob:
        return True
    if not jd_year_matches_cohort(blob, job.get("cohort")):
        return False
    if not jd_is_software_testing(blob):
        return False
    return True


def enrich_from_apis(jobs: list[dict[str, Any]]) -> int:
    extra: list[dict[str, Any]] = []
    for fn in (from_bytedance, from_huawei, from_nowcoder):
        try:
            extra.extend(fn())
        except Exception as exc:
            log_source(fn.__name__, False, 0, str(exc))
    n = 0
    for src in extra:
        if not looks_real_jd(src) and not looks_real_salary(as_text(src.get("salary"))):
            continue
        for job in jobs:
            same_co = src["company"] in job["company"] or job["company"] in src["company"]
            if not same_co or not _role_alike(src, job):
                continue
            if not _jd_passes_guards(job, src):
                continue
            before = looks_real_jd(job)
            merge_jd_into(job, src)
            if looks_real_jd(job) and not before:
                n += 1
            break
    log_source("官网接口补JD", True, n, f"接口返回 {len(extra)} 条")
    return n


def _role_alike(src: dict[str, Any], job: dict[str, Any]) -> bool:
    sp = " ".join(src.get("positions") or [])
    jp = " ".join(job.get("positions") or [])
    generic = ("软件测试相关", "测试相关", "测试开发")
    if jp in generic or sp in generic:
        return True
    tokens = re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z]{3,}", sp)
    return any(len(t) >= 4 and t in jp for t in tokens)


def enrich_jobs_with_jd(jobs: list[dict[str, Any]], time_budget: float = 300) -> int:
    """历史岗位 JD 二次补全：按优先级队列，带跳过逻辑、搜索反查、统计日志。"""
    filled = 0
    tried = 0
    start = time.time()
    stats_by_source: dict[str, int] = {}
    skipped_recent = 0
    # 优先级：无JD > 有详情URL > open/unknown > 新发现 > 临近截止
    def _priority(j):
        p = 0
        if not looks_real_jd(j):
            p += 100
        if is_job_detail_url(j.get("apply_url")):
            p += 50
        if j.get("status") in ("open", "unknown"):
            p += 20
        if j.get("last_seen_at") == TODAY.isoformat():
            p += 10
        dl = j.get("deadline")
        if dl:
            try:
                days = (date.fromisoformat(dl) - TODAY).days
                if 0 <= days <= 14:
                    p += 15
            except ValueError:
                pass
        return -p
    queue = sorted(jobs, key=_priority)
    no_jd_total = sum(1 for j in jobs if not looks_real_jd(j))
    print(f"[INFO] 历史岗位 JD 补全开始，待补 {no_jd_total} 条", flush=True)
    for job in queue:
        # 跳过：已有官方 JD 且 7 天内更新过
        if looks_real_jd(job):
            jds = job.get("jd_source") or "unknown"
            jdu = job.get("jd_updated_at") or ""
            if jds in ("official", "official_api", "iguopin") and jdu:
                try:
                    age = (TODAY - date.fromisoformat(jdu)).days
                    if age < 7:
                        skipped_recent += 1
                        continue
                except ValueError:
                    pass
            if looks_real_salary(as_text(job.get("salary"))):
                continue
        url = job.get("apply_url")
        if not should_fetch_jd(url):
            # 已知 SPA 门户先试抓 HTML（可能含 SSR/JSON-LD 数据）
            if _is_portal_url(url) and not looks_real_jd(job):
                if time.time() - start > time_budget:
                    break
                tried += 1
                try:
                    portal_parsed = fetch_jd_from_url(url)
                except Exception:
                    portal_parsed = None
                if portal_parsed and looks_real_jd(portal_parsed) and _jd_passes_guards(job, portal_parsed):
                    before = looks_real_jd(job)
                    merge_jd_into(job, portal_parsed)
                    if looks_real_jd(job) and not before:
                        filled += 1
                        job["jd_source"] = "official"
                        job["jd_source_url"] = url
                        job["jd_updated_at"] = TODAY.isoformat()
                        stats_by_source["portal"] = stats_by_source.get("portal", 0) + 1
                time.sleep(0.3)
                if looks_real_jd(job) and looks_real_salary(as_text(job.get("salary"))):
                    continue
            # apply_url 非详情页、或无 apply_url：有公司名+岗位名即尝试国聘反查
            _no_apply_url = not (url and str(url).startswith("http"))
            if (
                not looks_real_jd(job)
                and job.get("company")
                and job.get("positions")
                and (_no_apply_url or not is_job_detail_url(url))
            ):
                if time.time() - start > time_budget:
                    break
                search_result = _search_jd_on_iguopin(job)
                if search_result:
                    tried += 1
                    if time.time() - start > time_budget:
                        break
                    try:
                        parsed = fetch_jd_from_url(search_result)
                    except Exception as exc:
                        print(f"  JD搜索反查失败 {job['company'][:20]} -> {exc}", flush=True)
                        parsed = None
                    if parsed and looks_real_jd(parsed) and _jd_passes_guards(job, parsed):
                        before = looks_real_jd(job)
                        merge_jd_into(job, parsed)
                        if looks_real_jd(job) and not before:
                            filled += 1
                            job["jd_source"] = "iguopin"
                            job["jd_source_url"] = search_result
                            job["jd_updated_at"] = TODAY.isoformat()
                            if not job.get("jd_raw_text"):
                                job["jd_raw_text"] = as_text(parsed.get("description"))
                            stats_by_source["iguopin"] = stats_by_source.get("iguopin", 0) + 1
                    time.sleep(0.3)
            continue
        if time.time() - start > time_budget:
            break
        tried += 1
        try:
            parsed = fetch_jd_from_url(url)
        except Exception as exc:
            print(f"  JD fail {url[:70]} -> {exc}", flush=True)
            parsed = None
        if parsed:
            if not _jd_passes_guards(job, parsed):
                parsed = None
        if parsed:
            before = looks_real_jd(job)
            merge_jd_into(job, parsed)
            stype = source_type(job.get("source"))
            src_label = "official" if stype == "official" else ("iguopin" if "iguopin" in url else "official_api")
            if is_job_detail_url(url) and (stype == "official" or "iguopin" in url):
                job["jd_source"] = "official" if stype == "official" else "iguopin"
                job["jd_source_url"] = url
                job["jd_updated_at"] = TODAY.isoformat()
            elif looks_real_jd(job) and not before:
                job["jd_source"] = "official_api"
                job["jd_source_url"] = url
                job["jd_updated_at"] = TODAY.isoformat()
            if looks_real_jd(job) and not before:
                filled += 1
                if not job.get("jd_raw_text"):
                    job["jd_raw_text"] = as_text(parsed.get("description"))
                stats_by_source[src_label] = stats_by_source.get(src_label, 0) + 1
            elif looks_real_salary(as_text(job.get("salary"))) and parsed.get("salary"):
                filled += 1
        time.sleep(0.25)
    remaining = sum(1 for j in jobs if not looks_real_jd(j))
    print(f"[INFO] JD 补全：尝试 {tried}，成功 {filled}，跳过(近期) {skipped_recent}，剩余待补 {remaining}", flush=True)
    for src, n in sorted(stats_by_source.items(), key=lambda x: -x[1]):
        print(f"  {src}: {n} 条", flush=True)
    log_source("职位详情补全", True, filled, f"尝试 {tried} 个投递链接，耗时 {int(time.time()-start)}s")
    return filled


def _search_jd_on_iguopin(job: dict[str, Any]) -> str | None:
    """在国聘 API 按公司名+岗位名搜索，返回匹配的详情页 URL。"""
    company = job.get("company") or ""
    pos = (job.get("positions") or [""])[0]
    if not company or not pos:
        return None
    # 公司名去后缀
    co = re.sub(r"(集团|股份|有限公司|有限责任公司|股份有限公司)$", "", company).strip()
    # 搜索关键词：先公司+岗位，再公司名单独搜
    keywords = [f"{co} {pos}"[:20], co[:20]]
    url = "https://gp-api.iguopin.com/api/jobs/v1/list"
    headers = {
        "Content-Type": "application/json;charset=UTF-8",
        "Device": "pc", "Subsite": "iguopin", "Version": "5.2.300",
        "Origin": "https://www.iguopin.com", "Referer": "https://www.iguopin.com/",
    }
    for keyword in keywords:
        body = {"page": 1, "page_size": 10, "keyword": keyword}
        resp = post(url, json=body, headers=headers)
        if not resp:
            continue
        try:
            data = resp.json()
        except Exception:
            continue
        rows = ((data.get("data") or {}).get("list")) or []
        for row in rows:
            if not isinstance(row, dict):
                continue
            row_company = as_text(row.get("company_name"))
            row_title = as_text(row.get("job_name"))
            # 公司名匹配：包含关系
            if co not in row_company and row_company not in company:
                continue
            # 岗位名相似
            if not _job_name_match(pos, row_title):
                continue
            jid = as_text(row.get("job_id"))
            if jid:
                return f"https://www.iguopin.com/job/detail?id={jid}"
    return None


def _job_name_match(a: str, b: str) -> bool:
    """判断两个岗位名是否高度相似（不自动合并不同级别）。"""
    from normalize import normalize_for_dedup
    na = normalize_for_dedup(a)
    nb = normalize_for_dedup(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    if na in nb or nb in na:
        # 但不能是不同级别（实习生/高级/专家/负责人）
        level_kw = ["实习", "高级", "专家", "负责人", "资深", "初级", "主管", "经理"]
        a_level = any(k in a for k in level_kw)
        b_level = any(k in b for k in level_kw)
        if a_level != b_level:
            return False
        return True
    return False


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
        hq = COMPANY_HQ.get(company) or COMPANY_HQ.get(re.sub(r"(集团|股份|有限公司)$", "", company))
        if hq:
            locations, provinces = js_zj_cities(hq)
    if not locations and not provinces:
        return None
    start = parse_date(kwargs.get("start_date"))
    deadline = parse_date(kwargs.get("deadline"))
    updated = parse_date(kwargs.get("updated_at")) or TODAY.isoformat()
    apply_url = kwargs.get("apply_url") or None
    if apply_url and not str(apply_url).startswith("http"):
        apply_url = None
    apply_url = official_apply(company, apply_url)
    ch = lookup_channel(company)
    search_hint = (kwargs.get("search_hint") or ch.get("hint") or "").strip() or default_search_hint(company)
    role = kwargs.get("role_type") or classify_role(positions)
    parsed = parse_jd_text(
        kwargs.get("description"),
        kwargs.get("raw_jd"),
        kwargs.get("raw"),
        "\n".join(kwargs.get("responsibilities") or []),
        "\n".join(kwargs.get("requirements") or []),
    )
    if kwargs.get("responsibilities"):
        parsed["responsibilities"] = list(dict.fromkeys(
            [as_text(x) for x in kwargs["responsibilities"] if as_text(x)] + parsed["responsibilities"]
        ))[:16]
    if kwargs.get("requirements"):
        parsed["requirements"] = list(dict.fromkeys(
            [as_text(x) for x in kwargs["requirements"] if as_text(x)] + parsed["requirements"]
        ))[:16]
    if kwargs.get("skills"):
        parsed["skills"] = list(dict.fromkeys(
            [as_text(x) for x in kwargs["skills"] if as_text(x)] + parsed["skills"]
        ))[:16]
    salary = as_text(kwargs.get("salary")) or parsed["salary"]
    description = as_text(kwargs.get("description")) or parsed["description"]
    draft = {
        "description": description,
        "responsibilities": parsed["responsibilities"],
        "requirements": parsed["requirements"],
        "skills": parsed["skills"],
    }
    if description and not looks_real_jd(draft):
        description = ""
        parsed["responsibilities"] = []
        parsed["requirements"] = []
        parsed["skills"] = []
    if salary and not looks_real_salary(salary):
        salary = ""
    key = hashlib.md5(
        f"{company}|{kwargs.get('batch')}|{deadline}|{','.join(locations)}|{positions[0]}".encode("utf-8")
    ).hexdigest()[:12]
    norm_name = normalize_job_name(positions)
    stype = source_type(kwargs.get("source"))
    has_jd_flag = bool(description) or bool(parsed["responsibilities"]) or bool(parsed["requirements"])
    jd_src = stype if has_jd_flag and stype != "unknown" else "unknown"
    raw_text = as_text(kwargs.get("raw_jd") or kwargs.get("description") or "")
    if raw_text and not looks_real_jd({"description": raw_text}):
        raw_text = ""
    source_list = kwargs.get("sources")
    if not source_list:
        source_list = [{"type": stype, "url": apply_url, "found_at": updated}]
    return {
        "id": key,
        "company": company,
        "program": kwargs.get("program") or None,
        "cohort": kwargs.get("cohort") or "2027届",
        "batch": kwargs.get("batch") or "正式批",
        "recruitment_batch": kwargs.get("recruitment_batch") or infer_batch(
            kwargs.get("program"), kwargs.get("batch"), kwargs.get("cohort")),
        "role_type": role,
        "normalized_job_name": norm_name,
        "job_category": job_category(norm_name),
        "positions": positions,
        "locations": locations,
        "provinces": provinces,
        "start_date": start,
        "deadline": deadline,
        "deadline_source": stype if deadline else "",
        "deadline_conflict": False,
        "updated_at": updated,
        "first_seen_at": kwargs.get("first_seen_at") or updated,
        "last_seen_at": kwargs.get("last_seen_at") or updated,
        "apply_url": apply_url,
        "search_hint": search_hint,
        "source": kwargs.get("source") or "未知",
        "sources": source_list,
        "jd_source": kwargs.get("jd_source") or jd_src,
        "jd_raw_text": raw_text,
        "jd_reused_from": "",
        "jd_source_url": kwargs.get("jd_source_url") or "",
        "jd_updated_at": kwargs.get("jd_updated_at") or "",
        "job_domain": kwargs.get("job_domain") or "unknown",
        "job_domain_confidence": kwargs.get("job_domain_confidence") or 0.0,
        "excluded": kwargs.get("excluded") or False,
        "exclude_reason": kwargs.get("exclude_reason") or "",
        "industry": kwargs.get("industry") or "其他",
        "scale": kwargs.get("scale") or classify_scale(company),
        "owner": kwargs.get("owner") or "",
        "status": "unknown",
        "description": description or "",
        "responsibilities": parsed["responsibilities"],
        "requirements": parsed["requirements"],
        "skills": parsed["skills"],
        "salary": salary or "",
        "data_quality": {},
    }

IGUOPIN_CAMPUS_NATURE = "115xW5oQ"
IGUOPIN_PROV = {"310000", "320000", "330000", "340000"}


def _merge_one_into(base: dict[str, Any], src: dict[str, Any]) -> None:
    today = TODAY.isoformat()
    base.setdefault("sources", [])
    src_stype = source_type(src.get("source"))
    src_entry = {"type": src_stype, "url": src.get("apply_url"), "found_at": src.get("updated_at") or today}
    if not any(s.get("type") == src_entry["type"] and normalize_url(s.get("url")) == normalize_url(src_entry["url"])
               for s in base["sources"]):
        base["sources"].append(src_entry)
    if source_rank(src_stype) > source_rank(source_type(base.get("source"))):
        base["source"] = src.get("source")
    if is_job_detail_url(src.get("apply_url")) and not is_job_detail_url(base.get("apply_url")):
        base["apply_url"] = src.get("apply_url")
    elif not base.get("apply_url") and src.get("apply_url"):
        base["apply_url"] = src.get("apply_url")
    base["positions"] = list(dict.fromkeys((base.get("positions") or []) + (src.get("positions") or [])))
    base["locations"] = list(dict.fromkeys((base.get("locations") or []) + (src.get("locations") or [])))
    base["provinces"] = list(dict.fromkeys((base.get("provinces") or []) + (src.get("provinces") or [])))
    sh = src.get("search_hint") or ""
    if sh and (not base.get("search_hint") or len(sh) > len(base.get("search_hint") or "")):
        base["search_hint"] = sh
    if src.get("owner") and not base.get("owner"):
        base["owner"] = src["owner"]
    if src.get("start_date") and (not base.get("start_date") or src["start_date"] < base["start_date"]):
        base["start_date"] = src["start_date"]
    if src.get("updated_at") and src["updated_at"] > (base.get("updated_at") or ""):
        base["updated_at"] = src["updated_at"]
    _merge_jd_by_source(base, src)
    _merge_deadline(base, src)


def _merge_jd_by_source(base: dict[str, Any], src: dict[str, Any]) -> None:
    src_has = looks_real_jd(src) or (bool(src.get("jd_raw_text")) and looks_real_jd({"description": src["jd_raw_text"]}))
    if not src_has:
        return
    src_jd = src.get("jd_source") or source_type(src.get("source"))
    if src_jd == "unknown":
        src_jd = "other"
    base_jd = base.get("jd_source") or "unknown"
    if jd_source_rank(src_jd) > jd_source_rank(base_jd) or (src_jd == base_jd and not looks_real_jd(base)):
        base["description"] = src.get("description", "")
        base["responsibilities"] = src.get("responsibilities", [])
        base["requirements"] = src.get("requirements", [])
        base["skills"] = src.get("skills", [])
        base["salary"] = src.get("salary", "")
        base["jd_raw_text"] = src.get("jd_raw_text", "")
        base["jd_source"] = src_jd
    elif jd_source_rank(src_jd) == jd_source_rank(base_jd):
        merge_jd_into(base, {"description": src.get("description"), "responsibilities": src.get("responsibilities"),
                              "requirements": src.get("requirements"), "skills": src.get("skills"), "salary": src.get("salary")})
        if src.get("jd_raw_text") and not base.get("jd_raw_text"):
            base["jd_raw_text"] = src["jd_raw_text"]


def _merge_deadline(base: dict[str, Any], src: dict[str, Any]) -> None:
    sd = src.get("deadline")
    if not sd:
        return
    bd = base.get("deadline")
    if not bd:
        base["deadline"] = sd
        base["deadline_source"] = source_type(src.get("source"))
        return
    if sd == bd:
        return
    sr = source_rank(source_type(src.get("source")))
    br = source_rank(base.get("deadline_source") or source_type(base.get("source")))
    if sr > br:
        base["deadline"] = sd
        base["deadline_source"] = source_type(src.get("source"))
    base["deadline_conflict"] = True


def merge_jobs(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    today = TODAY.isoformat()
    for job in items:
        if not job:
            continue
        target = None
        for oj in out:
            if same_job(job, oj, is_detail_url_fn=is_job_detail_url):
                target = oj
                break
        if target is None:
            job = dict(job)
            job.setdefault("first_seen_at", today)
            job["last_seen_at"] = today
            out.append(job)
        else:
            _merge_one_into(target, job)
            target["last_seen_at"] = today
    deduped = len(items) - len(out)
    if deduped > 0:
        print(f"[INFO] 去重合并 {deduped} 条", flush=True)
    out.sort(key=lambda j: (j.get("deadline") or "9999", j["company"]))
    return out


def merge_with_archive(fresh: list[dict[str, Any]], archive: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    today = TODAY.isoformat()
    result: list[dict[str, Any]] = []
    matched_ids: set[str] = set()
    new_n = 0
    updated_n = 0
    for fj in fresh:
        matched_aid = None
        for aid, aj in archive.items():
            if same_job(fj, aj, is_detail_url_fn=is_job_detail_url):
                matched_aid = aid
                break
        if matched_aid:
            aj = archive[matched_aid]
            if matched_aid in matched_ids:
                # 多个 fresh 匹配同一个 archive 条目：合并到已存在的 result 条目
                for r in result:
                    if r.get("id") == matched_aid or same_job(r, aj, is_detail_url_fn=is_job_detail_url):
                        _merge_one_into(r, fj)
                        r["last_seen_at"] = today
                        break
            else:
                base = dict(aj)
                base["first_seen_at"] = aj.get("first_seen_at") or aj.get("updated_at") or fj.get("first_seen_at")
                base["last_seen_at"] = today
                _merge_one_into(base, fj)
                matched_ids.add(matched_aid)
                updated_n += 1
                result.append(base)
        else:
            result.append(dict(fj))
            new_n += 1
    for aid, aj in archive.items():
        if aid not in matched_ids:
            result.append(dict(aj))
    if new_n:
        print(f"[INFO] 新增岗位 {new_n} 条", flush=True)
    if updated_n:
        print(f"[INFO] 更新已有岗位 {updated_n} 条", flush=True)
    return result


def finalize_job(job: dict[str, Any]) -> None:
    job["normalized_job_name"] = normalize_job_name(job.get("positions") or [])
    job["job_category"] = job_category(job["normalized_job_name"])
    job["recruitment_batch"] = job.get("recruitment_batch") or infer_batch(
        job.get("program"), job.get("batch"), job.get("cohort"))
    if not job.get("sources"):
        st = source_type(job.get("source"))
        job["sources"] = [{"type": st, "url": job.get("apply_url"), "found_at": job.get("updated_at") or TODAY.isoformat()}]
    if not job.get("jd_source"):
        if looks_real_jd(job) or (job.get("jd_raw_text") and looks_real_jd({"description": job["jd_raw_text"]})):
            job["jd_source"] = source_type(job.get("source"))
            if job["jd_source"] == "unknown":
                job["jd_source"] = "other"
        else:
            job["jd_source"] = "unknown"
    job.setdefault("jd_raw_text", "")
    job.setdefault("deadline_source", source_type(job.get("source")) if job.get("deadline") else "")
    job.setdefault("deadline_conflict", False)
    job.setdefault("jd_reused_from", "")
    # 已有 JD 但缺 jd_source_url/jd_updated_at 的，从现有信息补
    if looks_real_jd(job) or (job.get("jd_raw_text") and looks_real_jd({"description": job["jd_raw_text"]})):
        if not job.get("jd_source_url") and job.get("apply_url"):
            job["jd_source_url"] = job["apply_url"]
        if not job.get("jd_updated_at"):
            job["jd_updated_at"] = job.get("last_seen_at") or job.get("updated_at") or TODAY.isoformat()
    else:
        job.setdefault("jd_source_url", "")
        job.setdefault("jd_updated_at", "")
    freshly = (job.get("last_seen_at") == TODAY.isoformat())
    job["status"] = classify_status(job, TODAY, freshly_seen=freshly)
    job["data_quality"] = compute_quality(job, looks_real_jd)
    # JD 核心信息提取（只在有 JD 时提取，不编造）
    if looks_real_jd(job) or job.get("jd_raw_text"):
        core = extract_jd_core(job)
        job["core_skills"] = core["core_skills"]
        job["core_responsibilities"] = core["core_responsibilities"]
        job["education"] = core["education"]
        job["major"] = core["major"]
        job["experience"] = core["experience"]
        job["graduation_year"] = core["graduation_year"]
    else:
        job.setdefault("core_skills", [])
        job.setdefault("core_responsibilities", [])
        job.setdefault("education", "")
        job.setdefault("major", [])
        job.setdefault("experience", "")
        job.setdefault("graduation_year", "")
    # 岗位专业方向分类（综合岗位名+JD+技能，不误杀无JD岗位）
    domain = classify_job_domain(job)
    job["job_domain"] = domain["job_domain"]
    job["job_domain_confidence"] = domain["job_domain_confidence"]
    job["excluded"] = domain["excluded"]
    job["exclude_reason"] = domain["exclude_reason"]


def save_raw(name: str, data: Any) -> None:
    raw_dir = ROOT / "data" / "raw" / "latest"
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / f"{name}.json"
    try:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception as exc:
        print(f"[WARN] 保存 raw 失败 {name}: {exc}", flush=True)


def load_old_raw(name: str) -> list[dict[str, Any]]:
    path = ROOT / "data" / "raw" / "latest" / f"{name}.json"
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []


def load_archive() -> dict[str, dict[str, Any]]:
    cand = ROOT / "candidate_jobs.json"
    if cand.exists():
        try:
            rows = json.loads(cand.read_text(encoding="utf-8"))
            return {j["id"]: j for j in rows if isinstance(j, dict) and j.get("id")}
        except Exception:
            pass
    jobs_p = ROOT / "jobs.json"
    if jobs_p.exists():
        try:
            rows = json.loads(jobs_p.read_text(encoding="utf-8"))
        except Exception:
            rows = []
        archive: dict[str, dict[str, Any]] = {}
        for r in rows:
            if not isinstance(r, dict) or not r.get("id"):
                continue
            r.setdefault("sources", [{"type": source_type(r.get("source")),
                                      "url": r.get("apply_url"),
                                      "found_at": r.get("updated_at") or TODAY.isoformat()}])
            r.setdefault("jd_source", source_type(r.get("source")) if looks_real_jd(r) else "unknown")
            r.setdefault("jd_raw_text", "")
            r["first_seen_at"] = r.get("first_seen_at") or r.get("updated_at") or TODAY.isoformat()
            r["last_seen_at"] = r.get("last_seen_at") or r.get("updated_at") or TODAY.isoformat()
            archive[r["id"]] = r
        print(f"[INFO] 首次运行，从 jobs.json 初始化历史档案 {len(archive)} 条", flush=True)
        return archive
    return {}


def save_normalized(jobs: list[dict[str, Any]]) -> None:
    norm_dir = ROOT / "data" / "normalized"
    norm_dir.mkdir(parents=True, exist_ok=True)
    (norm_dir / "jobs_normalized.json").write_text(
        json.dumps(jobs, ensure_ascii=False, indent=1), encoding="utf-8")


def save_candidate(jobs: list[dict[str, Any]]) -> None:
    (ROOT / "candidate_jobs.json").write_text(
        json.dumps(jobs, ensure_ascii=False, indent=1), encoding="utf-8")


def _iguopin_locations(row: dict[str, Any]) -> list[str]:
    out = []
    for d in row.get("district_list") or []:
        if not isinstance(d, dict):
            continue
        area = as_text(d.get("area_cn") or d.get("address"))
        out.extend(split_locations(area.replace("-", "、")))
    return out


def _iguopin_in_region(row: dict[str, Any]) -> bool:
    for d in row.get("district_list") or []:
        if not isinstance(d, dict):
            continue
        if str(d.get("province") or "") in IGUOPIN_PROV:
            return True
        area = as_text(d.get("area_cn"))
        cities, provs = js_zj_cities(split_locations(area.replace("-", "、")))
        if cities or provs:
            return True
    return False


def from_iguopin() -> list[dict[str, Any]]:
    url = "https://gp-api.iguopin.com/api/jobs/v1/list"
    headers = {
        "Content-Type": "application/json;charset=UTF-8",
        "Accept": "application/json, text/plain, */*",
        "Device": "pc",
        "Subsite": "iguopin",
        "Version": "5.2.300",
        "Origin": "https://www.iguopin.com",
        "Referer": "https://www.iguopin.com/",
    }
    seen: set[str] = set()
    jobs: list[dict[str, Any]] = []
    for keyword in ("软件测试", "测试开发", "测试工程师", "质量保障", "测开"):
        for page in range(1, 8):
            body = {
                "page": page,
                "page_size": 50,
                "keyword": keyword,
            }
            resp = post(url, json=body, headers=headers)
            if not resp:
                continue
            try:
                data = resp.json()
            except Exception:
                continue
            rows = ((data.get("data") or {}).get("list")) or []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                jid = as_text(row.get("job_id"))
                if not jid or jid in seen:
                    continue
                title = as_text(row.get("job_name"))
                if not TEST_RE.search(title) or re.search(r"机械测试|通讯测试|无线通信|测量方向|生产辅助|射频测试|硬件测试|汽车通讯|GNSS测试|仿真测试", title):
                    continue
                if SKIP_TEST_RE.search(title) and not re.search(r"软件测试|测试开发|测开", title):
                    continue
                if not _iguopin_in_region(row):
                    continue
                seen.add(jid)
                contents = as_text(row.get("contents"))
                if "<" in contents:
                    contents = html_to_text(contents)
                notes = as_text(row.get("notes"))
                salary = salary_from_posting(row, contents + "\n" + notes)
                job = make_job(
                    company=as_text(row.get("company_name")),
                    program=as_text(row.get("recruitment_type_cn")) or "校园招聘",
                    cohort="2027届",
                    batch="校招",
                    positions=[title],
                    locations=_iguopin_locations(row),
                    start_date=row.get("start_time"),
                    deadline=row.get("end_time"),
                    updated_at=row.get("refresh_time") or row.get("update_time"),
                    apply_url=f"https://www.iguopin.com/job/detail?id={jid}",
                    source="国聘网",
                    industry=as_text((row.get("company_info") or {}).get("nature_cn")) or "国企",
                    description=contents,
                    raw_jd=contents,
                    salary=salary,
                    search_hint=f"国聘职位详情：https://www.iguopin.com/job/detail?id={jid}",
                )
                if job:
                    jobs.append(job)
            time.sleep(0.2)
    log_source("国聘网", True, len(jobs), "职位详情含原文职责/薪资")
    return jobs


def from_existing() -> list[dict[str, Any]]:
    path = ROOT / "jobs.json"
    if not path.exists():
        return []
    rows = json.loads(path.read_text(encoding="utf-8"))
    jobs = []
    for row in rows:
        job = make_job(**{k: v for k, v in row.items() if k != "id"})
        if job:
            jobs.append(job)
    log_source("现有岗位", True, len(jobs), "保留未截止")
    return jobs  # noqa: 历史档案由 main() 通过 load_archive 处理，此函数已不在 main 调用链


def copy_jd_across_same_company(jobs: list[dict[str, Any]]) -> int:
    with_jd = [j for j in jobs if looks_real_jd(j)]
    n = 0
    for job in jobs:
        if looks_real_jd(job) and looks_real_salary(as_text(job.get("salary"))):
            continue
        for src in with_jd:
            same_co = src["company"] in job["company"] or job["company"] in src["company"]
            if not same_co or not _role_alike(src, job):
                continue
            if not _jd_passes_guards(job, src):
                continue
            before = looks_real_jd(job)
            merge_jd_into(job, src)
            if looks_real_jd(job) and not before:
                n += 1
            if looks_real_salary(as_text(src.get("salary"))) and not looks_real_salary(as_text(job.get("salary"))):
                job["salary"] = src["salary"]
            if is_job_detail_url(src.get("apply_url")) and not is_job_detail_url(job.get("apply_url")):
                job["apply_url"] = src["apply_url"]
            break
    log_source("同公司补JD", True, n)
    return n


def mark_jd_status(jobs: list[dict[str, Any]]) -> None:
    """在补全链路末端给每条岗位打 jd_status：has_jd / no_jd。"""
    for job in jobs:
        if looks_real_jd(job):
            job["jd_status"] = "has_jd"
        else:
            job["jd_status"] = "no_jd"


def from_seed() -> list[dict[str, Any]]:
    jobs = []
    for name in ("seed_jobs.json", "extra_jobs.json", "sh_ah_jobs.json", "crawled_jobs.json", "iguopin_jobs.json"):
        path = ROOT / name
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for row in data:
            row = dict(row)
            row["source"] = row.get("source") or "公开招聘信息"
            row["updated_at"] = TODAY.isoformat()
            job = make_job(**row)
            if job:
                jobs.append(job)
    log_source("本地岗位库", True, len(jobs), "含中小厂")
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
            description=row.get("description") or row.get("desc") or row.get("jd"),
            responsibilities=row.get("responsibilities") or [],
            requirements=row.get("requirements") or row.get("requirement") or [],
            skills=row.get("skills") or [],
            salary=row.get("salary") or row.get("pay") or "",
        )
        if job:
            jobs.append(job)
    log_source("xixicc2027", True, len(jobs))
    return jobs


NIUQIZP_CITIES = [
    "hangzhou", "ningbo", "wenzhou", "jiaxing", "huzhou", "shaoxing", "jinhua",
    "nanjing", "suzhou", "wuxi", "changzhou", "nantong", "yangzhou", "xuzhou",
    "zhenjiang", "taizhou", "shanghai", "hefei", "wuhu",
]


def _parse_niuqizp_text(text: str, page_city: str) -> list[dict[str, Any]]:
    jobs = []
    blocks = re.split(r"\n(?=###\s)", text)
    for block in blocks:
        if "测试" not in block and "测开" not in block and "质量保障" not in block:
            continue
        title_m = re.search(r"###\s*(.+)", block)
        raw_title = (title_m.group(1) if title_m else "").strip()
        company = re.sub(
            r"\s*(27|26|2027|2026|届|秋招|校招|提前批|实习).*$",
            "",
            raw_title,
        ).strip(" -_|")
        if not company or len(company) < 2:
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
        "shanghai": "上海", "hefei": "合肥", "wuhu": "芜湖",
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
            soup = soup_of(resp.text)
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
                description=as_text(row.get("jobDescription") or row.get("description") or row.get("jobDesc")),
                requirements=split_jd_items(as_text(row.get("jobRequire") or row.get("requirement"))),
                salary=as_text(row.get("salaryDesc") or row.get("salary") or row.get("salaryRange")),
                raw_jd=as_text(row.get("jobDescription") or "") + "\n" + as_text(row.get("jobRequire") or ""),
            )
            if job:
                jobs.append(job)

    # HTML 日程页兜底
    page = get("https://www.nowcoder.com/jobs/school/schedule")
    if page:
        soup = soup_of(page.text)
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
        rec = row.get("recruit_type")
        program = as_text(rec) if rec else "校园招聘"
        desc = as_text(row.get("description") or row.get("job_description"))
        req = as_text(row.get("requirement") or row.get("job_requirement"))
        sal_raw = row.get("salary") or row.get("salary_range")
        salary = ""
        if isinstance(sal_raw, dict):
            lo = as_text(sal_raw.get("min") or sal_raw.get("min_value"))
            hi = as_text(sal_raw.get("max") or sal_raw.get("max_value"))
            salary = f"{lo}-{hi}" if lo and hi else (lo or hi)
        else:
            salary = as_text(sal_raw) or extract_salary(desc + "\n" + req)
        job = make_job(
            company="字节跳动",
            program=program or "校园招聘",
            positions=[title],
            locations=locs,
            deadline=row.get("expired_time") or row.get("end_time"),
            start_date=row.get("publish_time") or row.get("create_time"),
            updated_at=row.get("publish_time"),
            apply_url=row.get("job_post_url")
            or f"https://jobs.bytedance.com/campus/position/{row.get('id')}/detail",
            source="企业官网",
            industry="互联网",
            description=desc,
            requirements=split_jd_items(req),
            raw_jd=desc + "\n" + req,
            salary=salary,
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
        duty = as_text(row.get("jobDuty") or row.get("duty") or row.get("jobDesc") or row.get("description"))
        req = as_text(row.get("jobRequire") or row.get("requirement") or row.get("qualify"))
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
            description=duty,
            requirements=split_jd_items(req),
            raw_jd=duty + "\n" + req,
            salary=as_text(row.get("salary") or row.get("salaryRange")),
        )
        if job:
            jobs.append(job)
    log_source("华为官网", True, len(jobs))
    return jobs


def from_netease() -> list[dict[str, Any]]:
    jobs = []
    # TODO: 网易校招职位接口不固定，未实现真实岗位发现。
    # 不要写死占位岗位冒充官网抓取数据。
    log_source("网易官网", False, 0, "未实现真实抓取（pending）")
    return jobs


def from_alibaba() -> list[dict[str, Any]]:
    jobs = []
    # TODO: 阿里校招页面为 SPA，未实现真实岗位发现。
    # 不要写死占位岗位冒充官网抓取数据。
    log_source("阿里官网", False, 0, "未实现真实抓取（pending）")
    return jobs


def render_readme(jobs: list[dict[str, Any]], meta: dict[str, Any]) -> None:
    js = sum(1 for j in jobs if "江苏" in j["provinces"])
    zj = sum(1 for j in jobs if "浙江" in j["provinces"])
    ah = sum(1 for j in jobs if "安徽" in j["provinces"])
    sh = sum(1 for j in jobs if "上海" in j["provinces"])
    lines = [
        "# 2027届秋招 · 江浙沪皖测试岗",
        "",
        f"> 只收录**还在招**的软件测试 / 测试开发 / 质量保障等岗位 ｜ 地区：江苏、浙江、安徽、上海 ｜ "
        f"更新时间：{meta['updated_at']} ｜ 共 {len(jobs)} 条（江苏 {js} / 浙江 {zj} / 安徽 {ah} / 上海 {sh}）",
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
        "> 以下为示例岗位，完整列表请[打开网站](./index.html)查看。",
        "",
        "| 公司 | 岗位 | 地区 | 截止 | 投递 | 来源 |",
        "|---|---|---|---|---|---|",
    ]
    for j in jobs[:4]:
        pos = "、".join(j["positions"][:4])
        loc = "、".join(j["locations"])
        end = j.get("deadline") or "招满即止"
        if j.get("apply_url"):
            link = f"[网申]({j['apply_url']})"
        else:
            hint = (j.get("search_hint") or "见搜法").split("；")[0]
            link = hint
        lines.append(
            f"| {j['company']} | {pos} | {loc} | {end} | {link} | {j['source']} |"
        )
    lines += [
        "",
        "## 说明",
        "",
        "- 信息来自公开招聘页，投递前以企业官网为准。",
        "- 已过截止日期的岗位不会出现在本站。",
        "- 投递栏能打开就给网址；打不开就写搜索方法，不再放 404 链接。",
        "- 不要把 Boss / 智联账号密码写进仓库。",
        "",
    ]
    (ROOT / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def ensure_jd_fields(jobs: list[dict[str, Any]]) -> None:
    for job in jobs:
        job.setdefault("description", "")
        job.setdefault("responsibilities", [])
        job.setdefault("requirements", [])
        job.setdefault("skills", [])
        job.setdefault("salary", "")
        job.setdefault("jd_raw_text", "")
        job.setdefault("jd_source", "unknown")
        job.setdefault("jd_reused_from", "")
        job.setdefault("jd_source_url", "")
        job.setdefault("jd_updated_at", "")
        job.setdefault("job_domain", "unknown")
        job.setdefault("job_domain_confidence", 0.0)
        job.setdefault("excluded", False)
        job.setdefault("exclude_reason", "")
        job.setdefault("core_skills", [])
        job.setdefault("core_responsibilities", [])
        job.setdefault("education", "")
        job.setdefault("major", [])
        job.setdefault("experience", "")
        job.setdefault("graduation_year", "")
        job.setdefault("sources", [])
        job.setdefault("normalized_job_name", "")
        job.setdefault("job_category", "")
        job.setdefault("recruitment_batch", "")
        job.setdefault("first_seen_at", "")
        job.setdefault("last_seen_at", "")
        job.setdefault("deadline_source", "")
        job.setdefault("deadline_conflict", False)
        job.setdefault("data_quality", {})
        job.setdefault("status", "unknown")
        job.setdefault("jd_status", "pending")


def write_site(jobs: list[dict[str, Any]], meta: dict[str, Any]) -> None:
    ensure_jd_fields(jobs)
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
    print(f"今天（北京时间）{TODAY.isoformat()}，开始抓取测试岗位…", flush=True)
    # 1. 加载历史档案
    archive = load_archive()
    # 2. 抓取各来源，保存 raw
    raw_sources = {
        "seed": from_seed,
        "iguopin": from_iguopin,
        "xixicc": from_xixicc,
        "niuqizp": from_niuqizp,
        "nowcoder": from_nowcoder,
        "bytedance": from_bytedance,
        "huawei": from_huawei,
        "netease": from_netease,
        "alibaba": from_alibaba,
    }
    collected: list[dict[str, Any]] = []
    for raw_name, fn in raw_sources.items():
        try:
            items = fn()
            if items:
                save_raw(raw_name, items)
            collected.extend(items)
        except Exception as exc:
            log_source(fn.__name__, False, 0, str(exc))
            # 失败时保留旧 raw 兜底
            old = load_old_raw(raw_name)
            if old:
                print(f"[WARN] {fn.__name__} 抓取失败，使用上次 raw 数据 {len(old)} 条", flush=True)
                collected.extend(old)
    print(f"[INFO] 本轮抓取 {len(collected)} 条原始岗位", flush=True)
    # 3. 标准化 + 去重（fresh 内部）
    for j in collected:
        finalize_job(j)
    fresh = merge_jobs(collected)
    # 4. 与历史档案合并
    all_jobs = merge_with_archive(fresh, archive)
    # 5. JD 多级补全（优先级：已有 > 详情页 > API > 国聘 > 同公司复用）
    scrub_false_jd(all_jobs)
    copy_jd_across_same_company(all_jobs)   # 先复用已有 JD，减少网络请求
    enrich_from_apis(all_jobs)              # 企业公开 API（字节/华为/牛客）
    enrich_jobs_with_jd(all_jobs, time_budget=300)  # 详情页 + 门户抓取 + 国聘反查
    copy_jd_across_same_company(all_jobs)   # 二次复用（新补的 JD 可能帮到同公司其他岗）
    scrub_false_jd(all_jobs)
    mark_jd_status(all_jobs)
    # 6. finalize + quality
    for j in all_jobs:
        finalize_job(j)
    save_normalized(all_jobs)
    # 7. 写 candidate_jobs（全量历史档案）
    save_candidate(all_jobs)
    # 8. jobs.json 只输出 open + unknown
    display = [j for j in all_jobs if j.get("status") in ("open", "unknown") and not j.get("excluded")]
    display.sort(key=lambda j: (j.get("deadline") or "9999", j["company"]))
    excluded_n = sum(1 for j in all_jobs if j.get("excluded"))
    domain_counts: dict[str, int] = {}
    for j in all_jobs:
        d = j.get("job_domain") or "unknown"
        domain_counts[d] = domain_counts.get(d, 0) + 1
    print(f"[INFO] 岗位方向过滤：原始 {len(all_jobs)}，软件测试 {domain_counts.get('software_testing',0)}，排除 {excluded_n}，展示 {len(display)}", flush=True)
    for d, n in sorted(domain_counts.items(), key=lambda x: -x[1]):
        if d not in ("software_testing", "unknown"):
            print(f"  {d}: {n} 条", flush=True)
    jd_n = sum(1 for j in display if looks_real_jd(j))
    sal_n = sum(1 for j in display if looks_real_salary(as_text(j.get("salary"))))
    open_n = sum(1 for j in all_jobs if j.get("status") == "open")
    unknown_n = sum(1 for j in all_jobs if j.get("status") == "unknown")
    expired_n = sum(1 for j in all_jobs if j.get("status") == "expired")
    closed_n = sum(1 for j in all_jobs if j.get("status") == "closed")
    new_n = sum(1 for j in all_jobs if j.get("first_seen_at") == TODAY.isoformat())
    excluded_display = sum(1 for j in all_jobs if j.get("excluded"))
    sources = [s["name"] for s in SOURCE_LOG if s["ok"]]
    meta = {
        "updated_at": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M"),
        "count": len(display),
        "total_candidates": len(all_jobs),
        "sources": sources,
        "source_log": SOURCE_LOG,
        "note": "江苏/浙江/安徽/上海，仅软件测试相关；jobs.json 仅 open+unknown，candidate_jobs 含全量历史",
        "jd_filled": jd_n,
        "salary_filled": sal_n,
        "jd_missing": len(display) - jd_n,
        "stats": {
            "open": open_n, "unknown": unknown_n, "expired": expired_n,
            "closed": closed_n, "new_today": new_n,
            "excluded": excluded_display,
        },
    }
    write_site(display, meta)
    render_readme(display, meta)
    print(f"[INFO] 历史档案 {len(all_jobs)} 条，展示 {len(display)} 条（open {open_n} / unknown {unknown_n} / expired {expired_n}）", flush=True)
    print(f"[INFO] 方向过滤排除 {excluded_display} 条（机械/硬件/材料等非软件测试方向）", flush=True)
    print(f"[INFO] JD 已补全 {jd_n} 条，JD 暂缺 {len(display) - jd_n} 条，薪资 {sal_n} 条", flush=True)
    print(f"[INFO] 今日新增 {new_n} 条", flush=True)
    return 0


def enrich_only() -> int:
    path = ROOT / "jobs.json"
    jobs = json.loads(path.read_text(encoding="utf-8"))
    print(f"只补全现有 {len(jobs)} 条岗位的职责/技能/薪资，不重新抓日历…", flush=True)
    scrub_false_jd(jobs)
    enrich_from_apis(jobs)
    enrich_jobs_with_jd(jobs)
    scrub_false_jd(jobs)
    mark_jd_status(jobs)
    meta = json.loads((ROOT / "meta.json").read_text(encoding="utf-8"))
    meta["updated_at"] = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M")
    meta["count"] = len(jobs)
    meta["source_log"] = SOURCE_LOG
    jd_n = sum(1 for j in jobs if job_has_jd(j))
    sal_n = sum(1 for j in jobs if as_text(j.get("salary")))
    meta["jd_filled"] = jd_n
    meta["salary_filled"] = sal_n
    write_site(jobs, meta)
    print(f"完成：{len(jobs)} 条中 {jd_n} 条有职责/技能，{sal_n} 条有薪资", flush=True)
    return 0


if __name__ == "__main__":
    if "--enrich-only" in sys.argv:
        sys.exit(enrich_only())
    sys.exit(main())
