"""供应商与物料基础资料接口。"""

import sqlite3

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


@router.put("/materials/{material_id}")
def update_material(material_id: int, payload: MaterialInput,
                    _: dict = Depends(require("catalog.manage"))) -> dict:
    with connection() as db:
        try:
            cursor = db.execute("UPDATE materials SET sku = ?, name = ?, unit = ? WHERE id = ?",
                                (payload.sku, payload.name, payload.unit, material_id))
        except sqlite3.IntegrityError:
            raise HTTPException(409, "物料编码已存在") from None
        if not cursor.rowcount:
            raise HTTPException(404, "物料不存在")
        return {"id": material_id, **payload.model_dump()}


@router.delete("/materials/{material_id}", status_code=204)
def delete_material(material_id: int, _: dict = Depends(require("catalog.manage"))) -> None:
    with connection() as db:
        try:
            cursor = db.execute("DELETE FROM materials WHERE id = ?", (material_id,))
        except sqlite3.IntegrityError:
            raise HTTPException(409, "物料已被业务单据或库存记录引用，不能删除") from None
        if not cursor.rowcount:
            raise HTTPException(404, "物料不存在")


@router.put("/suppliers/{supplier_id}")
def update_supplier(supplier_id: int, payload: SupplierInput,
                    _: dict = Depends(require("catalog.manage"))) -> dict:
    with connection() as db:
        try:
            cursor = db.execute("UPDATE suppliers SET name = ? WHERE id = ?", (payload.name, supplier_id))
        except sqlite3.IntegrityError:
            raise HTTPException(409, "供应商已存在") from None
        if not cursor.rowcount:
            raise HTTPException(404, "供应商不存在")
        return {"id": supplier_id, **payload.model_dump()}


@router.delete("/suppliers/{supplier_id}", status_code=204)
def delete_supplier(supplier_id: int, _: dict = Depends(require("catalog.manage"))) -> None:
    with connection() as db:
        try:
            cursor = db.execute("DELETE FROM suppliers WHERE id = ?", (supplier_id,))
        except sqlite3.IntegrityError:
            raise HTTPException(409, "供应商已被业务单据引用，不能删除") from None
        if not cursor.rowcount:
            raise HTTPException(404, "供应商不存在")


@router.get("/supplier-materials")
def list_supplier_materials(_: dict = Depends(require("inventory.view"))) -> list[dict]:
    with connection() as db:
        return [dict(row) for row in db.execute(
            "SELECT supplier_id, material_id FROM supplier_materials ORDER BY supplier_id, material_id")]


@router.put("/suppliers/{supplier_id}/materials/{material_id}", status_code=204)
def bind_supplier_material(supplier_id: int, material_id: int,
                           _: dict = Depends(require("catalog.manage"))) -> None:
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        if not db.execute("SELECT 1 FROM suppliers WHERE id = ?", (supplier_id,)).fetchone():
            raise HTTPException(404, "供应商不存在")
        if not db.execute("SELECT 1 FROM materials WHERE id = ?", (material_id,)).fetchone():
            raise HTTPException(404, "物料不存在")
        db.execute("INSERT OR IGNORE INTO supplier_materials(supplier_id, material_id) VALUES (?, ?)",
                   (supplier_id, material_id))


@router.delete("/suppliers/{supplier_id}/materials/{material_id}", status_code=204)
def unbind_supplier_material(supplier_id: int, material_id: int,
                             _: dict = Depends(require("catalog.manage"))) -> None:
    with connection() as db:
        cursor = db.execute("DELETE FROM supplier_materials WHERE supplier_id = ? AND material_id = ?",
                            (supplier_id, material_id))
        if not cursor.rowcount:
            raise HTTPException(404, "供货关系不存在")
