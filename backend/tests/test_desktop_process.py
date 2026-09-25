import json
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
import pytest


@pytest.mark.parametrize("exit_mode", ["pipe", "parent"])
def test_desktop_process_lifecycle(exit_mode):
    backend = Path(__file__).resolve().parents[1]
    owner = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    process = subprocess.Popen(
        [sys.executable, str(backend / "run_desktop.py"), "--parent-pid", str(owner.pid)], cwd=backend,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True,
    )
    try:
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(process.stdout.readline)
            try:
                line = future.result(timeout=10)
            except concurrent.futures.TimeoutError:
                process.kill()
                raise
        port = json.loads(line)["port"]
        endpoint = f"http://127.0.0.1:{port}/api/v1/health"
        deadline = time.monotonic() + 10
        while True:
            try:
                with urllib.request.urlopen(endpoint, timeout=1) as response:
                    assert json.load(response)["service"] == "nexora-api"
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.1)
        if exit_mode == "pipe":
            process.stdin.close()
        else:
            # 保持管道打开，验证父进程监测不依赖 EOF。
            owner.kill()
            owner.wait(timeout=5)
        assert process.wait(timeout=8) == 0
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        process.stdout.close()
        process.stderr.close()
        if not process.stdin.closed:
            process.stdin.close()
        if owner.poll() is None:
            owner.kill()
            owner.wait(timeout=5)
