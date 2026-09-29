"""服务状态与实例公开信息接口。"""

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.core.database import connection

router = APIRouter(prefix="/api/v1")


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


@router.get("/health", response_model=HealthResponse, tags=["health"])
def health(request: Request) -> HealthResponse:
    # 健康检查仅说明进程存活，不向未登录用户透露业务数据。
    return HealthResponse(status="ok", service="nexora-api", version=request.app.version)


@router.get("/setup/status")
def setup_status() -> dict:
    with connection() as db:
        return {"needs_setup": db.execute("SELECT NOT EXISTS(SELECT 1 FROM users)").fetchone()[0] == 1}


@router.get("/server/info")
def server_info(request: Request) -> dict:
    # 发现阶段只公开实例身份和兼容版本，不返回用户或业务资料。
    with connection() as db:
        row = db.execute("SELECT id, name FROM server_identity LIMIT 1").fetchone()
        return {"id": row["id"], "name": row["name"], "version": request.app.version,
                "ready": db.execute("SELECT EXISTS(SELECT 1 FROM users)").fetchone()[0] == 1}
