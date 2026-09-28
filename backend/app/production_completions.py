"""生产报工经质检确认后，将合格成品入目标仓库。"""

import sqlite3
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from .database import connection
from .inventory import balance
from .security import require
from .work_orders import issued_quantity, posted_completion_totals, required_for_output

router = APIRouter(prefix="/api/v1")


class CompletionInput(BaseModel):
    work_order_id: int = Field(gt=0)
    reported_quantity: Decimal
    reference: str = Field(default="", max_length=100)

    @field_validator("reported_quantity")
    @classmethod
    def valid_quantity(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value <= 0 or value > 1_000_000 or value.as_tuple().exponent < -3:
            raise ValueError("报工数量须大于零、最多三位小数且不超过一百万")
        return value


class InspectionInput(BaseModel):
    accepted_quantity: Decimal
    qc_note: str = Field(min_length=1, max_length=200)

    @field_validator("accepted_quantity")
    @classmethod
    def valid_quantity(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value < 0 or value > 1_000_000 or value.as_tuple().exponent < -3:
            raise ValueError("合格数量须为非负数、最多三位小数且不超过一百万")
        return value

    @field_validator("qc_note")
    @classmethod
    def trim_note(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("质检说明不能为空")
        return value.strip()


class ReversalInput(BaseModel):
    reason: str = Field(min_length=1, max_length=200)

    @field_validator("reason")
    @classmethod
    def trim_reason(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("冲销原因不能为空")
        return value.strip()


def completion_data(db: sqlite3.Connection, completion_id: int) -> dict:
    row = db.execute("""SELECT pc.*, wo.warehouse_id, w.name AS warehouse_name,
        b.product_material_id, m.sku AS product_sku, m.name AS product_name, m.unit AS product_unit,
        creator.username AS created_by_name, inspector.username AS inspected_by_name,
        reversal.id AS reversal_id, reversal.reason AS reversal_reason,
        reversal.created_by AS reversed_by, reversal.created_at AS reversed_at,
        reverser.username AS reversed_by_name
        FROM production_completions pc JOIN work_orders wo ON wo.id = pc.work_order_id
        JOIN warehouses w ON w.id = wo.warehouse_id
        JOIN boms b ON b.id = wo.bom_id JOIN materials m ON m.id = b.product_material_id
        JOIN users creator ON creator.id = pc.created_by
        LEFT JOIN users inspector ON inspector.id = pc.inspected_by
        LEFT JOIN production_completion_reversals reversal ON reversal.production_completion_id = pc.id
        LEFT JOIN users reverser ON reverser.id = reversal.created_by
        WHERE pc.id = ?""", (completion_id,)).fetchone()
    if not row:
        raise HTTPException(404, "生产完工单不存在")
    result = dict(row)
    if result["reversal_id"] is not None:
        result["status"] = "reversed"
    return result


@router.get("/production-completions")
def list_completions(_: dict = Depends(require("production.view"))) -> list[dict]:
    with connection() as db:
        ids = [row[0] for row in db.execute("SELECT id FROM production_completions ORDER BY id DESC")]
        return [completion_data(db, completion_id) for completion_id in ids]


@router.post("/production-completions", status_code=201)
def create_completion(payload: CompletionInput,
                      user: dict = Depends(require("production_completion.create"))) -> dict:
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        order = db.execute("SELECT status, target_quantity FROM work_orders WHERE id = ?",
                           (payload.work_order_id,)).fetchone()
        if not order:
            raise HTTPException(422, "生产工单不存在")
        if order["status"] != "in_progress":
            raise HTTPException(409, "只有生产中的工单可以报工")
        posted, _, _ = posted_completion_totals(db, payload.work_order_id)
        if payload.reported_quantity > Decimal(order["target_quantity"]) - posted:
            raise HTTPException(409, "报工数量超出工单剩余目标产量")
        cursor = db.execute("""INSERT INTO production_completions(
            work_order_id, reported_quantity, reference, created_by) VALUES (?, ?, ?, ?)""",
            (payload.work_order_id, str(payload.reported_quantity), payload.reference.strip(), user["id"]))
        return completion_data(db, cursor.lastrowid)


@router.post("/production-completions/{completion_id}/inspect")
def inspect_completion(completion_id: int, payload: InspectionInput,
                       user: dict = Depends(require("production_completion.inspect"))) -> dict:
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("""SELECT pc.status, pc.reported_quantity, wo.status AS work_order_status
            FROM production_completions pc JOIN work_orders wo ON wo.id = pc.work_order_id
            WHERE pc.id = ?""", (completion_id,)).fetchone()
        if not row:
            raise HTTPException(404, "生产完工单不存在")
        if row["status"] != "draft":
            raise HTTPException(409, "只有报工草稿可以质检")
        if row["work_order_status"] != "in_progress":
            raise HTTPException(409, "生产工单当前不可质检")
        reported = Decimal(row["reported_quantity"])
        if payload.accepted_quantity > reported:
            raise HTTPException(422, "合格数量不能超过报工数量")
        rejected = reported - payload.accepted_quantity
        db.execute("""UPDATE production_completions SET status = 'inspected',
            accepted_quantity = ?, rejected_quantity = ?, qc_note = ?,
            inspected_by = ?, inspected_at = CURRENT_TIMESTAMP WHERE id = ?""",
            (str(payload.accepted_quantity), str(rejected), payload.qc_note, user["id"], completion_id))
        return completion_data(db, completion_id)


@router.post("/production-completions/{completion_id}/post")
def post_completion(completion_id: int,
                    user: dict = Depends(require("production_completion.post"))) -> dict:
    with connection() as db:
        # 同一写锁覆盖目标产量、净领料、合格品入库和工单状态，避免并行报工超量。
        db.execute("BEGIN IMMEDIATE")
        completion = db.execute("SELECT * FROM production_completions WHERE id = ?",
                                (completion_id,)).fetchone()
        if not completion:
            raise HTTPException(404, "生产完工单不存在")
        if completion["status"] != "inspected":
            raise HTTPException(409, "完工单须先质检且不能重复确认")
        order = db.execute("""SELECT wo.*, b.product_material_id FROM work_orders wo
            JOIN boms b ON b.id = wo.bom_id WHERE wo.id = ?""",
            (completion["work_order_id"],)).fetchone()
        if order["status"] != "in_progress":
            raise HTTPException(409, "生产工单当前不可完工入库")
        posted, _, _ = posted_completion_totals(db, order["id"])
        # 目标数按实际报工总数累计，质检不合格品也占用本工单的报工目标。
        total = posted + Decimal(completion["reported_quantity"])
        target = Decimal(order["target_quantity"])
        if total > target:
            raise HTTPException(409, "完工数量超出工单目标产量")
        for line in db.execute("""SELECT id, component_material_id, required_quantity
            FROM work_order_lines WHERE work_order_id = ?""", (order["id"],)):
            needed = required_for_output(Decimal(line["required_quantity"]), target, total)
            if issued_quantity(db, line["id"]) < needed:
                raise HTTPException(409, f"组件 #{line['component_material_id']} 领料不足，不能确认完工")
        accepted = Decimal(completion["accepted_quantity"])
        # 不合格品只留在质检记录中，不进入可用成品库存。
        if accepted > 0:
            db.execute("""INSERT INTO stock_movements(
                warehouse_id, material_id, quantity, source_type, source_id, source_line_id, created_by)
                VALUES (?, ?, ?, 'production_completion', ?, ?, ?)""",
                (order["warehouse_id"], order["product_material_id"], str(accepted),
                 completion_id, completion_id, user["id"]))
        db.execute("""UPDATE production_completions SET status = 'posted', posted_by = ?,
            posted_at = CURRENT_TIMESTAMP WHERE id = ?""", (user["id"], completion_id))
        if total == target:
            db.execute("""UPDATE work_orders SET status = 'completed', completed_by = ?,
                completed_at = CURRENT_TIMESTAMP WHERE id = ?""", (user["id"], order["id"]))
        return completion_data(db, completion_id)


@router.post("/production-completions/{completion_id}/cancel")
def cancel_completion(completion_id: int,
                      user: dict = Depends(require("production_completion.cancel"))) -> dict:
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT status FROM production_completions WHERE id = ?", (completion_id,)).fetchone()
        if not row:
            raise HTTPException(404, "生产完工单不存在")
        if row["status"] not in ("draft", "inspected"):
            raise HTTPException(409, "已确认完工单不可取消，须另行更正")
        db.execute("""UPDATE production_completions SET status = 'cancelled', cancelled_by = ?,
            cancelled_at = CURRENT_TIMESTAMP WHERE id = ?""", (user["id"], completion_id))
        return completion_data(db, completion_id)


@router.post("/production-completions/{completion_id}/reverse")
def reverse_completion(completion_id: int, payload: ReversalInput,
                       user: dict = Depends(require("production_completion.reverse"))) -> dict:
    with connection() as db:
        # 库存核对、冲销凭据、负向流水和工单状态在同一写事务内完成。
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("""SELECT pc.*, wo.warehouse_id, b.product_material_id,
            wo.status AS order_status FROM production_completions pc
            JOIN work_orders wo ON wo.id = pc.work_order_id JOIN boms b ON b.id = wo.bom_id
            WHERE pc.id = ?""", (completion_id,)).fetchone()
        if not row:
            raise HTTPException(404, "生产完工单不存在")
        if row["status"] != "posted":
            raise HTTPException(409, "只有已确认的完工单可以冲销")
        if db.execute("""SELECT 1 FROM production_completion_reversals
            WHERE production_completion_id = ?""", (completion_id,)).fetchone():
            raise HTTPException(409, "此完工单已冲销")
        accepted = Decimal(row["accepted_quantity"])
        if accepted > 0 and balance(db, row["warehouse_id"], row["product_material_id"]) < accepted:
            raise HTTPException(409, "目标仓库合格成品库存不足，无法冲销；请先处理后续出库或调拨")
        cursor = db.execute("""INSERT INTO production_completion_reversals(
            production_completion_id, reason, created_by) VALUES (?, ?, ?)""",
            (completion_id, payload.reason, user["id"]))
        if accepted > 0:
            # 以冲销单为来源新增反向流水，不修改原入库流水。
            db.execute("""INSERT INTO stock_movements(
                warehouse_id, material_id, quantity, source_type, source_id, source_line_id, created_by)
                VALUES (?, ?, ?, 'production_completion_reversal', ?, ?, ?)""",
                (row["warehouse_id"], row["product_material_id"], str(-accepted),
                 cursor.lastrowid, cursor.lastrowid, user["id"]))
        if row["order_status"] == "completed":
            db.execute("""UPDATE work_orders SET status = 'in_progress', completed_by = NULL,
                completed_at = NULL WHERE id = ?""", (row["work_order_id"],))
        return completion_data(db, completion_id)
