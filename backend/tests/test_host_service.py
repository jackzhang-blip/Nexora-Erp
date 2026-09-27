"""系统服务安装配置的边界与失败回滚。"""

import json
import plistlib
import subprocess
import sys

import pytest

from app import host_service


def test_system_command_failure_keeps_service_diagnostic(monkeypatch):
    # Windows 服务控制器的错误文本比退出码更能说明启动失败的原因。
    monkeypatch.setattr(host_service.subprocess, "run", lambda *_args, **_kwargs: subprocess.CompletedProcess(
        args=["sc.exe"], returncode=5, stdout="[SC] StartService FAILED 5: Access is denied.", stderr=""))
    with pytest.raises(RuntimeError, match="Access is denied"):
        host_service._run("sc.exe", "start", host_service.SERVICE_NAME)


def test_service_startup_failure_writes_restricted_host_log(monkeypatch, tmp_path):
    logs = tmp_path / "logs"
    logs.mkdir()
    monkeypatch.setattr(host_service, "system_root", lambda: tmp_path)

    try:
        raise RuntimeError("服务启动失败样例")
    except RuntimeError:
        host_service.record_service_failure()

    assert "服务启动失败样例" in (logs / "host.err.log").read_text()


def test_windows_service_output_works_without_console(monkeypatch, tmp_path):
    logs = tmp_path / "logs"
    logs.mkdir()
    monkeypatch.setattr(host_service, "system_root", lambda: tmp_path)
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)

    with host_service.service_output():
        # 模拟服务管理器无控制台的环境，验证日志初始化依赖的 isatty 接口可用。
        assert sys.stdout.isatty() is False
        assert sys.stderr.isatty() is False
        print("服务运行日志")
        print("服务错误日志", file=sys.stderr)

    assert "服务运行日志" in (logs / "host.out.log").read_text()
    assert "服务错误日志" in (logs / "host.err.log").read_text()


def test_host_config_rejects_invalid_paths_and_ports(tmp_path):
    value = {"name": "  固定主机  ", "data_dir": str(tmp_path / "erp-data"), "port": 8123}
    parsed = host_service.HostConfig.parse(value)
    assert parsed.name == "固定主机"
    assert parsed.data_dir == tmp_path / "erp-data"
    for invalid in ("relative", str(tmp_path.anchor)):
        with pytest.raises(ValueError):
            host_service.HostConfig.parse({**value, "data_dir": invalid})
    for invalid in (True, 0, 65536, "8000"):
        with pytest.raises(ValueError):
            host_service.HostConfig.parse({**value, "port": invalid})


def test_mac_install_starts_boot_service_without_changing_instance_data(monkeypatch, tmp_path):
    root = tmp_path / "system"
    plist = tmp_path / "launch-daemon.plist"
    source = tmp_path / "packaged"
    source.mkdir()
    (source / "nexora-server").write_text("service-binary")
    data_dir = tmp_path / "existing-instance"
    data_dir.mkdir()
    (data_dir / "nexora.db").write_bytes(b"existing")
    commands = []
    monkeypatch.setattr(host_service.sys, "platform", "darwin")
    monkeypatch.setattr(host_service, "system_root", lambda: root)
    monkeypatch.setattr(host_service, "MAC_PLIST", plist)
    monkeypatch.setattr(host_service, "_require_admin", lambda: None)
    monkeypatch.setattr(host_service, "_run", lambda *args: commands.append(args))

    config = host_service.HostConfig("主机", data_dir, 8123)
    host_service.install_service(config, source)
    assert json.loads((root / "host.json").read_text())["data_dir"] == str(data_dir)
    assert (data_dir / "nexora.db").read_bytes() == b"existing"
    settings = plistlib.loads(plist.read_bytes())
    assert settings["RunAtLoad"] is True
    assert settings["KeepAlive"] is True
    assert settings["ProgramArguments"][:2] == [str(root / "service" / "nexora-server"), "serve-config"]
    assert commands == [("launchctl", "bootstrap", "system", str(plist))]


