"""系统域检查的隔离标签不能覆盖正式服务。"""

import plistlib
import runpy
from pathlib import Path

import pytest

from app.service.host_service import MAC_LABEL


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "smoke-macos-launchd.py"


def test_system_smoke_plist_uses_isolated_label_and_keeps_service_controls(tmp_path):
    build_plist = runpy.run_path(str(SCRIPT))["system_smoke_plist"]
    binary = tmp_path / "service" / "nexora-server"
    config = tmp_path / "host.json"
    logs = tmp_path / "logs"
    label = f"{MAC_LABEL}.smoke.test123"

    value = plistlib.loads(build_plist(binary, config, logs, label))
    assert value["Label"] == label
    assert value["ProgramArguments"] == [str(binary), "serve-config", "--config", str(config)]
    assert value["RunAtLoad"] is True
    assert value["KeepAlive"] is True
    with pytest.raises(ValueError, match="隔离"):
        build_plist(binary, config, logs, MAC_LABEL)
    with pytest.raises(ValueError, match="隔离"):
        build_plist(binary, config, logs, "com.example.other-service")
