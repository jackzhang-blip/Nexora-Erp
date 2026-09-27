"""供 PyInstaller 打包的固定入口。"""

import sys

from app.backup import main as backup_main
from app.host_service import main as host_main
from app.server import main


if __name__ == "__main__":
    # 备份和恢复复用同一已打包服务程序，避免部署机器还需要安装 Python。
    if len(sys.argv) > 1 and sys.argv[1] in {"backup", "restore"}:
        backup_main(sys.argv[1:])
    elif len(sys.argv) > 1 and sys.argv[1] in {"install", "upgrade", "serve-config", "status", "start", "stop"}:
        host_main(sys.argv[1:])
    elif len(sys.argv) > 1 and sys.argv[1] == "service" and sys.platform == "win32":
        from app.windows_service import run_service
        run_service()
    else:
        main()
