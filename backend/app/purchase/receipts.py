"""采购入库单及冲销接口。"""

import sqlite3
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.access.security import require
from app.core.database import connection
from app.inventory.warehouse import balance, require_warehouse
from app.purchase.orders import linked_order_for_receipt, order_receipt_lines, update_order_receipt_status, validate_receipt_post
from app.purchase.returns import returned_quantity as purchase_returned_quantity

router = APIRouter(prefix="/api/v1")


class ReceiptLineInput(BaseModel):
    material_id: int = Field(gt=0)
    quantity: Decimal

    @field_validator("quantity")
    @classmethod
    def valid_quantity(cls, value: Decimal) -> Decimal:
        # 用十进制字符串保存数量，避免浮点数改变库存精度。
        if not value.is_finite() or value <= 0 or value > 1_000_000 or value.as_tuple().exponent < -3:
            raise ValueError("数量须大于零、最多三位小数且不超过一百万")
        return value


class ReceiptInput(BaseModel):
    supplier_id: int = Field(gt=0)
    # 老客户端省略仓库时继续入主仓库；新客户端必须让用户明确选择。
    warehouse_id: int = Field(default=1, gt=0)
    purchase_order_id: int | None = Field(default=None, gt=0)
    reference: str = Field(default="", max_length=100)
    lines: list[ReceiptLineInput] = Field(min_length=1, max_length=100)


