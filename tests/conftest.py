"""pytest 共享配置：把 scripts/ 加入 import 路径，测试完全离线。"""
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))