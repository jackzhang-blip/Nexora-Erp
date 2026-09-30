"""仓库其他出库单；库存减少只发生在确认事务中。"""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.access.security import require
from app.core.database import connection
from app.inventory.warehouse import balance, require_warehouse

router = APIRouter(prefix="/api/v1")


class OutboundLineInput(BaseModel):
    material_id: int = Field(gt=0)
    quantity: Decimal

    @field_validator("quantity")
    @classmethod
    def valid_quantity(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value <= 0 or value > 1_000_000 or value.as_tuple().exponent < -3:
            raise ValueError("数量须大于零、最多三位小数且不超过一百万")
        return value


class OutboundInput(BaseModel):
    warehouse_id: int = Field(gt=0)
    reason: str
    note: str = Field(min_length=1, max_length=200)
    reference: str = Field(default="", max_length=100)
    lines: list[OutboundLineInput] = Field(min_length=1, max_length=100)

    @field_validator("reason")
    @classmethod
    def valid_reason(cls, value: str) -> str:
        if value not in ("scrap", "sample", "other"):
            raise ValueError("出库用途无效")
        return value

    @field_validator("note")
    @classmethod
    def valid_note(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("出库说明不能为空")
        return value.strip()


class ReverseInput(BaseModel):
    reason: str = Field(min_length=1, max_length=200)

    @field_validator("reason")
    @classmethod
    def valid_reason(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("冲销原因不能为空")
        return value.strip()


def outbound_data(db, outbound_id: int) -> dict:
    row = db.execute("""SELECT wo.*, w.name AS warehouse_name,
        creator.username AS created_by_name, poster.username AS posted_by_name,
        rev.id AS reversal_id, rev.reason AS reversal_reason,
        rev.created_by AS reversed_by, ru.username AS reversed_by_name,
        rev.created_at AS reversed_at
        FROM warehouse_outbounds wo JOIN warehouses w ON w.id = wo.warehouse_id
        JOIN users creator ON creator.id = wo.created_by
        LEFT JOIN users poster ON poster.id = wo.posted_by
        LEFT JOIN warehouse_outbound_reversals rev ON rev.outbound_id = wo.id
        LEFT JOIN users ru ON ru.id = rev.created_by WHERE wo.id = ?""", (outbound_id,)).fetchone()
    if not row:
        raise HTTPException(404, "仓库出库单不存在")
    lines = db.execute("""SELECT wol.id, wol.material_id, m.sku,
        m.name AS material_name, m.unit, wol.quantity FROM warehouse_outbound_lines wol
        JOIN materials m ON m.id = wol.material_id WHERE wol.outbound_id = ? ORDER BY wol.id""",
        (outbound_id,)).fetchall()
    return {**dict(row), "lines": [dict(line) for line in lines]}


@router.get("/warehouse-outbounds")
def list_outbounds(_: dict = Depends(require("other_outbound.view"))) -> list[dict]:
    with connection() as db:
        ids = [row[0] for row in db.execute("SELECT id FROM warehouse_outbounds ORDER BY id DESC")]
        return [outbound_data(db, item_id) for item_id in ids]


@router.post("/warehouse-outbounds", status_code=201)
def create_outbound(payload: OutboundInput,
                    user: dict = Depends(require("other_outbound.create"))) -> dict:
    if len({line.material_id for line in payload.lines}) != len(payload.lines):
        raise HTTPException(422, "一张出库单不能重复选择同一物料")
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        require_warehouse(db, payload.warehouse_id)
        for line in payload.lines:
            if not db.execute("SELECT 1 FROM materials WHERE id = ?", (line.material_id,)).fetchone():
                raise HTTPException(422, f"物料 #{line.material_id} 不存在")
        outbound_id = db.execute("""INSERT INTO warehouse_outbounds(
            warehouse_id, reason, note, reference, created_by) VALUES (?, ?, ?, ?, ?)""",
            (payload.warehouse_id, payload.reason, payload.note, payload.reference.strip(), user["id"])).lastrowid
        db.executemany("""INSERT INTO warehouse_outbound_lines(outbound_id, material_id, quantity)
            VALUES (?, ?, ?)""", [(outbound_id, line.material_id, str(line.quantity)) for line in payload.lines])
        return outbound_data(db, outbound_id)


@router.post("/warehouse-outbounds/{outbound_id}/post")
def post_outbound(outbound_id: int,
                  user: dict = Depends(require("other_outbound.post"))) -> dict:
    with connection() as db:
        # 写锁覆盖各行库存检查与扣减，整单要么确认要么完全不动库存。
        db.execute("BEGIN IMMEDIATE")
        source = db.execute("SELECT status, warehouse_id, source_kind FROM warehouse_outbounds WHERE id = ?",
                            (outbound_id,)).fetchone()
        if not source:
            raise HTTPException(404, "仓库出库单不存在")
        if source["status"] != "draft" or source["source_kind"] != "other":
            raise HTTPException(409, "此出库单不能按其他出库确认")
        lines = db.execute("SELECT id, material_id, quantity FROM warehouse_outbound_lines WHERE outbound_id = ?",
                           (outbound_id,)).fetchall()
        for line in lines:
            if balance(db, source["warehouse_id"], line["material_id"]) < Decimal(line["quantity"]):
                raise HTTPException(409, f"物料 #{line['material_id']} 在来源仓库库存不足")
        for line in lines:
            db.execute("""INSERT INTO stock_movements(
                warehouse_id, material_id, quantity, source_type, source_id, source_line_id, created_by)
                VALUES (?, ?, ?, 'other_outbound', ?, ?, ?)""",
                (source["warehouse_id"], line["material_id"], str(-Decimal(line["quantity"])),
                 outbound_id, line["id"], user["id"]))
        db.execute("""UPDATE warehouse_outbounds SET status = 'posted', posted_by = ?,
            posted_at = CURRENT_TIMESTAMP WHERE id = ?""", (user["id"], outbound_id))
        return outbound_data(db, outbound_id)


@router.post("/warehouse-outbounds/{outbound_id}/cancel")
def cancel_outbound(outbound_id: int,
                    user: dict = Depends(require("other_outbound.cancel"))) -> dict:
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        cursor = db.execute("""UPDATE warehouse_outbounds SET status = 'cancelled',
            cancelled_by = ?, cancelled_at = CURRENT_TIMESTAMP
            WHERE id = ? AND status = 'draft' AND source_kind = 'other'""",
            (user["id"], outbound_id))
        if not cursor.rowcount:
            if not db.execute("SELECT 1 FROM warehouse_outbounds WHERE id = ?", (outbound_id,)).fetchone():
                raise HTTPException(404, "仓库出库单不存在")
            raise HTTPException(409, "只能取消其他出库草稿")
        return outbound_data(db, outbound_id)


@router.post("/warehouse-outbounds/{outbound_id}/reverse", status_code=201)
def reverse_outbound(outbound_id: int, payload: ReverseInput,
                     user: dict = Depends(require("other_outbound.reverse"))) -> dict:
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        source = db.execute("SELECT status, warehouse_id, source_kind FROM warehouse_outbounds WHERE id = ?",
                            (outbound_id,)).fetchone()
        if not source:
            raise HTTPException(404, "仓库出库单不存在")
        if source["status"] != "posted" or source["source_kind"] != "other" or db.execute(
            "SELECT 1 FROM warehouse_outbound_reversals WHERE outbound_id = ?", (outbound_id,)).fetchone():
            raise HTTPException(409, "只能冲销尚未冲销的已确认其他出库")
        reversal_id = db.execute("""INSERT INTO warehouse_outbound_reversals(outbound_id, reason, created_by)
            VALUES (?, ?, ?)""", (outbound_id, payload.reason, user["id"])).lastrowid
        for line in db.execute("SELECT id, material_id, quantity FROM warehouse_outbound_lines WHERE outbound_id = ?",
                               (outbound_id,)):
            db.execute("""INSERT INTO stock_movements(
                warehouse_id, material_id, quantity, source_type, source_id, source_line_id, created_by)
                VALUES (?, ?, ?, 'other_outbound_reversal', ?, ?, ?)""",
                (source["warehouse_id"], line["material_id"], line["quantity"],
                 reversal_id, line["id"], user["id"]))
        return outbound_data(db, outbound_id)
