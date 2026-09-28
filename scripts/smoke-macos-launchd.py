"""用当前用户的 launchd 隔离域验证打包服务的启动与异常恢复。"""

import argparse
import json
import os
import re
import shutil
import signal
import socket
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.host_service import MAC_LABEL, mac_plist  # noqa: E402


def available_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def job_pid(label: str) -> int | None:
    result = subprocess.run(["launchctl", "print", label], capture_output=True, text=True)
    if result.returncode:
        return None
    match = re.search(r"^\s*pid = (\d+)$", result.stdout, re.MULTILINE)
    return int(match.group(1)) if match else None


def is_healthy(port: int) -> bool:
    try:
        # 隔离实例使用一次性证书；正式桌面客户端仍必须逐字核对指纹。
        context = ssl._create_unverified_context()
        with urllib.request.urlopen(
            f"https://127.0.0.1:{port}/api/v1/health", context=context, timeout=1
        ) as response:
            return response.status == 200
    except (OSError, urllib.error.URLError):
        return False


def wait_healthy(label: str, port: int, previous_pid: int | None = None) -> int:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        current_pid = job_pid(label)
        if current_pid and current_pid != previous_pid and is_healthy(port):
            return current_pid
        time.sleep(0.25)
    raise RuntimeError("launchd 服务未在 30 秒内启动并通过 HTTPS 健康检查")


def main() -> None:
    parser = argparse.ArgumentParser(description="验证 macOS 打包服务的 launchd 异常恢复")
    parser.add_argument("--source", type=Path, default=ROOT / "build" / "nexora-server")
    args = parser.parse_args()
    if sys.platform != "darwin":
        raise RuntimeError("此检查只在 macOS 上运行")
    source = args.source.resolve()
    if not (source / "nexora-server").is_file():
        raise FileNotFoundError(f"缺少打包服务程序：{source / 'nexora-server'}")

    label = f"gui/{os.getuid()}/{MAC_LABEL}"
    if subprocess.run(["launchctl", "print", label], capture_output=True).returncode == 0:
        raise RuntimeError("当前用户域已有同名 launchd 作业，请先检查，避免干扰已有实例")

    port = available_port()
    with tempfile.TemporaryDirectory(prefix="nexora-launchd-smoke-") as directory:
        root = Path(directory)
        (root / "logs").mkdir()
        # launchd 对桌面工作目录的访问可能受 macOS 隐私保护限制；复制后更接近正式安装位置。
        shutil.copytree(source, root / "service")
        config = root / "host.json"
        config.write_text(
            json.dumps({"name": "Mac 后台恢复隔离测试", "data_dir": str(root / "data"), "port": port}),
            encoding="utf-8",
        )
        plist = root / "host.plist"
        plist.write_bytes(mac_plist(root / "service" / "nexora-server", config, root / "logs"))
        subprocess.run(["launchctl", "bootstrap", f"gui/{os.getuid()}", str(plist)], check=True)
        try:
            first_pid = wait_healthy(label, port)
            os.kill(first_pid, signal.SIGKILL)
            second_pid = wait_healthy(label, port, first_pid)
            print(f"macOS launchd 启动与异常恢复通过：{first_pid} -> {second_pid}")
        except Exception:
            error_log = root / "logs" / "host.err.log"
            if error_log.exists():
                print(error_log.read_text(encoding="utf-8")[-3000:], file=sys.stderr)
            raise
        finally:
            subprocess.run(["launchctl", "bootout", label], check=True)


if __name__ == "__main__":
    main()
