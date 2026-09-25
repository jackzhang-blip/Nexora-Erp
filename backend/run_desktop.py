"""桌面托管入口：使用系统分配端口，并在父进程断开时退出。"""

import json
import argparse
import os
import socket
import sys
import threading
import time

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent-pid", type=int, required=True)
    parent_pid = parser.parse_args().parent_pid
    # 先绑定再交给 Uvicorn，避免探测空闲端口后被其他进程抢占。
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        server = uvicorn.Server(uvicorn.Config(
            "app.main:app", host="127.0.0.1", log_level="warning",
            timeout_graceful_shutdown=3,
        ))

        def watch_parent() -> None:
            # 正常退出、开发重载和主进程崩溃都会关闭管道。
            # 避免缓冲流在解释器退出时被阻塞的守护线程持锁。
            while os.read(sys.stdin.fileno(), 1):
                pass
            server.should_exit = True

        def watch_parent_process() -> None:
            # Windows 中其他继承句柄可能延迟 EOF，直接等待父进程句柄更可靠。
            if sys.platform == "win32":
                import ctypes
                from ctypes import wintypes

                kernel = ctypes.WinDLL("kernel32", use_last_error=True)
                kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
                kernel.OpenProcess.restype = wintypes.HANDLE
                kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
                kernel.WaitForSingleObject.restype = wintypes.DWORD
                kernel.CloseHandle.argtypes = [wintypes.HANDLE]
                handle = kernel.OpenProcess(0x00100000, False, parent_pid)
                if handle:
                    try:
                        kernel.WaitForSingleObject(handle, 0xFFFFFFFF)
                    finally:
                        kernel.CloseHandle(handle)
            else:
                while not server.should_exit:
                    try:
                        os.kill(parent_pid, 0)
                    except ProcessLookupError:
                        break
                    time.sleep(0.5)
            server.should_exit = True

        threading.Thread(target=watch_parent, daemon=True).start()
        threading.Thread(target=watch_parent_process, daemon=True).start()
        print(json.dumps({"port": listener.getsockname()[1]}), flush=True)
        server.run(sockets=[listener])


if __name__ == "__main__":
    main()