def test_windows_install_grants_system_access_to_selected_instance(monkeypatch, tmp_path):
    root = tmp_path / "system"
    source = tmp_path / "packaged"
    source.mkdir()
    (source / "nexora-server.exe").write_text("service-binary")
    data_dir = tmp_path / "private-instance"
    commands = []
    monkeypatch.setattr(host_service.sys, "platform", "win32")
    monkeypatch.setattr(host_service, "system_root", lambda: root)
    monkeypatch.setattr(host_service, "_require_admin", lambda: None)
    monkeypatch.setattr(host_service, "_run", lambda *args: commands.append(args))
    monkeypatch.setattr(host_service, "service_running", lambda: True)
    monkeypatch.setattr(host_service.time, "sleep", lambda _seconds: None)

    host_service.install_service(host_service.HostConfig("主机", data_dir, 8123), source)

    # SCM 启动前必须能访问数据库和证书；用户原有 ACL 不应被整体替换。
    assert data_dir.is_dir()
    program_acl = [command for command in commands if command[:2] == ("icacls.exe", str(root))]
    assert program_acl[0][2] == "/grant:r"
    assert program_acl[1] == ("icacls.exe", str(root), "/inheritance:r")
    assert not any("/T" in command for command in program_acl)
    assert ("icacls.exe", str(data_dir), "/grant", "*S-1-5-18:(OI)(CI)F", "/T") in commands
    assert commands[-2] == ("sc.exe", "start", host_service.SERVICE_NAME)
    assert commands[-1] == ("sc.exe", "config", host_service.SERVICE_NAME, "start=", "auto")


