"""服务状态与实例公开信息接口。"""

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlalchemy import select

from app.core.models import User, ServerIdentity
from app.core.orm import orm_session

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
    with orm_session() as db:
        return {"needs_setup": db.scalar(select(User.id).limit(1)) is None}


@router.get("/server/info")
def server_info(request: Request) -> dict:
    # 发现阶段只公开实例身份和兼容版本，不返回用户或业务资料。
    with orm_session() as db:
        row = db.scalar(select(ServerIdentity).limit(1))
        return {"id": row.id, "name": row.name, "version": request.app.version,
                "ready": db.scalar(select(User.id).limit(1)) is not None}
