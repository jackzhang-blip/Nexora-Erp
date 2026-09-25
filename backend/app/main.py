from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Nexora ERP API", version="0.1.0")


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: Literal["nexora-api"]
    version: str


@app.get("/api/v1/health", response_model=HealthResponse, tags=["health"])
def health() -> HealthResponse:
    # 此接口仅检查服务存活，不代表数据库或业务模块已就绪。
    return HealthResponse(status="ok", service="nexora-api", version=app.version)