class ReceiptReverseInput(BaseModel):
    reason: str = Field(min_length=1, max_length=200)

    @field_validator("reason")
    @classmethod
    def trim_reason(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("冲销原因不能为空")
        return value.strip()


def receipt_data(db: sqlite3.Connection, receipt_id: int) -> dict:
    row = db.execute("""
        SELECT r.*, s.name AS supplier_name, u.username AS created_by_name,
               w.id AS warehouse_id, w.name AS warehouse_name,
               rev.id AS reversal_id, rev.reason AS reversal_reason,
               rev.created_by AS reversed_by, ru.username AS reversed_by_name,
               rev.created_at AS reversed_at
        FROM receipts r JOIN suppliers s ON s.id = r.supplier_id
        JOIN users u ON u.id = r.created_by
        JOIN receipt_warehouses rw ON rw.receipt_id = r.id
        JOIN warehouses w ON w.id = rw.warehouse_id
        LEFT JOIN receipt_reversals rev ON rev.receipt_id = r.id
        LEFT JOIN users ru ON ru.id = rev.created_by WHERE r.id = ?
    """, (receipt_id,)).fetchone()
    if not row:
        raise HTTPException(404, "入库单不存在")
    lines = db.execute("""
        SELECT rl.id, rl.material_id, m.sku, m.name AS material_name, m.unit, rl.quantity
        FROM receipt_lines rl JOIN materials m ON m.id = rl.material_id
        WHERE rl.receipt_id = ? ORDER BY rl.id
    """, (receipt_id,)).fetchall()
    detailed_lines = []
    for line in lines:
        # 同一次读取只汇总一次已退量，可退数量只由已确认单据推导。
        returned = purchase_returned_quantity(db, line["id"])
        detailed_lines.append({**dict(line), "returned_quantity": str(returned),
                               "returnable_quantity": str(Decimal(0) if row["reversal_id"] else
                                                          Decimal(line["quantity"]) - returned)})
    goods_receipt = db.execute("SELECT id FROM purchase_goods_receipts WHERE inbound_receipt_id = ?",
                               (receipt_id,)).fetchone()
    return {**dict(row), "purchase_order_id": linked_order_for_receipt(db, receipt_id),
            "goods_receipt_id": goods_receipt["id"] if goods_receipt else None,
            "lines": detailed_lines}

@router.get("/receipts")
def list_receipts(_: dict = Depends(require("inventory.view"))) -> list[dict]:
    with connection() as db:
        ids = [row[0] for row in db.execute("SELECT id FROM receipts ORDER BY id DESC")]
        return [receipt_data(db, receipt_id) for receipt_id in ids]


@router.post("/receipts", status_code=201)
def create_receipt(payload: ReceiptInput, user: dict = Depends(require("receipt.create"))) -> dict:
    if len({line.material_id for line in payload.lines}) != len(payload.lines):
        raise HTTPException(422, "一张入库单不能重复选择同一物料")
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        require_warehouse(db, payload.warehouse_id)
        if not db.execute("SELECT 1 FROM suppliers WHERE id = ?", (payload.supplier_id,)).fetchone():
            raise HTTPException(422, "供应商不存在")
        for line in payload.lines:
            if not db.execute("SELECT 1 FROM materials WHERE id = ?", (line.material_id,)).fetchone():
                raise HTTPException(422, "物料不存在")
        order_line_ids = (order_receipt_lines(db, payload.purchase_order_id, payload.supplier_id,
            [(line.material_id, line.quantity) for line in payload.lines])
            if payload.purchase_order_id is not None else {})
        cursor = db.execute("""
            INSERT INTO receipts(supplier_id, reference, created_by) VALUES (?, ?, ?)
        """, (payload.supplier_id, payload.reference.strip(), user["id"]))
        db.execute("INSERT INTO receipt_warehouses(receipt_id, warehouse_id) VALUES (?, ?)",
                   (cursor.lastrowid, payload.warehouse_id))
        for line in payload.lines:
            line_cursor = db.execute("""INSERT INTO receipt_lines(receipt_id, material_id, quantity)
                VALUES (?, ?, ?)""", (cursor.lastrowid, line.material_id, str(line.quantity)))
            if payload.purchase_order_id is not None:
                db.execute("INSERT INTO receipt_order_links(receipt_line_id, purchase_order_line_id) VALUES (?, ?)",
                           (line_cursor.lastrowid, order_line_ids[line.material_id]))
        return receipt_data(db, cursor.lastrowid)


@router.post("/receipts/{receipt_id}/post")
def post_receipt(receipt_id: int, user: dict = Depends(require("receipt.post"))) -> dict:
    with connection() as db:
        # 状态变更和库存流水写入使用同一个写事务，重复确认会返回冲突。
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT status, supplier_id FROM receipts WHERE id = ?", (receipt_id,)).fetchone()
        if not row:
            raise HTTPException(404, "入库单不存在")
        if row["status"] != "draft":
            raise HTTPException(409, "此入库单已经确认")
        order_id = validate_receipt_post(db, receipt_id, row["supplier_id"])
        db.execute("""
            INSERT INTO stock_movements(warehouse_id, material_id, quantity, source_type,
                                        source_id, source_line_id, created_by)
            SELECT rw.warehouse_id, rl.material_id, rl.quantity, 'receipt', ?, rl.id, ?
            FROM receipt_lines rl JOIN receipt_warehouses rw ON rw.receipt_id = rl.receipt_id
            WHERE rl.receipt_id = ?
        """, (receipt_id, user["id"], receipt_id))
        db.execute("""
            UPDATE receipts SET status = 'posted', posted_by = ?, posted_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (user["id"], receipt_id))
        if order_id is not None:
            update_order_receipt_status(db, order_id)
        return receipt_data(db, receipt_id)


@router.post("/receipts/{receipt_id}/reverse", status_code=201)
def reverse_receipt(receipt_id: int, payload: ReceiptReverseInput,
                    user: dict = Depends(require("receipt.reverse"))) -> dict:
    with connection() as db:
        # 写锁覆盖退货依赖、当前库存、冲销流水和订单进度，避免并发改变核对结果。
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("""SELECT r.status, rw.warehouse_id FROM receipts r
            JOIN receipt_warehouses rw ON rw.receipt_id = r.id WHERE r.id = ?""",
            (receipt_id,)).fetchone()
        if not row:
            raise HTTPException(404, "入库单不存在")
        if row["status"] != "posted":
            raise HTTPException(409, "只有已确认入库单可冲销")
        if db.execute("SELECT 1 FROM receipt_reversals WHERE receipt_id = ?",
                      (receipt_id,)).fetchone():
            raise HTTPException(409, "此入库单已冲销")
        lines = db.execute("SELECT id, material_id, quantity FROM receipt_lines WHERE receipt_id = ?",
                           (receipt_id,)).fetchall()
        for line in lines:
            if purchase_returned_quantity(db, line["id"]) > 0:
                raise HTTPException(409, "原入库单仍有已确认采购退货，请先冲销退货")
            if balance(db, row["warehouse_id"], line["material_id"]) < Decimal(line["quantity"]):
                raise HTTPException(409, f"原入库仓物料 #{line['material_id']} 库存不足，无法冲销")
        cursor = db.execute("""INSERT INTO receipt_reversals(receipt_id, reason, created_by)
            VALUES (?, ?, ?)""", (receipt_id, payload.reason, user["id"]))
        for line in lines:
            # 保留原正向入库流水，再用关联原明细的负向流水抵消误入库数量。
            db.execute("""INSERT INTO stock_movements(
                warehouse_id, material_id, quantity, source_type, source_id, source_line_id, created_by)
                VALUES (?, ?, ?, 'receipt_reversal', ?, ?, ?)""",
                (row["warehouse_id"], line["material_id"], str(-Decimal(line["quantity"])),
                 cursor.lastrowid, line["id"], user["id"]))
        order_id = linked_order_for_receipt(db, receipt_id)
        if order_id is not None:
            update_order_receipt_status(db, order_id)
        return receipt_data(db, receipt_id)
