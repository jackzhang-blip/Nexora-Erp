"""生产 BOM 版本与启停用；工单将引用固定版本的成品和组件。"""

import sqlite3
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.core.database import connection
from app.access.security import require

router = APIRouter(prefix="/api/v1")


class BomLineInput(BaseModel):
    component_material_id: int = Field(gt=0)
    quantity: Decimal

    @field_validator("quantity")
    @classmethod
    def valid_quantity(cls, value: Decimal) -> Decimal:
        # 用料与库存采用相同的三位小数精度，后续领料可逐项核对。
        if not value.is_finite() or value <= 0 or value > 1_000_000 or value.as_tuple().exponent < -3:
            raise ValueError("用料数量须大于零、最多三位小数且不超过一百万")
        return value


class BomInput(BaseModel):
    product_material_id: int = Field(gt=0)
    base_quantity: Decimal = Decimal(1)
    note: str = Field(default="", max_length=200)
    lines: list[BomLineInput] = Field(min_length=1, max_length=100)

    @field_validator("base_quantity")
    @classmethod
    def valid_base_quantity(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value <= 0 or value > 1_000_000 or value.as_tuple().exponent < -3:
            raise ValueError("成品基准数量须大于零、最多三位小数且不超过一百万")
        return value


def bom_data(db: sqlite3.Connection, bom_id: int) -> dict:
    row = db.execute("""SELECT b.*, m.sku AS product_sku, m.name AS product_name,
        m.unit AS product_unit, u.username AS created_by_name
        FROM boms b JOIN materials m ON m.id = b.product_material_id
        JOIN users u ON u.id = b.created_by WHERE b.id = ?""", (bom_id,)).fetchone()
    if not row:
        raise HTTPException(404, "BOM 不存在")
    lines = db.execute("""SELECT bl.id, bl.component_material_id, m.sku,
        m.name AS material_name, m.unit, bl.quantity
        FROM bom_lines bl JOIN materials m ON m.id = bl.component_material_id
        WHERE bl.bom_id = ? ORDER BY bl.id""", (bom_id,)).fetchall()
    return {**dict(row), "lines": [dict(line) for line in lines]}


def has_cycle_after_activation(db: sqlite3.Connection, product_id: int,
                               components: list[int]) -> bool:
    # 只看启用版本；草稿互相引用尚未生效，启用时必须阻止组件回指成品。
    graph: dict[int, set[int]] = {}
    for row in db.execute("""SELECT b.product_material_id, bl.component_material_id
        FROM boms b JOIN bom_lines bl ON bl.bom_id = b.id WHERE b.status = 'active'"""):
        graph.setdefault(row["product_material_id"], set()).add(row["component_material_id"])
    pending = list(components)
    seen: set[int] = set()
    while pending:
        current = pending.pop()
        if current == product_id:
            return True
        if current not in seen:
            seen.add(current)
            pending.extend(graph.get(current, ()))
    return False


@router.get("/boms")
def list_boms(_: dict = Depends(require("production.view"))) -> list[dict]:
    with connection() as db:
        ids = [row[0] for row in db.execute("SELECT id FROM boms ORDER BY id DESC")]
        return [bom_data(db, bom_id) for bom_id in ids]


@router.post("/boms", status_code=201)
def create_bom(payload: BomInput, user: dict = Depends(require("bom.create"))) -> dict:
    component_ids = [line.component_material_id for line in payload.lines]
    if len(set(component_ids)) != len(component_ids):
        raise HTTPException(422, "一份 BOM 不能重复选择同一组件")
    if payload.product_material_id in component_ids:
        raise HTTPException(422, "成品不能直接作为自身组件")
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        known = {row[0] for row in db.execute("SELECT id FROM materials")}
        if payload.product_material_id not in known or not set(component_ids) <= known:
            raise HTTPException(422, "成品或组件物料不存在")
        # 版本号在写事务中分配，两个计划员并行建单也不会拿到同一版本。
        version = db.execute("SELECT COALESCE(MAX(version), 0) + 1 FROM boms WHERE product_material_id = ?",
                             (payload.product_material_id,)).fetchone()[0]
        cursor = db.execute("""INSERT INTO boms(product_material_id, version, base_quantity, note, created_by)
            VALUES (?, ?, ?, ?, ?)""", (payload.product_material_id, version,
                                          str(payload.base_quantity), payload.note.strip(), user["id"]))
        db.executemany("""INSERT INTO bom_lines(bom_id, component_material_id, quantity)
            VALUES (?, ?, ?)""", [(cursor.lastrowid, line.component_material_id, str(line.quantity))
                                 for line in payload.lines])
        return bom_data(db, cursor.lastrowid)


@router.post("/boms/{bom_id}/activate")
def activate_bom(bom_id: int, user: dict = Depends(require("bom.activate"))) -> dict:
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        bom = db.execute("SELECT product_material_id, status FROM boms WHERE id = ?", (bom_id,)).fetchone()
        if not bom:
            raise HTTPException(404, "BOM 不存在")
        if bom["status"] != "draft":
            raise HTTPException(409, "只有 BOM 草稿可以启用")
        if db.execute("SELECT 1 FROM boms WHERE product_material_id = ? AND status = 'active'",
                      (bom["product_material_id"],)).fetchone():
            raise HTTPException(409, "此成品已有启用版本，请先停用旧版本")
        components = [row[0] for row in db.execute(
            "SELECT component_material_id FROM bom_lines WHERE bom_id = ?", (bom_id,))]
        if has_cycle_after_activation(db, bom["product_material_id"], components):
            raise HTTPException(409, "启用后会形成 BOM 循环引用")
        db.execute("""UPDATE boms SET status = 'active', activated_by = ?,
            activated_at = CURRENT_TIMESTAMP WHERE id = ?""", (user["id"], bom_id))
        return bom_data(db, bom_id)


@router.post("/boms/{bom_id}/retire")
def retire_bom(bom_id: int, user: dict = Depends(require("bom.retire"))) -> dict:
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT status FROM boms WHERE id = ?", (bom_id,)).fetchone()
        if not row:
            raise HTTPException(404, "BOM 不存在")
        if row["status"] != "active":
            raise HTTPException(409, "只有启用中的 BOM 可以停用")
        db.execute("""UPDATE boms SET status = 'retired', retired_by = ?,
            retired_at = CURRENT_TIMESTAMP WHERE id = ?""", (user["id"], bom_id))
        return bom_data(db, bom_id)


@router.post("/boms/{bom_id}/cancel")
def cancel_bom(bom_id: int, user: dict = Depends(require("bom.cancel"))) -> dict:
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT status FROM boms WHERE id = ?", (bom_id,)).fetchone()
        if not row:
            raise HTTPException(404, "BOM 不存在")
        if row["status"] != "draft":
            raise HTTPException(409, "只有 BOM 草稿可以取消")
        db.execute("""UPDATE boms SET status = 'cancelled', cancelled_by = ?,
            cancelled_at = CURRENT_TIMESTAMP WHERE id = ?""", (user["id"], bom_id))
        return bom_data(db, bom_id)
