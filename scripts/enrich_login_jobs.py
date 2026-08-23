# -*- coding: utf-8 -*-
"""用登录态浏览器补 Boss/智联岗位的原文 JD 与薪资。

用法：
  1) 用调试端口启动带登录态的 Chrome（复用现有登录）：
       chrome.exe --remote-debugging-port=9222 --user-data-dir="<你的 User Data 目录>"
     然后：
       python scripts/enrich_login_jobs.py --port 9222

  2) 或者让脚本自动开一个独立 Chrome 窗口（新 profile），扫码登录后抓取：
       python scripts/enrich_login_jobs.py --launch

常用参数：
  --port 9222        附加到已启动的调试 Chrome
  --launch           自动启动独立调试 Chrome（默认 9223）
  --limit 5          最多处理 N 个岗位（调试用）
  --company 华为     只处理指定公司（调试用）
  --only-salary      只补薪资，不碰 JD
  --source Boss      只处理某个来源（Boss/智联）
  --no-dedupe        抓完不去重（默认会按公司+岗位去重，保留最详细一条）

不写账号密码；岗位页面怎么写就存什么，沿用 update.py 的清洗规则。
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import update as u

ROOT = Path(__file__).resolve().parents[1]

# Boss 直聘城市代码
BOSS_CITY = {
    "上海": "101020100",
    "南京": "101190100",
    "苏州": "101190400",
    "无锡": "101190200",
    "杭州": "101210100",
    "宁波": "101210400",
    "合肥": "101220100",
    "芜湖": "101220300",
    "嘉兴": "101210300",
    "湖州": "101210200",
    "扬州": "101190600",
}

# 智联（社招 sou.zhaopin.com）城市代码 jl
ZHAOPIN_CITY = {
    "上海": "538",
    "南京": "635",
    "苏州": "639",
    "无锡": "636",
    "杭州": "653",
    "宁波": "654",
    "合肥": "684",
    "芜湖": "685",
    "嘉兴": "655",
    "湖州": "656",
    "扬州": "637",
}

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"


def log(msg: str) -> None:
    print(msg, flush=True)


def attach(port: int):
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    opts = Options()
    opts.add_experimental_option("debuggerAddress", f"127.0.0.1:{port}")
    return webdriver.Chrome(options=opts)


def launch(port: int, user_data_dir: Path | None):
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    data = user_data_dir or (ROOT / ".chrome-login-profile")
    data.mkdir(parents=True, exist_ok=True)
    opts = Options()
    opts.add_argument("--remote-debugging-port=%d" % port)
    opts.add_argument(f"--user-data-dir={data}")
    opts.add_argument("--no-first-run")
    opts.add_argument("--no-default-browser-check")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    log(f"正在打开独立 Chrome 窗口（调试端口 {port}，profile：{data}）…")
    drv = webdriver.Chrome(options=opts)
    log("Chrome 已启动。请在新窗口里完成 Boss / 智联登录，然后回到这里继续。")
    return drv


def query_from_apply_url(job: dict) -> str | None:
    """从 Boss/智联搜索 URL 还原关键词（query= 或 kw=）。"""
    url = job.get("apply_url") or ""
    m = re.search(r"[?&](?:query|kw)=([^&]+)", url)
    if not m:
        return None
    from urllib.parse import unquote
    return unquote(m.group(1)).strip()


def search_kw(job: dict) -> str:
    kw = query_from_apply_url(job)
    if kw:
        return kw
    pos = " ".join(job.get("positions") or []) or "软件测试"
    return f"{job['company']} {pos}".strip()


def city_code(job: dict, table: dict) -> str:
    for loc in job.get("locations") or []:
        for city, code in table.items():
            if city in loc:
                return code
    return "101020100" if table is BOSS_CITY else "538"


def wait_cards(drv, timeout: float = 12):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    try:
        WebDriverWait(drv, timeout).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "li.job-card-box, .position-card, .joblist-box__item")
            )
        )
    except Exception:
        pass
    time.sleep(1.5)


def boss_search(drv, kw: str, city: str) -> None:
    """在 Boss 搜索框输入关键词回车（前端搜索），带重试应对空壳页。"""
    from selenium.webdriver.common.by import By

    box = None
    for attempt in range(3):
        drv.get("https://www.zhipin.com/web/geek/job")
        time.sleep(6)
        try:
            box = drv.find_element(By.CSS_SELECTOR, "input[placeholder*='搜索职位']")
            break
        except Exception:
            log(f"  Boss 空壳页，重试 {attempt + 1}/3 …")
    if box is None:
        raise RuntimeError("Boss 搜索框多次加载失败")
    box.clear()
    box.send_keys(kw)
    box.send_keys("\ue007")
    time.sleep(7)


def boss_cards(drv):
    rows = drv.execute_script(
        """
        return Array.from(document.querySelectorAll('li.job-card-box')).map(c => {
          const a = c.querySelector('a[href*="job_detail"]');
          if (!a) return null;
          const title = c.querySelector('a.job-name');
          const salary = c.querySelector('span.job-salary');
          const company = c.querySelector('span.boss-name');
          return {
            href: a.href,
            title: title ? title.textContent.trim() : '',
            salary: salary ? salary.textContent.trim() : '',
            company: company ? company.textContent.trim() : ''
          };
        }).filter(Boolean);
        """
    )
    out = []
    for r in rows:
        out.append(
            {
                "href": r.get("href") or "",
                "title": r.get("title") or "",
                "salary": r.get("salary") or "",
                "company": r.get("company") or "",
            }
        )
    return out


def boss_detail(drv, url: str) -> dict:
    from selenium.webdriver.common.by import By

    drv.get(url)
    time.sleep(2.5)
    if "job_detail" not in drv.current_url:
        return {"salary": "", "jd_text": ""}
    salary = ""
    for sel in (".salary", ".job-banner .salary", ".job-sec-header .salary"):
        try:
            t = drv.find_element(By.CSS_SELECTOR, sel).text.strip()
            if t:
                salary = t
                break
        except Exception:
            continue
    blocks = []
    for sel in (".job-sec-text", ".job-detail-section .text", ".job-sec .text", "[class*='job-sec']"):
        try:
            for el in drv.find_elements(By.CSS_SELECTOR, sel):
                t = el.text.strip()
                if len(t) > 20:
                    blocks.append(t)
        except Exception:
            continue
    if not blocks:
        try:
            body = drv.find_element(By.TAG_NAME, "body").text
            blocks.append(body)
        except Exception:
            pass
    jd_text = "\n".join(blocks)
    return {"salary": salary, "jd_text": jd_text}


def zhaopin_search(drv, job: dict) -> list[dict]:
    """智联校园/社招搜索并返回卡片。

    智联校园：xiaoyuan.zhaopin.com/search，卡片 .position-card，jdno 藏在
    data-sensors-exposure-option 里，详情 URL 为 /job/{jdno}。
    智联社招：sou.zhaopin.com，卡片 .joblist-box__item，详情链接在 a.jobinfo__name。
    """
    from selenium.webdriver.common.by import By

    kw = search_kw(job)
    city = city_code(job, ZHAOPIN_CITY)
    src = job.get("source") or ""
    if "校园" in src:
        url = f"https://xiaoyuan.zhaopin.com/search/index?refcode=4404&query={kw}&city={city}"
    else:
        url = f"https://sou.zhaopin.com/?kw={kw}&jl={city}"
    drv.get(url)
    time.sleep(7)
    out = []
    if "校园" in src:
        for card in drv.find_elements(By.CSS_SELECTOR, ".position-card"):
            try:
                html = card.get_attribute("outerHTML")
                m = re.search(r'jdno&quot;:&quot;([A-Za-z0-9]+)', html)
                jdno = m.group(1) if m else ""
                title = card.find_element(By.CSS_SELECTOR, ".position-card__job-name").text.strip()
                salary = card.find_element(By.CSS_SELECTOR, ".position-card__salary").text.strip()
                try:
                    company = card.find_element(By.CSS_SELECTOR, ".position-card__company__name").text.strip()
                except Exception:
                    company = ""
            except Exception:
                continue
            if jdno:
                out.append({"href": f"https://xiaoyuan.zhaopin.com/job/{jdno}", "title": title, "salary": salary, "company": company})
    else:
        for item in drv.find_elements(By.CSS_SELECTOR, ".joblist-box__item"):
            try:
                a = item.find_element(By.CSS_SELECTOR, "a.jobinfo__name")
                href = a.get_attribute("href") or ""
                title = a.text.strip()
                try:
                    salary = item.find_element(By.CSS_SELECTOR, ".jobinfo__salary").text.strip()
                except Exception:
                    salary = ""
                try:
                    company = item.find_element(By.CSS_SELECTOR, ".companyinfo__name").text.strip()
                except Exception:
                    company = ""
            except Exception:
                continue
            if href:
                out.append({"href": href, "title": title, "salary": salary, "company": company})
    return out


def zhaopin_detail(drv, url: str, campus: bool = False) -> dict:
    from selenium.webdriver.common.by import By

    drv.get(url)
    time.sleep(5)
    salary = ""
    sels = (".job-banner__salary", ".jobs-deliver__salary", ".salary", "[class*='salary']")
    for sel in sels:
        try:
            for el in drv.find_elements(By.CSS_SELECTOR, sel):
                t = el.text.strip()
                if t and len(t) < 40:
                    salary = t
                    break
            if salary:
                break
        except Exception:
            continue
    blocks = []
    desc_sels = (".job-banner__desc-text", ".jobs-deliver__text", ".tab__content", ".describtion", "[class*='detail']")
    for sel in desc_sels:
        try:
            for el in drv.find_elements(By.CSS_SELECTOR, sel):
                t = el.text.strip()
                if len(t) > 20:
                    blocks.append(t)
        except Exception:
            continue
    if not blocks:
        try:
            body = drv.find_element(By.TAG_NAME, "body").text
            # 只取职位描述之后到工作地点之前的部分
            m = re.search(r"职位描述(.*?)(?:工作地点|公司简介|智联安全提示)", body, re.S)
            if m:
                blocks.append(m.group(1).strip())
            else:
                blocks.append(body)
        except Exception:
            pass
    jd_text = "\n".join(blocks)
    if not campus and not salary:
        try:
            body = drv.find_element(By.TAG_NAME, "body").text
            m = re.search(r"(职位描述|岗位职责)(.*?)(?:工作地点|公司简介|智联安全提示)", body, re.S)
            if m and not blocks:
                jd_text = m.group(2).strip()
        except Exception:
            pass
    return {"salary": salary, "jd_text": jd_text}


def pick_best_card(cards: list[dict], job: dict) -> dict | None:
    company = job["company"]
    positions = job.get("positions") or []
    # 严格：公司名匹配 + 岗位名含“测试”
    for c in cards:
        comp = c.get("company") or ""
        title = c.get("title") or ""
        if (company in comp or comp in company) and "测试" in title:
            return c
    # 岗位名相似（不限公司，防止公司名写全称差异）
    for c in cards:
        title = c.get("title") or ""
        for p in positions:
            p = p or ""
            if p and (p in title or title in p or (len(p) >= 4 and p[:4] in title)):
                return c
    return None


def norm_positions(ps) -> str:
    s = "".join(ps or [])
    for w in ("工程师", "开发", "相关", "岗", "类"):
        s = s.replace(w, "")
    return s


def info_score(j: dict) -> float:
    s = 0.0
    if u.looks_real_jd(j):
        s += 3
    if u.looks_real_salary(u.as_text(j.get("salary"))):
        s += 3
    if u.is_job_detail_url(j.get("apply_url")):
        s += 2
    if j.get("source") == "企业官网":
        s += 1
    if len(j.get("positions") or []) > 1:
        s += 0.5
    if j.get("deadline"):
        s += 0.5
    return s


def dedupe_jobs(jobs: list[dict]) -> int:
    """同公司+同岗位（规范化后）只留最详细一条，其余信息合并进保留条。

    返回删除条数。已过截止日期的条目前面已被剔除，这里不额外处理。
    """
    groups: dict[tuple[str, str], list[dict]] = {}
    for j in jobs:
        key = (j["company"], norm_positions(j.get("positions")))
        groups.setdefault(key, []).append(j)
    removed = 0
    kept: list[dict] = []
    for key, items in groups.items():
        if len(items) < 2:
            kept.extend(items)
            continue
        best = max(items, key=info_score)
        for other in items:
            if other is best:
                continue
            removed += 1
            merged_pos = list(best.get("positions") or []) + list(other.get("positions") or [])
            best["positions"] = list(dict.fromkeys(merged_pos))
            merged_loc = list(best.get("locations") or []) + list(other.get("locations") or [])
            best["locations"] = list(dict.fromkeys(merged_loc))
            merged_prov = list(best.get("provinces") or []) + list(other.get("provinces") or [])
            best["provinces"] = list(dict.fromkeys(merged_prov))
            if other.get("deadline") and (not best.get("deadline") or other["deadline"] > best["deadline"]):
                best["deadline"] = other["deadline"]
            if other.get("start_date") and (not best.get("start_date") or other["start_date"] < best["start_date"]):
                best["start_date"] = other["start_date"]
            if other.get("updated_at") and other["updated_at"] > (best.get("updated_at") or ""):
                best["updated_at"] = other["updated_at"]
            if other.get("search_hint") and (
                not best.get("search_hint") or len(other["search_hint"]) > len(best.get("search_hint") or "")
            ):
                best["search_hint"] = other["search_hint"]
            if u.is_job_detail_url(other.get("apply_url")) and not u.is_job_detail_url(best.get("apply_url")):
                best["apply_url"] = other["apply_url"]
            # 来源：企业官网 > Boss/智联详情 > 其他
            src_rank = {"企业官网": 3, "Boss直聘": 2, "智联招聘": 2, "智联校园": 2}
            if src_rank.get(other.get("source") or "", 0) > src_rank.get(best.get("source") or "", 0):
                best["source"] = other["source"]
        kept.append(best)
    jobs[:] = kept
    return removed


def is_logged_out(drv) -> bool:
    url = drv.current_url
    # Boss 搜索 URL 自带 _security_check 参数，那不是登出。
    if "security_check" in url and "/web/geek/" in url:
        return False
    if "passport" in url or "/web/user/" in url:
        return True
    if "login" in url and "geek/jobs" not in url and "search/index" not in url:
        return True
    return False


def wait_for_login(drv, prompt: str, timeout: int = 300) -> bool:
    log(prompt)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not is_logged_out(drv):
            return True
        time.sleep(3)
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=0)
    ap.add_argument("--launch", action="store_true")
    ap.add_argument("--launch-port", type=int, default=9223)
    ap.add_argument("--user-data-dir", type=str, default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--company", type=str, default="")
    ap.add_argument("--only-salary", action="store_true")
    ap.add_argument("--source", type=str, default="", help="Boss / 智联")
    ap.add_argument("--no-dedupe", action="store_true")
    args = ap.parse_args()

    jobs = json.loads((ROOT / "jobs.json").read_text(encoding="utf-8"))
    targets = []
    for j in jobs:
        src = j.get("source") or ""
        if args.source and args.source not in src:
            continue
        if not (("Boss" in src) or ("智联" in src)):
            continue
        has_jd = u.looks_real_jd(j)
        has_sal = u.looks_real_salary(u.as_text(j.get("salary")))
        if args.only_salary:
            if has_sal:
                continue
        elif has_jd and has_sal:
            continue
        if args.company and args.company not in j["company"]:
            continue
        targets.append(j)
    if args.limit:
        targets = targets[: args.limit]
    log(f"待补岗位 {len(targets)} 条")
    if not targets:
        return 0

    if args.launch or not args.port:
        port = args.launch_port if args.launch else args.port
        drv = launch(port, Path(args.user_data_dir) if args.user_data_dir else None)
    else:
        drv = attach(args.port)

    done = 0
    seen_hrefs: set[str] = set()
    try:
        drv.get("https://www.zhipin.com/")
        time.sleep(4)
        if not wait_for_login(drv, "请确认 Boss 直聘已登录；若未登录请扫码/登录，我等最多 5 分钟…"):
            log("Boss 直聘登录超时，放弃。")
            return 1

        for job in targets:
            src = job.get("source") or ""
            company = job["company"]
            kw = search_kw(job)
            idx = targets.index(job) + 1
            log(f"\n[{idx}/{len(targets)}] {company} | {src} | {kw}")
            try:
                if "Boss" in src:
                    city = city_code(job, BOSS_CITY)
                    boss_search(drv, kw, city)
                    wait_cards(drv)
                    cards = boss_cards(drv)
                    log(f"  搜索页卡片 {len(cards)} 张")
                    card = pick_best_card(cards, job)
                    if not card:
                        log("  未找到匹配卡片（可能被风控），跳过。")
                        continue
                    if card["href"] in seen_hrefs:
                        log(f"  详情 {card['href'][-40:]} 已抓过，跳过（去重）。")
                        continue
                    seen_hrefs.add(card["href"])
                    det = boss_detail(drv, card["href"])
                    # Boss 详情页被风控时会跳回首页，此时保底用搜索页卡片薪资
                    if "job_detail" not in drv.current_url and card.get("salary"):
                        det["salary"] = det.get("salary") or card["salary"]
                        log("  详情页被风控跳首页，仅用搜索页薪资。")
                else:
                    cards = zhaopin_search(drv, job)
                    log(f"  搜索页卡片 {len(cards)} 张")
                    card = pick_best_card(cards, job)
                    if not card:
                        log("  未找到匹配卡片，跳过。")
                        continue
                    if card["href"] in seen_hrefs:
                        log(f"  详情 {card['href'][-40:]} 已抓过，跳过（去重）。")
                        continue
                    seen_hrefs.add(card["href"])
                    det = zhaopin_detail(drv, card["href"], campus=("校园" in src))

                salary = det.get("salary") or ""
                jd_text = det.get("jd_text") or ""
                if not salary and card.get("salary"):
                    salary = card["salary"]
                if not jd_text and not salary:
                    log("  详情页无 JD 也无薪资，跳过。")
                    continue
                parsed = u.parse_jd_text(jd_text)
                if not u.job_has_jd(parsed):
                    # 结构化职位描述（智联详情页）没有“岗位职责”标题时，
                    # 直接把原文职责整体入库，避免丢 JD。
                    lines = [
                        l.strip(" -•·*、")
                        for l in re.split(r"[\n；;]", jd_text)
                        if 6 <= len(l.strip(" -•·*、")) <= 180
                    ]
                    parsed = {
                        "description": jd_text[:800],
                        "responsibilities": lines[:12],
                        "requirements": [],
                        "skills": u.extract_skills_from_blob(jd_text),
                        "salary": parsed.get("salary") or salary or "",
                    }
                if salary and not u.looks_like_salary_text(salary):
                    parsed["salary"] = ""
                elif salary:
                    parsed["salary"] = salary
                merged = dict(job)
                u.merge_jd_into(merged, parsed)
                if u.looks_real_jd(merged):
                    for key in ("description", "responsibilities", "requirements", "skills"):
                        job[key] = merged[key]
                    job["updated_at"] = u.datetime.now(u.timezone(u.timedelta(hours=8))).strftime("%Y-%m-%d")
                # 本次抓到的薪资直接覆盖旧值（来自匹配岗位的详情页/卡片）
                if u.looks_real_salary(u.as_text(parsed.get("salary"))):
                    job["salary"] = parsed["salary"]
                    job["updated_at"] = u.datetime.now(u.timezone(u.timedelta(hours=8))).strftime("%Y-%m-%d")
                log(f"  薪资：{salary or '（无）'} | JD长度：{len(jd_text)}")
                done += 1
            except Exception as exc:
                log(f"  异常：{exc}")
            time.sleep(1)

        u.copy_jd_across_same_company(jobs)
        u.scrub_false_jd(jobs)
        u.ensure_jd_fields(jobs)
        dedupe_n = 0
        if not args.no_dedupe:
            dedupe_n = dedupe_jobs(jobs)
            u.ensure_jd_fields(jobs)
        jd_n = sum(1 for j in jobs if u.looks_real_jd(j))
        sal_n = sum(1 for j in jobs if u.looks_real_salary(u.as_text(j.get("salary"))))
        meta = json.loads((ROOT / "meta.json").read_text(encoding="utf-8"))
        meta["updated_at"] = u.datetime.now(u.timezone(u.timedelta(hours=8))).strftime("%Y-%m-%d %H:%M")
        meta["count"] = len(jobs)
        meta["jd_filled"] = jd_n
        meta["salary_filled"] = sal_n
        meta["note"] = "职责/薪资按 Boss/智联职位详情原文（登录态抓取）；日历岗无详情时仍为空"
        u.write_site(jobs, meta)
        try:
            u.render_readme(jobs, meta)
        except Exception as exc:
            log(f"README 更新失败（不影响站点）：{exc}")
        log(f"\n完成：{done}/{len(targets)} 条入库；去重 {dedupe_n} 条；站点共 {len(jobs)} 条，原文职责 {jd_n}，薪资 {sal_n}")
    finally:
        try:
            drv.quit()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
