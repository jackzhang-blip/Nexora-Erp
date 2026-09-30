"""其他入库单：不产生采购应付的正向库存来源。"""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.access.security import require
from app.core.database import connection
from app.inventory.warehouse import balance, require_warehouse

router = APIRouter(prefix="/api/v1")


class InboundLineInput(BaseModel):
    material_id: int = Field(gt=0)
    quantity: Decimal

    @field_validator("quantity")
    @classmethod
    def valid_quantity(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value <= 0 or value > 1_000_000 or value.as_tuple().exponent < -3:
            raise ValueError("数量须大于零、最多三位小数且不超过一百万")
        return value


class InboundInput(BaseModel):
    warehouse_id: int = Field(gt=0)
    reason: str
    note: str = Field(min_length=1, max_length=200)
    reference: str = Field(default="", max_length=100)
    lines: list[InboundLineInput] = Field(min_length=1, max_length=100)

    @field_validator("reason")
    @classmethod
    def valid_reason(cls, value: str) -> str:
        if value not in ("opening", "gift", "other"):
            raise ValueError("入库用途无效")
        return value

    @field_validator("note")
    @classmethod
    def valid_note(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("入库说明不能为空")
        return value.strip()


class ReverseInput(BaseModel):
    reason: str = Field(min_length=1, max_length=200)

    @field_validator("reason")
    @classmethod
    def valid_reason(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("冲销原因不能为空")
        return value.strip()


def inbound_data(db, inbound_id: int) -> dict:
    row = db.execute("""SELECT wi.*, w.name AS warehouse_name,
        creator.username AS created_by_name, poster.username AS posted_by_name,
        rev.id AS reversal_id, rev.reason AS reversal_reason,
        rev.created_by AS reversed_by, ru.username AS reversed_by_name,
        rev.created_at AS reversed_at
        FROM warehouse_inbounds wi JOIN warehouses w ON w.id = wi.warehouse_id
        JOIN users creator ON creator.id = wi.created_by
        LEFT JOIN users poster ON poster.id = wi.posted_by
        LEFT JOIN warehouse_inbound_reversals rev ON rev.inbound_id = wi.id
        LEFT JOIN users ru ON ru.id = rev.created_by WHERE wi.id = ?""", (inbound_id,)).fetchone()
    if not row:
        raise HTTPException(404, "其他入库单不存在")
    lines = db.execute("""SELECT wil.id, wil.material_id, m.sku,
        m.name AS material_name, m.unit, wil.quantity FROM warehouse_inbound_lines wil
        JOIN materials m ON m.id = wil.material_id WHERE wil.inbound_id = ? ORDER BY wil.id""",
        (inbound_id,)).fetchall()
    return {**dict(row), "lines": [dict(line) for line in lines]}


@router.get("/warehouse-inbounds")
def list_inbounds(_: dict = Depends(require("other_inbound.view"))) -> list[dict]:
    with connection() as db:
        ids = [row[0] for row in db.execute("SELECT id FROM warehouse_inbounds ORDER BY id DESC")]
        return [inbound_data(db, item_id) for item_id in ids]


@router.post("/warehouse-inbounds", status_code=201)
def create_inbound(payload: InboundInput,
                   user: dict = Depends(require("other_inbound.create"))) -> dict:
    if len({line.material_id for line in payload.lines}) != len(payload.lines):
        raise HTTPException(422, "一张入库单不能重复选择同一物料")
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        require_warehouse(db, payload.warehouse_id)
        for line in payload.lines:
            if not db.execute("SELECT 1 FROM materials WHERE id = ?", (line.material_id,)).fetchone():
                raise HTTPException(422, f"物料 #{line.material_id} 不存在")
        inbound_id = db.execute("""INSERT INTO warehouse_inbounds(
            warehouse_id, reason, note, reference, created_by) VALUES (?, ?, ?, ?, ?)""",
            (payload.warehouse_id, payload.reason, payload.note, payload.reference.strip(), user["id"])).lastrowid
        db.executemany("""INSERT INTO warehouse_inbound_lines(inbound_id, material_id, quantity)
            VALUES (?, ?, ?)""", [(inbound_id, line.material_id, str(line.quantity)) for line in payload.lines])
        return inbound_data(db, inbound_id)


@router.post("/warehouse-inbounds/{inbound_id}/post")
def post_inbound(inbound_id: int,
                 user: dict = Depends(require("other_inbound.post"))) -> dict:
    with connection() as db:
        # 状态与所有正向流水同事务提交，失败时整单不改变库存。
        db.execute("BEGIN IMMEDIATE")
        source = db.execute("SELECT status, warehouse_id FROM warehouse_inbounds WHERE id = ?",
                            (inbound_id,)).fetchone()
        if not source:
            raise HTTPException(404, "其他入库单不存在")
        if source["status"] != "draft":
            raise HTTPException(409, "此入库单已处理")
        db.execute("""INSERT INTO stock_movements(
            warehouse_id, material_id, quantity, source_type, source_id, source_line_id, created_by)
            SELECT ?, material_id, quantity, 'other_inbound', ?, id, ?
            FROM warehouse_inbound_lines WHERE inbound_id = ?""",
            (source["warehouse_id"], inbound_id, user["id"], inbound_id))
        db.execute("""UPDATE warehouse_inbounds SET status = 'posted', posted_by = ?,
            posted_at = CURRENT_TIMESTAMP WHERE id = ?""", (user["id"], inbound_id))
        return inbound_data(db, inbound_id)


@router.post("/warehouse-inbounds/{inbound_id}/cancel")
def cancel_inbound(inbound_id: int,
                   user: dict = Depends(require("other_inbound.cancel"))) -> dict:
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        cursor = db.execute("""UPDATE warehouse_inbounds SET status = 'cancelled',
            cancelled_by = ?, cancelled_at = CURRENT_TIMESTAMP WHERE id = ? AND status = 'draft'""",
            (user["id"], inbound_id))
        if not cursor.rowcount:
            if not db.execute("SELECT 1 FROM warehouse_inbounds WHERE id = ?", (inbound_id,)).fetchone():
                raise HTTPException(404, "其他入库单不存在")
            raise HTTPException(409, "只能取消其他入库草稿")
        return inbound_data(db, inbound_id)


@router.post("/warehouse-inbounds/{inbound_id}/reverse", status_code=201)
def reverse_inbound(inbound_id: int, payload: ReverseInput,
                    user: dict = Depends(require("other_inbound.reverse"))) -> dict:
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        source = db.execute("SELECT status, warehouse_id FROM warehouse_inbounds WHERE id = ?",
                            (inbound_id,)).fetchone()
        if not source:
            raise HTTPException(404, "其他入库单不存在")
        if source["status"] != "posted" or db.execute(
            "SELECT 1 FROM warehouse_inbound_reversals WHERE inbound_id = ?", (inbound_id,)).fetchone():
            raise HTTPException(409, "只能冲销尚未冲销的已确认其他入库")
        lines = db.execute("SELECT id, material_id, quantity FROM warehouse_inbound_lines WHERE inbound_id = ?",
                           (inbound_id,)).fetchall()
        for line in lines:
            if balance(db, source["warehouse_id"], line["material_id"]) < Decimal(line["quantity"]):
                raise HTTPException(409, f"物料 #{line['material_id']} 当前库存不足，不能冲销原入库")
        reversal_id = db.execute("""INSERT INTO warehouse_inbound_reversals(inbound_id, reason, created_by)
            VALUES (?, ?, ?)""", (inbound_id, payload.reason, user["id"])).lastrowid
        for line in lines:
            db.execute("""INSERT INTO stock_movements(
                warehouse_id, material_id, quantity, source_type, source_id, source_line_id, created_by)
                VALUES (?, ?, ?, 'other_inbound_reversal', ?, ?, ?)""",
                (source["warehouse_id"], line["material_id"], str(-Decimal(line["quantity"])),
                 reversal_id, line["id"], user["id"]))
        return inbound_data(db, inbound_id)
