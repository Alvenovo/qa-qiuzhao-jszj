"""保护 same_job 的去重行为，测试当前规则，不重新设计。

当前规则要点（与实现一致）：
- 同公司 + 同岗位名(归一化后) + 同城市 + 同批次 -> 合并
- 详情页 URL 归一化后相同 -> 合并（不看岗位名，这是已验证正确的同详情页行为）
- 不同公司 -> 不合并
"""
from normalize import same_job


def _job(company="公司A", positions=None, locations=None, batch="正式批", apply_url=None, id=None):
    return {
        "company": company,
        "positions": positions or ["测试"],
        "locations": locations or ["南京"],
        "batch": batch,
        "apply_url": apply_url,
        "id": id,
    }


class TestSameCompanySameJobSameCity:
    def test_dedup_same_company_job_city(self):
        a = _job(company="华为", positions=["测试工程师"], locations=["南京"])
        b = _job(company="华为", positions=["测试工程师"], locations=["南京"])
        assert same_job(a, b) is True

    def test_dedup_company_suffix_variant(self):
        a = _job(company="华为集团", positions=["测试"], locations=["杭州"])
        b = _job(company="华为有限公司", positions=["测试"], locations=["杭州"])
        assert same_job(a, b) is True


class TestDifferentCompanies:
    def test_different_companies_no_dedup(self):
        a = _job(company="华为", positions=["测试"], locations=["南京"])
        b = _job(company="阿里巴巴", positions=["测试"], locations=["南京"])
        assert same_job(a, b) is False


class TestSameCompanyDifferentJob:
    def test_different_positions_no_merge(self):
        a = _job(company="华为", positions=["测试工程师"], locations=["南京"])
        b = _job(company="华为", positions=["开发工程师"], locations=["南京"])
        assert same_job(a, b) is False


class TestIguopinDetailUrlDedup:
    """不同岗位 ID 的国聘详情 URL 不能因 URL 归一化而错误合并。

    当前行为：不同 id 的详情 URL 归一化后不同，不会触发 URL 去重；
    为隔离 URL 变量，这里让岗位名不同，确保只有 URL 不同时不合并。
    """

    def test_different_job_ids_different_positions_no_merge(self):
        a = _job(company="中国电信", positions=["测试工程师"],
                  apply_url="https://www.iguopin.com/job/detail?id=123")
        b = _job(company="中国电信", positions=["网络工程师"],
                  apply_url="https://www.iguopin.com/job/detail?id=456")
        assert same_job(a, b) is False

    def test_same_detail_url_with_tracking_dedup(self):
        a = _job(company="中国电信",
                  apply_url="https://www.iguopin.com/job/detail?id=123&utm_source=baidu")
        b = _job(company="中国电信",
                  apply_url="https://www.iguopin.com/job/detail?id=123")
        assert same_job(a, b) is True


class TestSameDetailPageMultipleJobs:
    """当前规则：同详情页 URL 归一化后相同 -> 合并，不看岗位名。

    这是已验证正确的同详情页去重行为：同一 URL 视为同一岗位入口。
    """

    def test_same_url_merged_by_current_rule(self):
        a = _job(company="华为", positions=["测试工程师"],
                  apply_url="https://jobs.bytedance.com/pos/1")
        b = _job(company="华为", positions=["开发工程师"],
                  apply_url="https://jobs.bytedance.com/pos/1")
        assert same_job(a, b) is True
