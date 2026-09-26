"""供 PyInstaller 打包的固定入口。"""

from app.server import main


if __name__ == "__main__":
    main()
