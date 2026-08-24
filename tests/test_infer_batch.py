"""保护 infer_batch 招聘类型判断，宁可 unknown 也不误判校招。"""
from normalize import infer_batch


class TestCampus:
    def test_xiaozhao(self):
        assert infer_batch(None, "校招", "2027届") == "2027秋招"

    def test_qiuzhao(self):
        assert infer_batch(None, "秋招", None) == "2027秋招"

    def test_campus_recruitment(self):
        assert infer_batch("校园招聘", None, None) == "2027秋招"

    def test_2027_cohort_campus(self):
        assert infer_batch("2027届校招", None, "2027届") == "2027秋招"

    def test_2027_campus(self):
        assert infer_batch("2027校园招聘", "正式批", "2027届") == "2027秋招"

    def test_yingjie(self):
        assert infer_batch("应届生招聘", None, None) == "2027秋招"


class TestSocial:
    def test_shezhao(self):
        assert infer_batch(None, "社招", None) == "社招"

    def test_shehui_zhaopin(self):
        assert infer_batch("社会招聘", None, None) == "社招"

    def test_experienced_hire(self):
        assert infer_batch("Experienced Hire", None, None) == "社招"


class TestIntern:
    def test_shixi(self):
        assert infer_batch(None, "实习", None) == "实习"

    def test_shixi_program(self):
        assert infer_batch("实习岗位", None, None) == "实习"


class TestEarlyBatch:
    def test_early_no_campus_semantic(self):
        # 提前批本身不含校招语义 → 仅作为批次阶段保留，不判校招
        assert infer_batch(None, "提前批", None) == "提前批"

    def test_early_with_campus(self):
        # 提前批 + 校园招聘 → 校招
        assert infer_batch("2027届校园招聘提前批", "提前批", "2027届") == "2027秋招"


class TestUnknown:
    def test_no_info(self):
        assert infer_batch(None, None, None) == "unknown"

    def test_test_engineer_only(self):
        # "测试工程师"不能单独证明校招
        assert infer_batch("测试工程师", None, None) == "unknown"

    def test_2027_experience_year(self):
        # "2027年以后工作经验要求"不能证明是校招
        assert infer_batch("2027年以后工作经验要求", None, None) == "unknown"

    def test_zhengshipi_only(self):
        # "正式批"本身不是校招语义
        assert infer_batch(None, "正式批", None) == "unknown"

    def test_qita_only(self):
        # "其他"不能判为校招
        assert infer_batch(None, "其他", None) == "unknown"

    def test_company_name_only(self):
        # 仅公司名不判校招
        assert infer_batch("大疆", None, "不限") == "unknown"