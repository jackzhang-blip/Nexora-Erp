"""独立库存调整单：异人审批与仓库确认后才追加库存流水。"""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.access.security import require
from app.core.database import connection
from app.inventory.warehouse import balance, require_warehouse

router = APIRouter(prefix="/api/v1")


class AdjustmentLineInput(BaseModel):
    material_id: int = Field(gt=0)
    quantity: Decimal

    @field_validator("quantity")
    @classmethod
    def valid_quantity(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value == 0 or abs(value) > 1_000_000 or value.as_tuple().exponent < -3:
            raise ValueError("调整量不能为零，绝对值不超过一百万且最多三位小数")
        return value


class AdjustmentInput(BaseModel):
    warehouse_id: int = Field(gt=0)
    reason: str = Field(min_length=1, max_length=200)
    reference: str = Field(default="", max_length=100)
    lines: list[AdjustmentLineInput] = Field(min_length=1, max_length=100)

    @field_validator("reason")
    @classmethod
    def valid_reason(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("调整原因不能为空")
        return value.strip()


class ReasonInput(BaseModel):
    reason: str = Field(min_length=1, max_length=200)

    @field_validator("reason")
    @classmethod
    def valid_reason(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("原因不能为空")
        return value.strip()


def adjustment_data(db, adjustment_id: int) -> dict:
    row = db.execute("""SELECT a.*, w.name AS warehouse_name,
        creator.username AS created_by_name, reviewer.username AS reviewed_by_name,
        poster.username AS posted_by_name, rev.id AS reversal_id,
        rev.reason AS reversal_reason, rev.created_at AS reversed_at,
        rev.created_by AS reversed_by, reverser.username AS reversed_by_name
        FROM stock_adjustments a JOIN warehouses w ON w.id = a.warehouse_id
        JOIN users creator ON creator.id = a.created_by
        LEFT JOIN users reviewer ON reviewer.id = a.reviewed_by
        LEFT JOIN users poster ON poster.id = a.posted_by
        LEFT JOIN stock_adjustment_reversals rev ON rev.adjustment_id = a.id
        LEFT JOIN users reverser ON reverser.id = rev.created_by
        WHERE a.id = ?""", (adjustment_id,)).fetchone()
    if not row:
        raise HTTPException(404, "库存调整单不存在")
    lines = db.execute("""SELECT al.id, al.material_id, m.sku,
        m.name AS material_name, m.unit, al.quantity
        FROM stock_adjustment_lines al JOIN materials m ON m.id = al.material_id
        WHERE al.adjustment_id = ? ORDER BY al.id""", (adjustment_id,)).fetchall()
    return {**dict(row), "lines": [dict(line) for line in lines]}


@router.get("/stock-adjustments")
def list_adjustments(_: dict = Depends(require("adjustment.view"))) -> list[dict]:
    with connection() as db:
        ids = [row[0] for row in db.execute("SELECT id FROM stock_adjustments ORDER BY id DESC")]
        return [adjustment_data(db, item_id) for item_id in ids]


@router.post("/stock-adjustments", status_code=201)
def create_adjustment(payload: AdjustmentInput,
                      user: dict = Depends(require("adjustment.create"))) -> dict:
    if len({line.material_id for line in payload.lines}) != len(payload.lines):
        raise HTTPException(422, "一张调整单不能重复选择同一物料")
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        require_warehouse(db, payload.warehouse_id)
        for line in payload.lines:
            if not db.execute("SELECT 1 FROM materials WHERE id = ?", (line.material_id,)).fetchone():
                raise HTTPException(422, f"物料 #{line.material_id} 不存在")
        item_id = db.execute("""INSERT INTO stock_adjustments(warehouse_id, reason, reference, created_by)
            VALUES (?, ?, ?, ?)""", (payload.warehouse_id, payload.reason,
                                     payload.reference.strip(), user["id"])).lastrowid
        db.executemany("""INSERT INTO stock_adjustment_lines(adjustment_id, material_id, quantity)
            VALUES (?, ?, ?)""", [(item_id, line.material_id, str(line.quantity)) for line in payload.lines])
        return adjustment_data(db, item_id)


def transition(adjustment_id: int, current: str, target: str, actor: int,
               actor_column: str, time_column: str, reason: str | None = None) -> dict:
    # 列名只由服务端固定路由传入；单据状态用条件更新阻止重复处理。
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT status, created_by FROM stock_adjustments WHERE id = ?",
                         (adjustment_id,)).fetchone()
        if not row:
            raise HTTPException(404, "库存调整单不存在")
        if row["status"] != current:
            raise HTTPException(409, f"只能处理{current}状态的调整单")
        if target in ("approved", "rejected") and row["created_by"] == actor:
            raise HTTPException(409, "建单人不能审批自己的库存调整单")
        db.execute(f"""UPDATE stock_adjustments SET status = ?, {actor_column} = ?,
            {time_column} = CURRENT_TIMESTAMP, review_reason = COALESCE(?, review_reason)
            WHERE id = ?""", (target, actor, reason, adjustment_id))
        return adjustment_data(db, adjustment_id)


@router.post("/stock-adjustments/{adjustment_id}/submit")
def submit_adjustment(adjustment_id: int,
                      user: dict = Depends(require("adjustment.submit"))) -> dict:
    return transition(adjustment_id, "draft", "submitted", user["id"], "submitted_by", "submitted_at")


@router.post("/stock-adjustments/{adjustment_id}/approve")
def approve_adjustment(adjustment_id: int,
                       user: dict = Depends(require("adjustment.review"))) -> dict:
    return transition(adjustment_id, "submitted", "approved", user["id"], "reviewed_by", "reviewed_at")


@router.post("/stock-adjustments/{adjustment_id}/reject")
def reject_adjustment(adjustment_id: int, payload: ReasonInput,
                      user: dict = Depends(require("adjustment.review"))) -> dict:
    return transition(adjustment_id, "submitted", "rejected", user["id"],
                      "reviewed_by", "reviewed_at", payload.reason)


@router.post("/stock-adjustments/{adjustment_id}/cancel")
def cancel_adjustment(adjustment_id: int,
                      user: dict = Depends(require("adjustment.cancel"))) -> dict:
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT status FROM stock_adjustments WHERE id = ?", (adjustment_id,)).fetchone()
        if not row:
            raise HTTPException(404, "库存调整单不存在")
        if row["status"] not in ("draft", "submitted", "approved", "rejected"):
            raise HTTPException(409, "此调整单已处理")
        db.execute("""UPDATE stock_adjustments SET status = 'cancelled', cancelled_by = ?,
            cancelled_at = CURRENT_TIMESTAMP WHERE id = ?""", (user["id"], adjustment_id))
        return adjustment_data(db, adjustment_id)


@router.post("/stock-adjustments/{adjustment_id}/post")
def post_adjustment(adjustment_id: int,
                    user: dict = Depends(require("adjustment.post"))) -> dict:
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT status, warehouse_id FROM stock_adjustments WHERE id = ?",
                         (adjustment_id,)).fetchone()
        if not row:
            raise HTTPException(404, "库存调整单不存在")
        if row["status"] != "approved":
            raise HTTPException(409, "只有已审批调整单可确认")
        lines = db.execute("SELECT * FROM stock_adjustment_lines WHERE adjustment_id = ?",
                           (adjustment_id,)).fetchall()
        for line in lines:
            if balance(db, row["warehouse_id"], line["material_id"]) + Decimal(line["quantity"]) < 0:
                raise HTTPException(409, f"物料 #{line['material_id']} 库存不足")
        for line in lines:
            db.execute("""INSERT INTO stock_movements(warehouse_id, material_id, quantity,
                source_type, source_id, source_line_id, created_by)
                VALUES (?, ?, ?, 'adjustment', ?, ?, ?)""", (
                    row["warehouse_id"], line["material_id"], line["quantity"],
                    adjustment_id, line["id"], user["id"]))
        db.execute("""UPDATE stock_adjustments SET status = 'posted', posted_by = ?,
            posted_at = CURRENT_TIMESTAMP WHERE id = ?""", (user["id"], adjustment_id))
        return adjustment_data(db, adjustment_id)


@router.post("/stock-adjustments/{adjustment_id}/reverse", status_code=201)
def reverse_adjustment(adjustment_id: int, payload: ReasonInput,
                       user: dict = Depends(require("adjustment.reverse"))) -> dict:
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT status, warehouse_id FROM stock_adjustments WHERE id = ?",
                         (adjustment_id,)).fetchone()
        if not row:
            raise HTTPException(404, "库存调整单不存在")
        if row["status"] != "posted" or db.execute(
            "SELECT 1 FROM stock_adjustment_reversals WHERE adjustment_id = ?",
            (adjustment_id,)).fetchone():
            raise HTTPException(409, "只能冲销尚未冲销的已确认调整单")
        lines = db.execute("SELECT * FROM stock_adjustment_lines WHERE adjustment_id = ?",
                           (adjustment_id,)).fetchall()
        for line in lines:
            if balance(db, row["warehouse_id"], line["material_id"]) - Decimal(line["quantity"]) < 0:
                raise HTTPException(409, f"物料 #{line['material_id']} 库存不足，无法冲销")
        reversal_id = db.execute("""INSERT INTO stock_adjustment_reversals(adjustment_id, reason, created_by)
            VALUES (?, ?, ?)""", (adjustment_id, payload.reason, user["id"])).lastrowid
        for line in lines:
            db.execute("""INSERT INTO stock_movements(warehouse_id, material_id, quantity,
                source_type, source_id, source_line_id, created_by)
                VALUES (?, ?, ?, 'adjustment_reversal', ?, ?, ?)""", (
                    row["warehouse_id"], line["material_id"], str(-Decimal(line["quantity"])),
                    reversal_id, line["id"], user["id"]))
        return adjustment_data(db, adjustment_id)
