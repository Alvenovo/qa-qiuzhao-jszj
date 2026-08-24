"""保护 normalize_url 的归一化与去重行为，纯离线测试。"""
from normalize import normalize_url


class TestTrackingParamsCleaned:
    def test_utm_source_removed(self):
        url = "https://example.com/job?utm_source=baidu&spm=1001&id=123"
        n = normalize_url(url)
        assert "utm_source" not in n
        assert "spm" not in n

    def test_from_param_removed(self):
        url = "https://example.com/job?from=xiaohongshu&id=456"
        n = normalize_url(url)
        assert "from" not in n
        assert "id=456" in n

    def test_spm_removed(self):
        url = "https://example.com/job?spm=a21bo.2024&id=789"
        n = normalize_url(url)
        assert "spm" not in n
        assert "id=789" in n


class TestJobIdPreserved:
    def test_id_preserved(self):
        n = normalize_url("https://www.iguopin.com/job/detail?id=123")
        assert "id=123" in n

    def test_jdno_preserved(self):
        n = normalize_url("https://example.com/job?jdno=J001")
        assert "jdno=j001" in n

    def test_postid_preserved(self):
        n = normalize_url("https://example.com/job?postid=P002")
        assert "postid=p002" in n

    def test_positionid_preserved(self):
        n = normalize_url("https://example.com/job?positionid=POS3")
        assert "positionid=pos3" in n

    def test_jid_preserved(self):
        n = normalize_url("https://example.com/job?jid=J004")
        assert "jid=j004" in n

    def test_jobno_preserved(self):
        n = normalize_url("https://example.com/job?jobno=NO5")
        assert "jobno=no5" in n


class TestIguopinDedup:
    """特别保护之前已修复的国聘 URL 去重问题。"""

    def test_iguopin_id_123_kept(self):
        n = normalize_url("https://www.iguopin.com/job/detail?id=123")
        assert "id=123" in n

    def test_iguopin_different_ids_not_equal(self):
        a = normalize_url("https://www.iguopin.com/job/detail?id=123")
        b = normalize_url("https://www.iguopin.com/job/detail?id=456")
        assert a != b

    def test_iguopin_tracking_stripped_keeps_id(self):
        full = normalize_url("https://www.iguopin.com/job/detail?id=123&utm_source=baidu&spm=xx")
        bare = normalize_url("https://www.iguopin.com/job/detail?id=123")
        assert full == bare


class TestEdgeCases:
    def test_none_url(self):
        assert normalize_url(None) == ""

    def test_empty_url(self):
        assert normalize_url("") == ""

    def test_normal_url_no_query(self):
        n = normalize_url("https://jobs.bytedance.com/campus/position")
        assert n == "https://jobs.bytedance.com/campus/position"

    def test_trailing_slash_stripped(self):
        n = normalize_url("https://example.com/path/")
        assert not n.endswith("/")

    def test_lowercased(self):
        n = normalize_url("HTTPS://Example.COM/Path?ID=1")
        assert n == n.lower() or n == "https://example.com/path?id=1"