"""供应商与物料基础资料接口。"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.access.security import require
from app.core.database import connection

router = APIRouter(prefix="/api/v1")


class SupplierInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("供应商名称不能为空")
        return value.strip()


class MaterialInput(BaseModel):
    sku: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=120)
    unit: str = Field(min_length=1, max_length=20)

    @field_validator("sku", "name", "unit")
    @classmethod
    def trim_fields(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("字段不能为空")
        return value.strip()

@router.get("/suppliers")
def list_suppliers(_: dict = Depends(require("inventory.view"))) -> list[dict]:
    with connection() as db:
        return [dict(row) for row in db.execute("SELECT id, name FROM suppliers ORDER BY name")]


@router.post("/suppliers", status_code=201)
def create_supplier(payload: SupplierInput, _: dict = Depends(require("catalog.manage"))) -> dict:
    with connection() as db:
        try:
            cursor = db.execute("INSERT INTO suppliers(name) VALUES (?)", (payload.name,))
        except sqlite3.IntegrityError:
            raise HTTPException(409, "供应商已存在") from None
        return {"id": cursor.lastrowid, "name": payload.name}


@router.get("/materials")
def list_materials(_: dict = Depends(require("inventory.view"))) -> list[dict]:
    with connection() as db:
        return [dict(row) for row in db.execute("SELECT id, sku, name, unit FROM materials ORDER BY sku")]


@router.post("/materials", status_code=201)
def create_material(payload: MaterialInput, _: dict = Depends(require("catalog.manage"))) -> dict:
    with connection() as db:
        try:
            cursor = db.execute("INSERT INTO materials(sku, name, unit) VALUES (?, ?, ?)",
                                (payload.sku, payload.name, payload.unit))
        except sqlite3.IntegrityError:
            raise HTTPException(409, "物料编码已存在") from None
        return {"id": cursor.lastrowid, **payload.model_dump()}
