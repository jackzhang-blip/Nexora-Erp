"""采购申请审批与分批转单数量查询。"""

import sqlite3
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.access.security import require
from app.core.database import connection

router = APIRouter(prefix="/api/v1")


class RequestLineInput(BaseModel):
    material_id: int = Field(gt=0)
    quantity: Decimal

    @field_validator("quantity")
    @classmethod
    def valid_quantity(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value <= 0 or value > 1_000_000 or value.as_tuple().exponent < -3:
            raise ValueError("数量须大于零、最多三位小数且不超过一百万")
        return value


class PurchaseRequestInput(BaseModel):
    reference: str = Field(default="", max_length=100)
    note: str = Field(default="", max_length=500)
    lines: list[RequestLineInput] = Field(min_length=1, max_length=100)


class ReviewReasonInput(BaseModel):
    reason: str = Field(min_length=1, max_length=200)

    @field_validator("reason")
    @classmethod
    def valid_reason(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("驳回原因不能为空")
        return value.strip()


def ordered_quantity(db: sqlite3.Connection, request_line_id: int) -> Decimal:
    # 草稿订单也占用申请额度，取消后才释放，避免并发转单超量。
    return sum((Decimal(row[0]) for row in db.execute("""
        SELECT pol.quantity FROM purchase_order_request_links link
        JOIN purchase_order_lines pol ON pol.id = link.purchase_order_line_id
        JOIN purchase_orders po ON po.id = pol.purchase_order_id
        WHERE link.purchase_request_line_id = ? AND po.status != 'cancelled'
    """, (request_line_id,))), Decimal(0))


def request_data(db: sqlite3.Connection, request_id: int) -> dict:
    row = db.execute("""SELECT pr.*, creator.username AS created_by_name,
        reviewer.username AS reviewed_by_name FROM purchase_requests pr
        JOIN users creator ON creator.id = pr.created_by
        LEFT JOIN users reviewer ON reviewer.id = pr.reviewed_by
        WHERE pr.id = ?""", (request_id,)).fetchone()
    if not row:
        raise HTTPException(404, "采购申请不存在")
    lines = []
    for item in db.execute("""SELECT prl.id, prl.material_id, m.sku,
        m.name AS material_name, m.unit, prl.quantity
        FROM purchase_request_lines prl JOIN materials m ON m.id = prl.material_id
        WHERE prl.purchase_request_id = ? ORDER BY prl.id""", (request_id,)):
        ordered = ordered_quantity(db, item["id"])
        lines.append({**dict(item), "ordered_quantity": str(ordered),
                      "remaining_quantity": str(Decimal(item["quantity"]) - ordered)})
    return {**dict(row), "lines": lines}


def validate_lines(db: sqlite3.Connection, payload: PurchaseRequestInput) -> None:
    if len({line.material_id for line in payload.lines}) != len(payload.lines):
        raise HTTPException(422, "一张申请不能重复选择同一物料")
    for line in payload.lines:
        if not db.execute("SELECT 1 FROM materials WHERE id = ?", (line.material_id,)).fetchone():
            raise HTTPException(422, f"物料 #{line.material_id} 不存在")


@router.get("/purchase-requests")
def list_purchase_requests(_: dict = Depends(require("purchase_request.view"))) -> list[dict]:
    with connection() as db:
        ids = [row[0] for row in db.execute("SELECT id FROM purchase_requests ORDER BY id DESC")]
        return [request_data(db, request_id) for request_id in ids]


@router.post("/purchase-requests", status_code=201)
def create_purchase_request(payload: PurchaseRequestInput,
                            user: dict = Depends(require("purchase_request.create"))) -> dict:
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        validate_lines(db, payload)
        cursor = db.execute("""INSERT INTO purchase_requests(reference, note, created_by)
            VALUES (?, ?, ?)""", (payload.reference.strip(), payload.note.strip(), user["id"]))
        db.executemany("""INSERT INTO purchase_request_lines(
            purchase_request_id, material_id, quantity) VALUES (?, ?, ?)""",
            [(cursor.lastrowid, line.material_id, str(line.quantity)) for line in payload.lines])
        return request_data(db, cursor.lastrowid)


@router.put("/purchase-requests/{request_id}")
def update_purchase_request(request_id: int, payload: PurchaseRequestInput,
                            _: dict = Depends(require("purchase_request.create"))) -> dict:
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT status FROM purchase_requests WHERE id = ?", (request_id,)).fetchone()
        if not row:
            raise HTTPException(404, "采购申请不存在")
        if row["status"] not in ("draft", "rejected"):
            raise HTTPException(409, "只能修改草稿或已驳回的申请")
        validate_lines(db, payload)
        db.execute("DELETE FROM purchase_request_lines WHERE purchase_request_id = ?", (request_id,))
        db.executemany("""INSERT INTO purchase_request_lines(
            purchase_request_id, material_id, quantity) VALUES (?, ?, ?)""",
            [(request_id, line.material_id, str(line.quantity)) for line in payload.lines])
        db.execute("""UPDATE purchase_requests SET reference = ?, note = ?, status = 'draft',
            submitted_by = NULL, submitted_at = NULL, reviewed_by = NULL,
            reviewed_at = NULL, review_reason = '' WHERE id = ?""",
            (payload.reference.strip(), payload.note.strip(), request_id))
        return request_data(db, request_id)


@router.post("/purchase-requests/{request_id}/submit")
def submit_purchase_request(request_id: int,
                            user: dict = Depends(require("purchase_request.submit"))) -> dict:
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        cursor = db.execute("""UPDATE purchase_requests SET status = 'submitted',
            submitted_by = ?, submitted_at = CURRENT_TIMESTAMP
            WHERE id = ? AND status = 'draft'""", (user["id"], request_id))
        if not cursor.rowcount:
            if not db.execute("SELECT 1 FROM purchase_requests WHERE id = ?", (request_id,)).fetchone():
                raise HTTPException(404, "采购申请不存在")
            raise HTTPException(409, "只能提交草稿采购申请")
        return request_data(db, request_id)


@router.post("/purchase-requests/{request_id}/approve")
def approve_purchase_request(request_id: int,
                             user: dict = Depends(require("purchase_request.review"))) -> dict:
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        cursor = db.execute("""UPDATE purchase_requests SET status = 'approved',
            reviewed_by = ?, reviewed_at = CURRENT_TIMESTAMP, review_reason = ''
            WHERE id = ? AND status = 'submitted'""", (user["id"], request_id))
        if not cursor.rowcount:
            if not db.execute("SELECT 1 FROM purchase_requests WHERE id = ?", (request_id,)).fetchone():
                raise HTTPException(404, "采购申请不存在")
            raise HTTPException(409, "只能批准已提交的采购申请")
        return request_data(db, request_id)


@router.post("/purchase-requests/{request_id}/reject")
def reject_purchase_request(request_id: int, payload: ReviewReasonInput,
                            user: dict = Depends(require("purchase_request.review"))) -> dict:
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        cursor = db.execute("""UPDATE purchase_requests SET status = 'rejected',
            reviewed_by = ?, reviewed_at = CURRENT_TIMESTAMP, review_reason = ?
            WHERE id = ? AND status = 'submitted'""",
            (user["id"], payload.reason, request_id))
        if not cursor.rowcount:
            if not db.execute("SELECT 1 FROM purchase_requests WHERE id = ?", (request_id,)).fetchone():
                raise HTTPException(404, "采购申请不存在")
            raise HTTPException(409, "只能驳回已提交的采购申请")
        return request_data(db, request_id)


@router.post("/purchase-requests/{request_id}/cancel")
def cancel_purchase_request(request_id: int,
                            user: dict = Depends(require("purchase_request.cancel"))) -> dict:
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT status FROM purchase_requests WHERE id = ?", (request_id,)).fetchone()
        if not row:
            raise HTTPException(404, "采购申请不存在")
        if row["status"] == "cancelled":
            raise HTTPException(409, "采购申请已取消")
        if db.execute("""SELECT 1 FROM purchase_order_request_links link
            JOIN purchase_order_lines pol ON pol.id = link.purchase_order_line_id
            JOIN purchase_orders po ON po.id = pol.purchase_order_id
            JOIN purchase_request_lines prl ON prl.id = link.purchase_request_line_id
            WHERE prl.purchase_request_id = ? AND po.status != 'cancelled' LIMIT 1""",
            (request_id,)).fetchone():
            raise HTTPException(409, "申请已被有效采购订单使用，不能取消")
        db.execute("""UPDATE purchase_requests SET status = 'cancelled',
            cancelled_by = ?, cancelled_at = CURRENT_TIMESTAMP WHERE id = ?""",
            (user["id"], request_id))
        return request_data(db, request_id)
