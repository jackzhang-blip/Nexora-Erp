"""升级演练必须拒绝已有系统资料和非一次性机器。"""

import runpy
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "smoke-macos-installed-upgrade.py"


def test_installed_upgrade_smoke_refuses_existing_service_and_non_ci(tmp_path):
    require_runner = runpy.run_path(str(SCRIPT))["require_disposable_runner"]
    root = tmp_path / "system"
    plist = tmp_path / "host.plist"

    with pytest.raises(RuntimeError, match="一次性"):
        require_runner(root, plist, None)
    root.mkdir()
    with pytest.raises(RuntimeError, match="拒绝覆盖"):
        require_runner(root, plist, "true")
    root.rmdir()
    plist.write_text("已有服务")
    with pytest.raises(RuntimeError, match="拒绝覆盖"):
        require_runner(root, plist, "true")
    plist.unlink()
    require_runner(root, plist, "true")
