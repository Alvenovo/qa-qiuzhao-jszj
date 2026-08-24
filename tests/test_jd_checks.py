"""保护 looks_real_jd 与 _is_search_page_noise 的真实性判断，纯离线。"""
from update import looks_real_jd, _is_search_page_noise


class TestLooksRealJd:
    def test_normal_software_jd_is_real(self):
        job = {
            "description": "岗位职责：负责软件测试用例设计，接口测试与自动化测试。",
            "responsibilities": ["编写测试用例", "接口测试", "缺陷跟踪"],
            "requirements": ["熟悉pytest", "掌握SQL"],
        }
        assert looks_real_jd(job) is True

    def test_empty_jd_not_real(self):
        job = {"description": "", "responsibilities": [], "requirements": []}
        assert looks_real_jd(job) is False

    def test_search_page_junk_not_real(self):
        job = {
            "description": "百度招聘信息\n谷歌招聘信息\n微软招聘信息\n"
                           "腾讯招聘信息\n阿里招聘信息\n网易招聘信息",
            "responsibilities": [],
            "requirements": [],
        }
        assert looks_real_jd(job) is False

    def test_too_short_jd(self):
        job = {"description": "短", "responsibilities": [], "requirements": []}
        assert looks_real_jd(job) is False

    def test_jd_with_test_keyword_count(self):
        # 含"测试">=2 次且总长>=30 字符也算真实
        job = {"description": "负责测试工作，编写测试报告，确保产品质量，"
                             "跟踪缺陷并推动修复，持续优化测试流程",
               "responsibilities": [], "requirements": []}
        assert looks_real_jd(job) is True


class TestIsSearchPageNoise:
    def test_zhilian_search_noise(self):
        text = "百度招聘信息\n腾讯招聘网\n阿里招聘信息\n字节招聘信息\n美团招聘网"
        assert _is_search_page_noise(text) is True

    def test_real_jd_not_noise(self):
        text = ("岗位职责：\n1. 负责软件测试用例设计与执行\n"
                "2. 接口测试与自动化测试\n任职要求：\n1. 本科以上\n2. 熟悉Python")
        assert _is_search_page_noise(text) is False

    def test_empty_text_not_noise(self):
        assert _is_search_page_noise("") is False

    def test_short_text_not_noise(self):
        assert _is_search_page_noise("短文本") is False
