"""保护 classify_job_domain 的软件测试方向识别与硬件/机械排除。"""
from normalize import classify_job_domain


class TestSoftwareTestingKept:
    def _kept(self, **kw):
        r = classify_job_domain(kw)
        assert not r["excluded"], r.get("exclude_reason")
        return r

    def test_software_test_title(self):
        self._kept(positions=["软件测试工程师"], description="负责接口测试与自动化测试")

    def test_test_dev_title(self):
        self._kept(positions=["测试开发工程师"], description="使用pytest进行接口测试")

    def test_automation_test_title(self):
        self._kept(positions=["自动化测试"], description="接口自动化测试与回归测试")

    def test_interface_test_title(self):
        self._kept(positions=["接口测试工程师"], description="接口测试与API测试")

    def test_test_engineer_with_software_jd(self):
        # 泛称"测试工程师" + 软件 JD → 保留
        self._kept(positions=["测试工程师"], description="岗位职责：负责软件测试用例设计，接口测试，自动化测试，缺陷跟踪")


class TestHardwareMechanicalExcluded:
    def _excluded(self, **kw):
        r = classify_job_domain(kw)
        assert r["excluded"], "应被排除但未排除: " + str(kw)
        return r

    def test_mechanical_test(self):
        self._excluded(positions=["机械测试工程师"], description="机械结构测试，力学性能测试，零部件检测")

    def test_hardware_test(self):
        self._excluded(positions=["硬件测试工程师"], description="硬件电路测试，示波器，万用表，信号源")

    def test_structure_test(self):
        self._excluded(positions=["结构测试工程师"], description="结构强度仿真，装配图，工装夹具")

    def test_strength_simulation(self):
        self._excluded(positions=["强度仿真"], description="强度仿真分析，有限元分析")

    def test_hardware_install(self):
        self._excluded(positions=["硬件安装"], description="硬件安装与调试，电气工程")

    def test_quality_inspection(self):
        self._excluded(positions=["产品质量检验"], description="生产制造质量检测")


class TestChinaHangfaBlocked:
    """特别保护之前"中国航发"被正确拦截的逻辑。"""

    def test_china_hangfa_mechanical(self):
        # 中国航发的机械/材料方向岗位应被排除
        r = classify_job_domain({
            "positions": ["测试工程师"],
            "description": "负责机械性能测试，材料拉伸试验，冲击试验，振动试验，耐久性试验，"
                           "发动机零部件检测，强度仿真，装配图与工装夹具",
        })
        assert r["excluded"] is True, "中国航发机械测试方向应被排除"