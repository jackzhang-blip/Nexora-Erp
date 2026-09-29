"""Windows Service Control Manager 对 FastAPI 的生命周期适配。"""

import servicemanager
import win32service
import win32serviceutil

from app.service.host_service import SERVICE_NAME, read_config, record_service_failure, service_output
from app.server import create_server


class NexoraWindowsService(win32serviceutil.ServiceFramework):
    _svc_name_ = SERVICE_NAME
    _svc_display_name_ = "Nexora ERP Host"
    _svc_description_ = "Nexora ERP 局域网服务端"

    def __init__(self, args):
        super().__init__(args)
        self.server = None
        self.stop_requested = False

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.stop_requested = True
        if self.server is not None:
            # 由 Uvicorn 完成连接和发现广播的有序关闭。
            self.server.should_exit = True

    def SvcDoRun(self):
        try:
            with service_output():
                config = read_config()
                self.server = create_server(config.data_dir, config.name, config.port)
                if self.stop_requested:
                    self.server.should_exit = True
                self.ReportServiceStatus(win32service.SERVICE_RUNNING)
                self.server.run()
        except Exception as error:
            # 服务运行在无人登录的会话中，失败堆栈写入仅管理员可读的系统日志目录。
            record_service_failure()
            servicemanager.LogErrorMsg(f"Nexora ERP 服务启动失败：{error}")
            raise


def run_service() -> None:
    # PyInstaller 可执行文件本身充当服务进程，不依赖开发机的 Python 安装。
    servicemanager.Initialize()
    servicemanager.PrepareToHostSingle(NexoraWindowsService)
    servicemanager.StartServiceCtrlDispatcher()
