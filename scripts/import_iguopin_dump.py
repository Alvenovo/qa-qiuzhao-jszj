# -*- coding: utf-8 -*-
"""把国聘浏览器抓到的职位详情写入 jobs.json / index.html。"""
from __future__ import annotations

import json
import re
from pathlib import Path

import update as u

DUMP = Path(r"C:\Users\王文东\.cursor\browser-logs\cdp-response-Runtime.evaluate-2026-08-22T17-28-07-643Z.json")
ROOT = Path(__file__).resolve().parents[1]
PROV = {"310000", "320000", "330000", "340000"}
HARDWARE_TITLE = re.compile(
    r"机械测试|通讯测试|无线通信|测量方向|生产辅助|射频测试|硬件测试|汽车通讯|GNSS测试|仿真测试"
)


def walk_jobs(obj):
    if isinstance(obj, dict):
        if isinstance(obj.get("jobs"), list) and obj["jobs"] and isinstance(obj["jobs"][0], dict) and obj["jobs"][0].get("job_id"):
            return obj["jobs"]
        for v in obj.values():
            found = walk_jobs(v)
            if found:
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = walk_jobs(v)
            if found:
                return found
    return []


def in_region(row: dict) -> bool:
    for d in row.get("district_list") or []:
        if str(d.get("province") or "") in PROV:
            return True
        area = d.get("area_cn") or ""
        cities, provs = u.js_zj_cities(u.split_locations(area.replace("-", "、")))
        if cities or provs:
            return True
    return False


def main() -> None:
    raw = json.loads(DUMP.read_text(encoding="utf-8"))
    rows = walk_jobs(raw)
    converted = []
    for row in rows:
        title = u.as_text(row.get("job_name"))
        if not u.TEST_RE.search(title):
            continue
        if HARDWARE_TITLE.search(title):
            continue
        if not in_region(row):
            continue
        contents = u.as_text(row.get("contents"))
        if "<" in contents:
            contents = u.html_to_text(contents)
        salary = u.salary_from_posting(row, contents)
        jid = u.as_text(row.get("job_id"))
        job = u.make_job(
            company=u.as_text(row.get("company_name")),
            program=u.as_text(row.get("recruitment_type_cn")) or "校园招聘",
            cohort="2027届",
            batch=u.as_text(row.get("nature_cn")) or "校招",
            positions=[title],
            locations=u._iguopin_locations(row),
            start_date=row.get("start_time"),
            deadline=row.get("end_time"),
            apply_url=f"https://www.iguopin.com/job/detail?id={jid}",
            source="国聘网",
            industry="国企",
            description=contents,
            raw_jd=contents,
            salary=salary,
            search_hint=f"国聘职位详情：https://www.iguopin.com/job/detail?id={jid}",
        )
        if job:
            converted.append(job)
    existing = json.loads((ROOT / "jobs.json").read_text(encoding="utf-8"))
    existing_jobs = []
    for row in existing:
        job = u.make_job(**{k: v for k, v in row.items() if k != "id"})
        if job and not HARDWARE_TITLE.search(" ".join(job.get("positions") or [])):
            existing_jobs.append(job)
    jobs = u.merge_jobs(existing_jobs + converted)
    u.copy_jd_across_same_company(jobs)
    u.scrub_false_jd(jobs)
    u.ensure_jd_fields(jobs)
    jd_n = sum(1 for j in jobs if u.looks_real_jd(j))
    sal_n = sum(1 for j in jobs if u.looks_real_salary(u.as_text(j.get("salary"))))
    meta = json.loads((ROOT / "meta.json").read_text(encoding="utf-8"))
    meta["updated_at"] = u.datetime.now(u.timezone(u.timedelta(hours=8))).strftime("%Y-%m-%d %H:%M")
    meta["count"] = len(jobs)
    meta["jd_filled"] = jd_n
    meta["salary_filled"] = sal_n
    meta["note"] = "职责/薪资按国聘职位原文；日历岗无详情时仍为空"
    u.write_site(jobs, meta)
    (ROOT / "iguopin_jobs.json").write_text(
        json.dumps(converted, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"国聘入库 {len(converted)} 条；站点共 {len(jobs)} 条，原文职责 {jd_n}，薪资 {sal_n}")
    for j in converted[:8]:
        print(j["company"], j["positions"][:1], j.get("salary"), (j.get("description") or "")[:40])


if __name__ == "__main__":
    main()
