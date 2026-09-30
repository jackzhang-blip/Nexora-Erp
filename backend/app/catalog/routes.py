"""供应商与物料基础资料接口。"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.access.security import require
from app.core.models import Material, Supplier, SupplierMaterial
from app.core.orm import orm_session, model_data

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


def flush_catalog(db: Session, message: str) -> None:
    # 在接口的事务内触发约束，冲突映射为原有 409 语义，外层统一回滚。
    try:
        db.flush()
    except IntegrityError:
        raise HTTPException(409, message) from None


@router.get("/suppliers")
def list_suppliers(_: dict = Depends(require("inventory.view"))) -> list[dict]:
    with orm_session() as db:
        return [{'id': row.id, 'name': row.name} for row in db.scalars(select(Supplier).order_by(Supplier.name))]


class SupplierPageQuery(BaseModel):
    # 限制页大小和搜索长度，避免客户端提交无界查询。
    query: str = Field(default="", max_length=120)
    page: int = Field(default=1, ge=1, le=2147483647)
    page_size: int = Field(default=20, ge=1, le=100)


@router.post("/suppliers/query")
def query_suppliers(payload: SupplierPageQuery,
                    _: dict = Depends(require("inventory.view"))) -> dict:
    with orm_session() as db:
        # 总数与当前页使用同一快照，搜索按字面子串匹配，不把通配符当查询语法。
        match = func.instr(func.lower(Supplier.name), func.lower(payload.query.strip())) > 0
        total = db.scalar(select(func.count()).select_from(Supplier).where(match))
        page = min(payload.page, max(1, (total + payload.page_size - 1) // payload.page_size))
        rows = db.scalars(select(Supplier).where(match).order_by(Supplier.name, Supplier.id)
            .limit(payload.page_size).offset((page - 1) * payload.page_size))
        return {"items": [{'id': row.id, 'name': row.name} for row in rows], "total": total,
                "page": page, "page_size": payload.page_size}


@router.post("/suppliers", status_code=201)
def create_supplier(payload: SupplierInput, _: dict = Depends(require("catalog.manage"))) -> dict:
    with orm_session(write=True) as db:
        supplier = Supplier(name=payload.name)
        db.add(supplier)
        flush_catalog(db, "供应商已存在")
        return {"id": supplier.id, "name": supplier.name}


@router.get("/materials")
def list_materials(_: dict = Depends(require("inventory.view"))) -> list[dict]:
    with orm_session() as db:
        return [{key: getattr(row, key) for key in ('id', 'sku', 'name', 'unit')}
                for row in db.scalars(select(Material).order_by(Material.sku))]


@router.post("/materials", status_code=201)
def create_material(payload: MaterialInput, _: dict = Depends(require("catalog.manage"))) -> dict:
    with orm_session(write=True) as db:
        material = Material(**payload.model_dump())
        db.add(material)
        flush_catalog(db, "物料编码已存在")
        return {"id": material.id, **payload.model_dump()}


@router.put("/materials/{material_id}")
def update_material(material_id: int, payload: MaterialInput,
                    _: dict = Depends(require("catalog.manage"))) -> dict:
    with orm_session(write=True) as db:
        material = db.get(Material, material_id)
        if material is None:
            raise HTTPException(404, "物料不存在")
        material.sku, material.name, material.unit = payload.sku, payload.name, payload.unit
        flush_catalog(db, "物料编码已存在")
        return {"id": material_id, **payload.model_dump()}


@router.delete("/materials/{material_id}", status_code=204)
def delete_material(material_id: int, _: dict = Depends(require("catalog.manage"))) -> None:
    with orm_session(write=True) as db:
        material = db.get(Material, material_id)
        if material is None:
            raise HTTPException(404, "物料不存在")
        db.delete(material)
        flush_catalog(db, "物料已被业务单据或库存记录引用，不能删除")


@router.put("/suppliers/{supplier_id}")
def update_supplier(supplier_id: int, payload: SupplierInput,
                    _: dict = Depends(require("catalog.manage"))) -> dict:
    with orm_session(write=True) as db:
        supplier = db.get(Supplier, supplier_id)
        if supplier is None:
            raise HTTPException(404, "供应商不存在")
        supplier.name = payload.name
        flush_catalog(db, "供应商已存在")
        return {"id": supplier_id, **payload.model_dump()}


@router.delete("/suppliers/{supplier_id}", status_code=204)
def delete_supplier(supplier_id: int, _: dict = Depends(require("catalog.manage"))) -> None:
    with orm_session(write=True) as db:
        supplier = db.get(Supplier, supplier_id)
        if supplier is None:
            raise HTTPException(404, "供应商不存在")
        db.delete(supplier)
        flush_catalog(db, "供应商已被业务单据引用，不能删除")


@router.get("/supplier-materials")
def list_supplier_materials(_: dict = Depends(require("inventory.view"))) -> list[dict]:
    with orm_session() as db:
        return [model_data(row) for row in db.scalars(select(SupplierMaterial)
            .order_by(SupplierMaterial.supplier_id, SupplierMaterial.material_id))]


@router.put("/suppliers/{supplier_id}/materials/{material_id}", status_code=204)
def bind_supplier_material(supplier_id: int, material_id: int,
                           _: dict = Depends(require("catalog.manage"))) -> None:
    with orm_session(write=True) as db:
        if db.get(Supplier, supplier_id) is None:
            raise HTTPException(404, "供应商不存在")
        if db.get(Material, material_id) is None:
            raise HTTPException(404, "物料不存在")
        if db.get(SupplierMaterial, (supplier_id, material_id)) is None:
            db.add(SupplierMaterial(supplier_id=supplier_id, material_id=material_id))


@router.delete("/suppliers/{supplier_id}/materials/{material_id}", status_code=204)
def unbind_supplier_material(supplier_id: int, material_id: int,
                             _: dict = Depends(require("catalog.manage"))) -> None:
    with orm_session(write=True) as db:
        link = db.get(SupplierMaterial, (supplier_id, material_id))
        if link is None:
            raise HTTPException(404, "供货关系不存在")
        db.delete(link)
