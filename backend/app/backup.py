"""保留现有 app.backup 命令入口。"""

from app.service.backup import main


if __name__ == "__main__":
    main()
