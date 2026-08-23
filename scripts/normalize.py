# -*- coding: utf-8 -*-
"""岗位标准化、状态判断、质量评分、去重辅助。

本模块只含纯函数，不依赖 update.py，避免循环导入。
update.py 通过 ``from normalize import ...`` 调用。
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any, Callable


def normalize_job_name(positions: list[str] | None) -> str:
    """归一化岗位名为标准类别，用于搜索 / 分类 / 统计，不作为唯一主键。"""
    blob = " ".join(positions or [])
    if not blob.strip():
        return "其他"
    if re.search(r"测试开发|测开|SDET|sdet|测试技术开发", blob):
        return "测试开发"
    if re.search(r"质量保障|质量工程|质量工程师|\bQE\b", blob):
        return "质量保障"
    if re.search(r"自动化测试", blob):
        return "自动化测试"
    if re.search(r"性能测试", blob):
        return "性能测试"
    if re.search(r"游戏测试", blob):
        return "游戏测试"
    if re.search(r"渗透测试", blob):
        return "渗透测试"
    if re.search(r"测试", blob):
        return "软件测试"
    return "其他"


def job_category(normalized: str) -> str:
    return normalized


_DEDUP_PREFIX = re.compile(r"^(软件|軟件|应用|應用)")
_DEDUP_SUFFIX = re.compile(r"(工程师|工程師|技术工程师|岗|崗|类|類|实习生|实习|相关)$")


def normalize_for_dedup(position: str) -> str:
    s = (position or "").strip()
    s = _DEDUP_PREFIX.sub("", s)
    changed = True
    while changed:
        changed = False
        m = _DEDUP_SUFFIX.search(s)
        if m:
            s = s[: m.start()] + s[m.end():]
            changed = True
    s = s.strip()
    return s or position or ""


SOURCE_TYPE_MAP: dict[str, str] = {
    "企业官网": "official",
    "校招日历": "calendar",
    "校招日历niuqizp": "calendar",
    "三方校招日历": "calendar",
    "国聘网": "iguopin",
    "牛客": "nowcoder",
    "牛客网": "nowcoder",
    "牛客校招日程": "nowcoder",
    "Boss直聘": "boss",
    "智联校园": "zhaopin",
    "智联招聘": "zhaopin",
    "猎聘": "liepin",
    "前程无忧": "51job",
    "xixicc2027": "xixicc",
    "公开招聘信息": "seed",
    "本地岗位库": "seed",
    "pending": "pending",
}


def source_type(source_str: str | None) -> str:
    if not source_str:
        return "unknown"
    return SOURCE_TYPE_MAP.get(source_str, "other")


SOURCE_RANK: dict[str, int] = {
    "official": 100, "iguopin": 80, "campus": 70, "nowcoder": 60,
    "calendar": 50, "xixicc": 50, "boss": 40, "zhaopin": 40,
    "liepin": 30, "51job": 30, "seed": 20, "other": 10,
    "pending": 5, "unknown": 0,
}


def source_rank(stype: str) -> int:
    return SOURCE_RANK.get(stype or "unknown", 0)


JD_SOURCE_RANK: dict[str, int] = {
    "official": 100, "official_api": 95, "iguopin": 80, "campus": 70,
    "nowcoder": 60, "zhaopin": 50, "boss": 40, "xixicc": 50,
    "other": 30, "company_reused": 20, "unknown": 0,
}


def jd_source_rank(jd_source: str | None) -> int:
    return JD_SOURCE_RANK.get(jd_source or "unknown", 0)


def classify_status(job: dict[str, Any], today: date, freshly_seen: bool = False) -> str:
    if job.get("status") == "closed":
        return "closed"
    deadline = job.get("deadline")
    if deadline:
        try:
            d = date.fromisoformat(deadline)
            return "expired" if d < today else "open"
        except ValueError:
            pass
    return "open" if freshly_seen else "unknown"


def compute_quality(job: dict[str, Any], has_jd_fn: Callable[[dict], bool] | None = None) -> dict[str, Any]:
    if has_jd_fn:
        has_jd = has_jd_fn(job) or bool(job.get("jd_raw_text"))
    else:
        has_jd = bool(
            job.get("description")
            or job.get("responsibilities")
            or job.get("requirements")
            or job.get("jd_raw_text")
        )
    has_deadline = bool(job.get("deadline"))
    has_apply = bool(job.get("apply_url"))
    sources = job.get("sources") or []
    has_official = any(s.get("type") == "official" for s in sources) or job.get("jd_source") == "official"
    score = 0
    score += 30 if has_official else 0
    score += 30 if has_jd else 0
    score += 15 if has_deadline else 0
    score += 15 if has_apply else 0
    score += 5 if job.get("locations") else 0
    score += 5 if job.get("job_category") else 0
    if score >= 90:
        level = "完整"
    elif score >= 70:
        level = "较完整"
    elif score >= 50:
        level = "基本完整"
    else:
        level = "信息不足"
    return {
        "score": score,
        "level": level,
        "has_jd": has_jd,
        "has_deadline": has_deadline,
        "has_apply_url": has_apply,
        "has_official_source": has_official,
    }


def normalize_url(url: str | None) -> str:
    if not url:
        return ""
    u = str(url).strip()
    u = re.sub(r"[?#].*$", "", u)
    u = u.rstrip("/")
    return u.lower()


def norm_company(name: str) -> str:
    s = (name or "").strip()
    s = re.sub(r"(集团|股份|有限公司|有限责任公司|股份有限公司)$", "", s)
    return s.strip()


def same_job(a: dict[str, Any], b: dict[str, Any], is_detail_url_fn: Callable | None = None) -> bool:
    if a.get("official_id") and a["official_id"] == b.get("official_id"):
        return True
    # 零级：id 相同（make_job 基于 公司+批次+截止+城市+岗位名 生成）
    if a.get("id") and a.get("id") == b.get("id"):
        return True
    ua, ub = a.get("apply_url"), b.get("apply_url")
    is_detail = is_detail_url_fn or (lambda u: bool(u and str(u).startswith("http")))
    if ua and ub and is_detail(ua) and normalize_url(ua) == normalize_url(ub):
        return True
    if norm_company(a.get("company")) == norm_company(b.get("company")):
        pa = normalize_for_dedup((a.get("positions") or [""])[0])
        pb = normalize_for_dedup((b.get("positions") or [""])[0])
        if pa and pa == pb:
            ca = set(a.get("locations") or [])
            cb = set(b.get("locations") or [])
            if ca & cb:
                ba = a.get("batch") or ""
                bb = b.get("batch") or ""
                if ba == bb or not ba or not bb:
                    return True
    return False


def similar_position(a: dict[str, Any], b: dict[str, Any]) -> bool:
    pa = normalize_for_dedup((a.get("positions") or [""])[0])
    pb = normalize_for_dedup((b.get("positions") or [""])[0])
    if not pa or not pb:
        return False
    if pa == pb:
        return True
    if pa in pb or pb in pa:
        return True
    return False


def infer_batch(program: str | None, batch: str | None, cohort: str | None) -> str:
    if batch and batch not in ("校招", "社招"):
        return batch
    s = " ".join(filter(None, [program or "", batch or "", cohort or ""]))
    if "提前" in s:
        return "提前批"
    if "实习" in s:
        return "实习"
    if "社招" in s or "社会招聘" in s:
        return "社招"
    if "秋招" in s or "校招" in s or "校园" in s or "2027" in s:
        return "2027秋招"
    return batch or "2027秋招"


# ---------------------------------------------------------------------------
# JD 核心信息提取（技能 / 学历 / 专业 / 经验 / 核心职责 / 软性要求过滤）
# ---------------------------------------------------------------------------

# 技能词表（扩展版，与 update.py 的 JD_SKILL_TERMS 保持一致并补充）
SKILL_TERMS: list[tuple[str, list[str]]] = [
    ("Python", ["Python", "python3", "Python3"]),
    ("Java", ["Java", "JAVA"]),
    ("C++", ["C++", "c++", "C/C++"]),
    ("Go", ["Golang", " Go ", "Go语言"]),
    ("SQL", ["SQL", "sql"]),
    ("MySQL", ["MySQL", "mysql"]),
    ("PostgreSQL", ["PostgreSQL", "Postgres"]),
    ("Redis", ["Redis", "redis"]),
    ("Kafka", ["Kafka", "kafka"]),
    ("Linux", ["Linux", "linux"]),
    ("Git", ["Git", "git"]),
    ("Selenium", ["Selenium", "selenium"]),
    ("Playwright", ["Playwright", "playwright"]),
    ("Appium", ["Appium", "appium"]),
    ("pytest", ["pytest", "py.test"]),
    ("unittest", ["unittest"]),
    ("JUnit", ["JUnit"]),
    ("JMeter", ["JMeter", "jmeter"]),
    ("Postman", ["Postman", "postman"]),
    ("requests", ["requests"]),
    ("Allure", ["Allure", "allure"]),
    ("Jenkins", ["Jenkins", "jenkins"]),
    ("CI/CD", ["CI/CD", "持续集成", "持续交付"]),
    ("Docker", ["Docker", "docker", "容器化"]),
    ("Kubernetes", ["Kubernetes", "k8s", "K8s"]),
    ("接口测试", ["接口测试", "API测试", "API 测试", "接口自动化"]),
    ("自动化测试", ["自动化测试"]),
    ("性能测试", ["性能测试", "压力测试", "负载测试"]),
    ("用例设计", ["用例设计", "测试用例", "用例编写"]),
    ("缺陷跟踪", ["禅道", "Jira", "缺陷跟踪", "bug跟踪"]),
    ("HTTP/HTTPS", ["HTTP", "HTTPS", "http协议"]),
    ("YAML", ["YAML", "yaml"]),
    ("RestAssured", ["RestAssured", "rest-assured"]),
    ("TestNG", ["TestNG"]),
    ("Charles", ["Charles"]),
    ("Fiddler", ["Fiddler"]),
    ("Wireshark", ["Wireshark"]),
]

# 软性要求过滤词（这些不进入核心信息展示）
SOFT_REQUIREMENTS = [
    "责任心强", "责任心", "认真负责", "工作负责", "负责任",
    "积极主动", "主动", "主动性强",
    "沟通能力强", "沟通能力", "沟通", "善于沟通",
    "学习能力强", "学习能力", "学习能力", "善于学习",
    "思维缜密", "思维敏捷", "逻辑思维",
    "细心", "细致", "认真细致",
    "抗压能力强", "抗压能力", "抗压", "承受压力",
    "团队合作", "团队协作", "团队精神", "协作精神",
    "执行力强", "执行力",
    "踏实", "踏实肯干", "勤奋",
    "热情", "热爱",
    "良好的态度", "端正的态度", "态度",
    "自驱力", "自我驱动",
    "亲和力",
    "稳定性好", "稳定性强",
    "能接受加班", "能承受",
]


def _is_soft(line: str) -> bool:
    """判断某条要求是否属于软性要求。"""
    s = line.strip()
    if len(s) < 4 or len(s) > 50:
        return False
    for kw in SOFT_REQUIREMENTS:
        if kw in s:
            return True
    return False


def extract_core_skills(text: str, existing_skills: list[str] | None = None) -> list[str]:
    """从 JD 文本中提取核心技能关键词。"""
    blob = text or ""
    if existing_skills:
        blob = blob + "\n" + " ".join(existing_skills)
    out = []
    for name, aliases in SKILL_TERMS:
        if any(a in blob for a in aliases + [name]):
            out.append(name)
    return list(dict.fromkeys(out))


# 学历提取
_EDU_PATTERNS = [
    (r"(博士(?:研究生|后)?|PhD)", "博士"),
    (r"(硕士(?:研究生)?|研究生|Master)", "硕士"),
    (r"(本科|学士|Bachelor|全日制本科|统招本科)", "本科"),
    (r"(大专|专科|高职|Associate)", "大专"),
]


def extract_education(text: str) -> str:
    """从 JD 文本提取最低学历要求。取最高的要求（如"本科及以上"->本科）。"""
    t = text or ""
    for pattern, label in _EDU_PATTERNS:
        if re.search(pattern, t):
            return label
    return ""


# 专业提取
_MAJOR_KEYWORDS = [
    "计算机科学与技术", "计算机科学", "计算机", "软件工程", "通信工程",
    "电子信息", "信息工程", "信息与计算", "数学", "统计学",
    "电气工程", "电子工程", "物联网", "网络工程",
    "信息安全", "数据科学", "人工智能", "测控技术", "机械",
]


def extract_major(text: str) -> list[str]:
    """从 JD 文本提取专业要求。"""
    t = text or ""
    out = []
    for kw in _MAJOR_KEYWORDS:
        # 精确匹配：专业名后不能紧跟"测试"（避免"自动化测试"误匹配）
        if kw in t and not re.search(kw + r"测试", t):
            out.append(kw)
    # 去重，保留顺序
    seen = set()
    result = []
    for m in out:
        if m not in seen:
            seen.add(m)
            result.append(m)
    return result[:6]


# 经验提取
def extract_experience(text: str) -> str:
    """从 JD 文本提取经验要求。"""
    t = text or ""
    if re.search(r"应届|2027届|2026届|校招|校园招聘|毕业生|不限经验|无经验", t):
        return "应届生"
    m = re.search(r"(\d+)\s*年(?:以上)?(?:相关)?(?:工作)?经验", t)
    if m:
        n = int(m.group(1))
        if n <= 1:
            return "1年以内"
        return f"{n}年"
    if re.search(r"经验不限|无经验要求|不限经验", t):
        return "应届生"
    return ""


# 毕业年份提取
def extract_graduation_year(text: str) -> str:
    """从 JD 文本提取毕业年份要求。"""
    t = text or ""
    m = re.search(r"(20\d{2})\s*(?:届|年)?\s*(?:毕业|应届|校招)", t)
    if m:
        return m.group(1)
    if "2027届" in t or "2027年" in t:
        return "2027"
    if "2026届" in t or "2026年" in t:
        return "2026"
    return ""


# 核心职责提取
def extract_core_responsibilities(responsibilities: list[str] | None, description: str = "") -> list[str]:
    """从职责列表提取前 3-5 条核心职责，过滤软性要求。

    只做压缩和筛选，不生成新职责。
    """
    items = [r for r in (responsibilities or []) if r and r.strip()]
    if not items and description:
        # 如果没有结构化职责但有 description，尝试从 description 切分
        items = [s.strip() for s in re.split(r"[；;\n]", description) if s.strip() and len(s.strip()) > 6]
    # 过滤软性要求
    core = [r for r in items if not _is_soft(r)]
    if not core:
        core = items  # 如果全是软性的，至少保留原样
    # 压缩每条到合理长度
    result = []
    for r in core[:5]:
        r = r.strip()
        if len(r) > 120:
            r = r[:117].rstrip() + "..."
        if r:
            result.append(r)
    return result


# JD 核心信息统一提取入口
def extract_jd_core(job: dict[str, Any]) -> dict[str, Any]:
    """从岗位 dict 中提取 JD 核心信息，返回新增字段。"""
    desc = (job.get("description") or "")
    resp = job.get("responsibilities") or []
    req = job.get("requirements") or []
    skills = job.get("skills") or []
    blob = "\n".join([desc, " ".join(resp), " ".join(req), " ".join(skills)])
    return {
        "core_skills": extract_core_skills(blob, skills),
        "core_responsibilities": extract_core_responsibilities(resp, desc),
        "education": extract_education(blob),
        "major": extract_major(blob),
        "experience": extract_experience(blob),
        "graduation_year": extract_graduation_year(blob),
    }


# ---------------------------------------------------------------------------
# 岗位专业方向分类（软件测试 vs 机械/硬件/材料等）
# ---------------------------------------------------------------------------

# 软件测试方向关键词（命中加分）
SOFTWARE_KW = [
    "Python", "Java", "JavaScript", "TypeScript", "C++", "Go", "SQL",
    "MySQL", "Redis", "Linux", "Git", "HTTP", "API", "接口测试",
    "自动化测试", "性能测试", "安全测试", "Selenium", "Playwright",
    "pytest", "Pytest", "JMeter", "Postman", "Appium", "CI/CD", "Docker",
    "微服务", "Web", "APP", "后端", "前端", "服务端", "接口",
    "数据库", "算法", "AI测试", "大模型测试", "算法测试",
    "移动端测试", "游戏测试", "客户端测试", "数据库测试",
    "网络测试", "unittest", "JUnit", "TestNG", "RestAssured",
    "用例设计", "缺陷跟踪", "回归测试", "功能测试", "兼容性测试",
    "软件测试", "测试开发", "测开", "SDET", "QA", "质量保障",
    "软件质量", "持续集成", "Allure", "Charles", "Fiddler",
]

# 机械/硬件/材料方向关键词（命中减分）
NON_SOFTWARE_KW = [
    "机械设计", "机械结构", "机械加工", "机械相关", "机械专业", "机械装配",
    "CAD", "SolidWorks", "CATIA", "AutoCAD", "UG", "有限元",
    "力学", "材料学", "材料相关", "材料专业",
    "零部件", "汽车零部件", "发动机", "底盘", "车身",
    "电机", "电控", "PLC", "电气设计", "电气专业", "电气工程",
    "电路板", "PCB", "硬件电路", "示波器", "万用表", "信号源", "综测仪",
    "物理实验", "化学实验", "耐久性试验", "可靠性试验",
    "拉伸试验", "冲击试验", "振动试验", "温度试验", "盐雾试验",
    "工艺测试", "生产测试", "制造测试", "设备测试",
    "结构测试", "热测试", "环境测试", "量产测试", "封装测试",
    "芯片测试", "晶圆测试", "射频测试", "光学测试", "半导体工艺",
    "机械测试", "硬件测试", "硬件验证", "电子测试", "电气测试",
    "材料测试", "化学测试", "声学测试",
    "装配图", "卡尺", "工装夹具", "样机", "试制",
    "出厂测试", "转产验收", "产品验证",
    "并网", "整机", "机组", "基站", "通信工程", "链路", "低轨", "信号测试",
]
NON_SOFTWARE_STRONG = [
    "机械专业", "机械相关", "机械装配", "机械设计", "机械加工",
    "发动机", "底盘", "车身", "汽车零部件",
    "示波器", "万用表", "信号源", "综测仪", "卡尺",
    "装配图", "工装夹具", "试制",
    "PLC", "电控", "电气专业", "电气工程",
    "耐久性试验", "拉伸试验", "冲击试验", "振动试验", "盐雾试验",
    "出厂测试", "转产验收", "CAD", "SolidWorks", "CATIA",
    "半导体工艺", "晶圆测试", "封装测试",
    "并网", "机组", "基站", "通信工程",
]

# 岗位名中的明确软件测试方向
SOFTWARE_TITLE_KW = [
    "软件测试", "测试开发", "测开", "自动化测试", "接口测试",
    "性能测试", "安全测试", "游戏测试", "移动端测试", "Web测试",
    "APP测试", "后端测试", "客户端测试", "数据库测试",
    "AI测试", "大模型测试", "算法测试", "网络测试",
    "SDET", "QA工程师", "质量保障", "软件质量", "QE",
]

# 岗位名中的明确非软件方向
NON_SOFTWARE_TITLE_KW = [
    "机械测试", "机械方向", "实验测试员", "硬件测试", "硬件验证",
    "电子测试", "电气测试", "材料测试", "化学测试", "声学测试",
    "结构测试", "力学测试", "热测试", "环境测试",
    "生产测试", "制造测试", "设备测试", "工艺测试",
    "量产测试", "封装测试", "芯片测试", "晶圆测试",
    "射频测试", "光学测试", "汽车测试", "零部件测试",
    "产品质量检验", "质量检测", "质量工程师",
]


def classify_job_domain(job: dict[str, Any]) -> dict[str, Any]:
    """综合岗位名 + JD + 技能判断岗位专业方向。

    返回 {"job_domain": str, "job_domain_confidence": float, "excluded": bool, "exclude_reason": str}
    """
    positions = job.get("positions") or []
    title_blob = " ".join(positions)
    desc = job.get("description") or ""
    resp = " ".join(job.get("responsibilities") or [])
    req = " ".join(job.get("requirements") or [])
    skills = " ".join(job.get("skills") or [])
    raw = job.get("jd_raw_text") or ""
    jd_blob = " ".join([desc, resp, req, skills, raw])

    # 岗位名明确软件方向
    title_software = any(kw in title_blob for kw in SOFTWARE_TITLE_KW)
    # 岗位名明确非软件方向
    title_non_software = any(kw in title_blob for kw in NON_SOFTWARE_TITLE_KW)

    # JD 关键词计数
    sw_hits = sum(1 for kw in SOFTWARE_KW if kw in jd_blob)
    non_sw_hits = sum(1 for kw in NON_SOFTWARE_KW if kw in jd_blob)
    non_sw_strong = sum(1 for kw in NON_SOFTWARE_STRONG if kw in jd_blob)

    # 岗位名"测试工程师"等泛称：需要靠 JD 判断
    generic_title = bool(re.search(r"^测试工程师$|^测试$|^测试类$|^测试技术岗$|^测试岗$", title_blob.strip()))

    # --- 判断逻辑 ---
    # 1. 岗位名明确软件方向 → 默认保留
    #    修复：先判 software 再判 non_software，避免"软件质量工程师"被误杀
    if title_software:
        # JD 有 >=3 个强非软件信号且非软件关键词远超软件关键词 → 排除
        if non_sw_strong >= 3 and non_sw_hits > sw_hits * 2:
            domain = _match_domain(jd_blob)
            return {"job_domain": domain, "job_domain_confidence": 0.65,
                    "excluded": True, "exclude_reason": f"岗位名为软件方向但 JD 主要涉及{domain}领域"}
        return {"job_domain": "software_testing", "job_domain_confidence": 0.95,
                "excluded": False, "exclude_reason": ""}

    # 2. 岗位名明确非软件方向 → 排除
    #    但如果 JD 有大量软件关键词，可能是软件岗（rescue）
    if title_non_software:
        if sw_hits >= 5 and sw_hits > non_sw_hits * 2:
            return {"job_domain": "software_testing", "job_domain_confidence": 0.7,
                    "excluded": False, "exclude_reason": ""}
        domain = _match_domain(title_blob)
        return {"job_domain": domain, "job_domain_confidence": 0.9,
                "excluded": True, "exclude_reason": "岗位名含非软件测试方向关键词"}

    # 3. 泛称岗位（"测试工程师"等）→ 靠 JD 判断
    # 软件关键词明显占优 → 保留
    if sw_hits >= 3 and sw_hits > non_sw_hits:
        return {"job_domain": "software_testing",
                "job_domain_confidence": min(0.9, 0.5 + sw_hits * 0.05),
                "excluded": False, "exclude_reason": ""}
    # 强非软件信号 + 非软件关键词占优 → 排除
    if non_sw_strong >= 1 and non_sw_hits > sw_hits:
        domain = _match_domain(jd_blob)
        return {"job_domain": domain,
                "job_domain_confidence": min(0.9, 0.5 + non_sw_hits * 0.05),
                "excluded": True, "exclude_reason": f"JD 主要涉及{domain}领域，非软件测试"}
    # 无强信号但非软件关键词明显占优 → 排除
    if non_sw_hits >= 3 and non_sw_hits > sw_hits:
        domain = _match_domain(jd_blob)
        return {"job_domain": domain,
                "job_domain_confidence": min(0.85, 0.5 + non_sw_hits * 0.05),
                "excluded": True, "exclude_reason": f"JD 主要涉及{domain}领域，非软件测试"}
    # 无 JD 或关键词不足 → unknown，保留（不误杀）
    return {"job_domain": "unknown", "job_domain_confidence": 0.0,
            "excluded": False, "exclude_reason": ""}


def _match_domain(text: str) -> str:
    """从文本中匹配最具体的非软件方向。"""
    domain_map = [
        ("mechanical_testing", ["机械", "力学", "装配", "CAD", "SolidWorks", "零部件", "发动机", "底盘"]),
        ("hardware_testing", ["硬件", "电路", "PCB", "示波器", "万用表", "电气", "电控"]),
        ("automotive_testing", ["汽车", "零部件", "发动机", "底盘", "车身"]),
        ("electrical_testing", ["电气", "电控", "PLC", "电机"]),
        ("material_testing", ["材料", "拉伸", "冲击", "盐雾"]),
        ("manufacturing_quality", ["生产", "制造", "工艺", "出厂", "转产", "试制"]),
        ("chemical_testing", ["化学"]),
    ]
    for domain, keywords in domain_map:
        if any(kw in text for kw in keywords):
            return domain
    return "other"
