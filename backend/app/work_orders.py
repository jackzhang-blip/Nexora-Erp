"""生产工单以启用 BOM 创建需料快照；发料和完工后续接入。"""

import sqlite3
from decimal import Decimal, ROUND_CEILING

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from .database import connection
from .inventory import require_warehouse
from .security import require

router = APIRouter(prefix="/api/v1")


class WorkOrderInput(BaseModel):
    bom_id: int = Field(gt=0)
    warehouse_id: int = Field(gt=0)
    target_quantity: Decimal
    reference: str = Field(default="", max_length=100)
    note: str = Field(default="", max_length=200)

    @field_validator("target_quantity")
    @classmethod
    def valid_quantity(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value <= 0 or value > 1_000_000 or value.as_tuple().exponent < -3:
            raise ValueError("目标产量须大于零、最多三位小数且不超过一百万")
        return value


def work_order_data(db: sqlite3.Connection, order_id: int) -> dict:
    row = db.execute("""SELECT wo.*, b.version AS bom_version,
        b.product_material_id, m.sku AS product_sku, m.name AS product_name,
        m.unit AS product_unit, w.name AS warehouse_name, u.username AS created_by_name
        FROM work_orders wo JOIN boms b ON b.id = wo.bom_id
        JOIN materials m ON m.id = b.product_material_id
        JOIN warehouses w ON w.id = wo.warehouse_id
        JOIN users u ON u.id = wo.created_by WHERE wo.id = ?""", (order_id,)).fetchone()
    if not row:
        raise HTTPException(404, "生产工单不存在")
    lines = db.execute("""SELECT wol.id, wol.component_material_id, m.sku,
        m.name AS material_name, m.unit, wol.required_quantity
        FROM work_order_lines wol JOIN materials m ON m.id = wol.component_material_id
        WHERE wol.work_order_id = ? ORDER BY wol.id""", (order_id,)).fetchall()
    return {**dict(row), "lines": [dict(line) for line in lines]}


@router.get("/work-orders")
def list_work_orders(_: dict = Depends(require("production.view"))) -> list[dict]:
    with connection() as db:
        ids = [row[0] for row in db.execute("SELECT id FROM work_orders ORDER BY id DESC")]
        return [work_order_data(db, order_id) for order_id in ids]


@router.post("/work-orders", status_code=201)
def create_work_order(payload: WorkOrderInput,
                      user: dict = Depends(require("work_order.create"))) -> dict:
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        bom = db.execute("SELECT status, base_quantity FROM boms WHERE id = ?", (payload.bom_id,)).fetchone()
        if not bom:
            raise HTTPException(422, "BOM 不存在")
        if bom["status"] != "active":
            raise HTTPException(409, "只有启用中的 BOM 可用于新工单")
        require_warehouse(db, payload.warehouse_id)
        requirements = []
        for line in db.execute("""SELECT component_material_id, quantity FROM bom_lines
            WHERE bom_id = ?""", (payload.bom_id,)):
            # 需求按库存的三位精度向上取整，防止比例换算后低估领料量。
            needed = (payload.target_quantity * Decimal(line["quantity"]) /
                      Decimal(bom["base_quantity"])).quantize(Decimal("0.001"), rounding=ROUND_CEILING)
            if needed > 1_000_000:
                raise HTTPException(422, "工单组件需求超过一百万，请拆分工单")
            requirements.append((line["component_material_id"], str(needed)))
        if not requirements:
            raise HTTPException(409, "BOM 没有组件，无法创建工单")
        cursor = db.execute("""INSERT INTO work_orders(
            bom_id, warehouse_id, target_quantity, reference, note, created_by)
            VALUES (?, ?, ?, ?, ?, ?)""", (payload.bom_id, payload.warehouse_id,
                str(payload.target_quantity), payload.reference.strip(), payload.note.strip(), user["id"]))
        db.executemany("""INSERT INTO work_order_lines(
            work_order_id, component_material_id, required_quantity) VALUES (?, ?, ?)""",
            [(cursor.lastrowid, material_id, quantity) for material_id, quantity in requirements])
        return work_order_data(db, cursor.lastrowid)


@router.post("/work-orders/{order_id}/release")
def release_work_order(order_id: int, user: dict = Depends(require("work_order.release"))) -> dict:
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("""SELECT wo.status, b.status AS bom_status FROM work_orders wo
            JOIN boms b ON b.id = wo.bom_id WHERE wo.id = ?""", (order_id,)).fetchone()
        if not row:
            raise HTTPException(404, "生产工单不存在")
        if row["status"] != "draft":
            raise HTTPException(409, "只有工单草稿可以下达")
        if row["bom_status"] != "active":
            raise HTTPException(409, "BOM 已停用，请取消草稿并使用新版本建单")
        db.execute("""UPDATE work_orders SET status = 'released', released_by = ?,
            released_at = CURRENT_TIMESTAMP WHERE id = ?""", (user["id"], order_id))
        return work_order_data(db, order_id)


@router.post("/work-orders/{order_id}/cancel")
def cancel_work_order(order_id: int, user: dict = Depends(require("work_order.cancel"))) -> dict:
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT status FROM work_orders WHERE id = ?", (order_id,)).fetchone()
        if not row:
            raise HTTPException(404, "生产工单不存在")
        # 发料后由后续更正流程处理，不能用取消抹去真实库存流水。
        if row["status"] not in ("draft", "released"):
            raise HTTPException(409, "已发料或已完工的生产工单不可取消")
        db.execute("""UPDATE work_orders SET status = 'cancelled', cancelled_by = ?,
            cancelled_at = CURRENT_TIMESTAMP WHERE id = ?""", (user["id"], order_id))
        return work_order_data(db, order_id)