def test_windows_install_rolls_back_when_service_exits_immediately(monkeypatch, tmp_path):
    root = tmp_path / "system"
    source = tmp_path / "packaged"
    source.mkdir()
    (source / "nexora-server.exe").write_text("service-binary")
    monkeypatch.setattr(host_service.sys, "platform", "win32")
    monkeypatch.setattr(host_service, "system_root", lambda: root)
    monkeypatch.setattr(host_service, "_require_admin", lambda: None)
    monkeypatch.setattr(host_service, "_run", lambda *_args: None)
    monkeypatch.setattr(host_service, "service_running", lambda: False)
    monkeypatch.setattr(host_service.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(host_service.subprocess, "run", lambda *args, **_kwargs: subprocess.CompletedProcess(
        args=args, returncode=0, stdout="diagnostic", stderr=""))

    with pytest.raises(RuntimeError, match="启动后退出"):
        host_service.install_service(host_service.HostConfig("主机", tmp_path / "instance", 8123), source)

    assert not (root / "host.json").exists()
    assert not (root / "service").exists()


def test_failed_mac_registration_removes_partial_install(monkeypatch, tmp_path):
    root = tmp_path / "system"
    plist = tmp_path / "launch-daemon.plist"
    source = tmp_path / "packaged"
    source.mkdir()
    (source / "nexora-server").write_text("service-binary")
    monkeypatch.setattr(host_service.sys, "platform", "darwin")
    monkeypatch.setattr(host_service, "system_root", lambda: root)
    monkeypatch.setattr(host_service, "MAC_PLIST", plist)
    monkeypatch.setattr(host_service, "_require_admin", lambda: None)

    def fail(*_):
        raise RuntimeError("launchctl failed")

    monkeypatch.setattr(host_service, "_run", fail)
    with pytest.raises(RuntimeError, match="launchctl failed"):
        host_service.install_service(host_service.HostConfig("主机", tmp_path / "data", 8123), source)
    assert not (root / "host.json").exists()
    assert not (root / "service").exists()
    assert not plist.exists()


def test_upgrade_backs_up_and_replaces_service_without_touching_instance(monkeypatch, tmp_path):
    root = tmp_path / "system"
    current = root / "service"
    current.mkdir(parents=True)
    (current / "nexora-server").write_text("old")
    source = tmp_path / "release"
    source.mkdir()
    (source / "nexora-server").write_text("new")
    data = tmp_path / "instance"
    data.mkdir()
    (data / "nexora.db").write_text("unchanged")
    (root / "host.json").write_text(json.dumps({"name": "主机", "data_dir": str(data), "port": 8123}))
    commands = []
    monkeypatch.setattr(host_service.sys, "platform", "darwin")
    monkeypatch.setattr(host_service, "system_root", lambda: root)
    monkeypatch.setattr(host_service, "service_running", lambda: True)
    monkeypatch.setattr(host_service, "_require_admin", lambda: None)
    monkeypatch.setattr(host_service, "_run", lambda *args: commands.append(args))
    monkeypatch.setattr(host_service, "create_backup", lambda _data, output: output.write_text("backup"))
    backup = host_service.upgrade_service(source)
    assert backup.read_text() == "backup"
    assert (current / "nexora-server").read_text() == "new"
    assert (data / "nexora.db").read_text() == "unchanged"
    assert commands[0] == ("launchctl", "bootout", f"system/{host_service.MAC_LABEL}")
    assert commands[-1][0:2] == ("launchctl", "bootstrap")


def test_windows_upgrade_limits_backup_directory_to_system_and_admin(monkeypatch, tmp_path):
    root = tmp_path / "system"
    current = root / "service"
    current.mkdir(parents=True)
    (current / "nexora-server.exe").write_text("old")
    source = tmp_path / "release"
    source.mkdir()
    (source / "nexora-server.exe").write_text("new")
    data = tmp_path / "instance"
    data.mkdir()
    (root / "host.json").write_text(json.dumps({"name": "主机", "data_dir": str(data), "port": 8123}))
    commands = []
    monkeypatch.setattr(host_service.sys, "platform", "win32")
    monkeypatch.setattr(host_service, "system_root", lambda: root)
    monkeypatch.setattr(host_service, "service_running", lambda: False)
    monkeypatch.setattr(host_service, "_require_admin", lambda: None)
    monkeypatch.setattr(host_service, "_run", lambda *args: commands.append(args))
    monkeypatch.setattr(host_service, "create_backup", lambda _data, output: output.write_text("backup"))

    backup = host_service.upgrade_service(source)

    assert backup.read_text() == "backup"
    assert (current / "nexora-server.exe").read_text() == "new"
    backup_acl = [command for command in commands if command[:2] == ("icacls.exe", str(root / "backups"))]
    assert backup_acl[0][2] == "/grant:r"
    assert backup_acl[1] == ("icacls.exe", str(root / "backups"), "/inheritance:r")


def test_upgrade_restores_old_program_when_restart_fails(monkeypatch, tmp_path):
    root = tmp_path / "system"
    current = root / "service"
    current.mkdir(parents=True)
    (current / "nexora-server").write_text("old")
    source = tmp_path / "release"
    source.mkdir()
    (source / "nexora-server").write_text("new")
    data = tmp_path / "instance"
    data.mkdir()
    (root / "host.json").write_text(json.dumps({"name": "主机", "data_dir": str(data), "port": 8123}))
    calls = []
    monkeypatch.setattr(host_service.sys, "platform", "darwin")
    monkeypatch.setattr(host_service, "system_root", lambda: root)
    monkeypatch.setattr(host_service, "service_running", lambda: False)
    monkeypatch.setattr(host_service, "_require_admin", lambda: None)
    monkeypatch.setattr(host_service, "create_backup", lambda _data, output: output.write_text("backup"))

    def fail_once(*args):
        calls.append(args)
        if len(calls) == 2:
            raise RuntimeError("new service failed")

    monkeypatch.setattr(host_service, "_run", fail_once)
    # 测试只让首个 bootstrap 失败；先模拟运行状态以进入启动路径。
    states = iter((True, False))
    monkeypatch.setattr(host_service, "service_running", lambda: next(states))
    with pytest.raises(RuntimeError, match="new service failed"):
        host_service.upgrade_service(source)
    assert (current / "nexora-server").read_text() == "old"
