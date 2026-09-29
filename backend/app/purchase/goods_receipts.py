"""采购收货事实与待入库单的单向生成。"""

import sqlite3
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator

from app.access.security import require
from app.core.database import connection
from app.inventory.warehouse import require_warehouse
from app.purchase.orders import received_quantity

router = APIRouter(prefix="/api/v1")


class GoodsReceiptLineInput(BaseModel):
    purchase_order_line_id: int = Field(gt=0)
    accepted_quantity: Decimal = Decimal(0)
    rejected_quantity: Decimal = Decimal(0)
    rejection_reason: str = Field(default="", max_length=200)

    @field_validator("accepted_quantity", "rejected_quantity")
    @classmethod
    def valid_quantity(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value < 0 or value > 1_000_000 or value.as_tuple().exponent < -3:
            raise ValueError("收货数量须非负、最多三位小数且不超过一百万")
        return value

    @model_validator(mode="after")
    def valid_result(self):
        if self.accepted_quantity + self.rejected_quantity <= 0:
            raise ValueError("每条收货明细须有合格或拒收数量")
        if self.rejected_quantity > 0 and not self.rejection_reason.strip():
            raise ValueError("拒收数量大于零时须填写原因")
        self.rejection_reason = self.rejection_reason.strip()
        return self


class GoodsReceiptInput(BaseModel):
    purchase_order_id: int = Field(gt=0)
    warehouse_id: int = Field(gt=0)
    reference: str = Field(default="", max_length=100)
    lines: list[GoodsReceiptLineInput] = Field(min_length=1, max_length=100)


def pending_accepted_quantity(db: sqlite3.Connection, order_line_id: int) -> Decimal:
    # 已确认收货生成的待入库单先占用收货额度，避免两个仓库员同时生成超量入库草稿。
    return sum((Decimal(row[0]) for row in db.execute("""
        SELECT grl.accepted_quantity FROM purchase_goods_receipt_lines grl
        JOIN purchase_goods_receipts gr ON gr.id = grl.goods_receipt_id
        JOIN receipts r ON r.id = gr.inbound_receipt_id
        WHERE grl.purchase_order_line_id = ? AND gr.status = 'confirmed' AND r.status = 'draft'
    """, (order_line_id,))), Decimal(0))


def checked_lines(db: sqlite3.Connection, payload: GoodsReceiptInput) -> tuple[sqlite3.Row, dict[int, sqlite3.Row]]:
    if len({line.purchase_order_line_id for line in payload.lines}) != len(payload.lines):
        raise HTTPException(422, "一张收货单不能重复选择同一订单明细")
    order = db.execute("SELECT supplier_id, status FROM purchase_orders WHERE id = ?",
                       (payload.purchase_order_id,)).fetchone()
    if not order:
        raise HTTPException(422, "采购订单不存在")
    if order["status"] not in ("confirmed", "partially_received"):
        raise HTTPException(409, "采购订单当前不可收货")
    known = {row["id"]: row for row in db.execute("""SELECT id, material_id, quantity
        FROM purchase_order_lines WHERE purchase_order_id = ?""", (payload.purchase_order_id,))}
    for line in payload.lines:
        source = known.get(line.purchase_order_line_id)
        if not source:
            raise HTTPException(422, "收货明细不属于此采购订单")
        remaining = Decimal(source["quantity"]) - received_quantity(db, source["id"]) - pending_accepted_quantity(db, source["id"])
        if line.accepted_quantity + line.rejected_quantity > remaining:
            raise HTTPException(409, f"订单明细 #{source['id']} 超过待收数量")
    return order, known


def goods_receipt_data(db: sqlite3.Connection, goods_receipt_id: int) -> dict:
    row = db.execute("""SELECT gr.*, po.supplier_id, s.name AS supplier_name,
        w.name AS warehouse_name, creator.username AS created_by_name,
        confirmer.username AS confirmed_by_name, r.status AS inbound_status,
        rev.id AS inbound_reversal_id
        FROM purchase_goods_receipts gr
        JOIN purchase_orders po ON po.id = gr.purchase_order_id
        JOIN suppliers s ON s.id = po.supplier_id
        JOIN warehouses w ON w.id = gr.warehouse_id
        JOIN users creator ON creator.id = gr.created_by
        LEFT JOIN users confirmer ON confirmer.id = gr.confirmed_by
        LEFT JOIN receipts r ON r.id = gr.inbound_receipt_id
        LEFT JOIN receipt_reversals rev ON rev.receipt_id = r.id
        WHERE gr.id = ?""", (goods_receipt_id,)).fetchone()
    if not row:
        raise HTTPException(404, "采购收货单不存在")
    lines = db.execute("""SELECT grl.*, pol.material_id, m.sku,
        m.name AS material_name, m.unit FROM purchase_goods_receipt_lines grl
        JOIN purchase_order_lines pol ON pol.id = grl.purchase_order_line_id
        JOIN materials m ON m.id = pol.material_id
        WHERE grl.goods_receipt_id = ? ORDER BY grl.id""", (goods_receipt_id,)).fetchall()
    return {**dict(row), "lines": [dict(line) for line in lines]}


@router.get("/purchase-goods-receipts")
def list_goods_receipts(_: dict = Depends(require("purchase_receiving.view"))) -> list[dict]:
    with connection() as db:
        ids = [row[0] for row in db.execute("SELECT id FROM purchase_goods_receipts ORDER BY id DESC")]
        return [goods_receipt_data(db, item_id) for item_id in ids]


@router.post("/purchase-goods-receipts", status_code=201)
def create_goods_receipt(payload: GoodsReceiptInput,
                         user: dict = Depends(require("purchase_receiving.create"))) -> dict:
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        require_warehouse(db, payload.warehouse_id)
        checked_lines(db, payload)
        cursor = db.execute("""INSERT INTO purchase_goods_receipts(
            purchase_order_id, warehouse_id, reference, created_by) VALUES (?, ?, ?, ?)""",
            (payload.purchase_order_id, payload.warehouse_id, payload.reference.strip(), user["id"]))
        db.executemany("""INSERT INTO purchase_goods_receipt_lines(
            goods_receipt_id, purchase_order_line_id, accepted_quantity, rejected_quantity, rejection_reason)
            VALUES (?, ?, ?, ?, ?)""",
            [(cursor.lastrowid, line.purchase_order_line_id, str(line.accepted_quantity),
              str(line.rejected_quantity), line.rejection_reason) for line in payload.lines])
        return goods_receipt_data(db, cursor.lastrowid)


@router.post("/purchase-goods-receipts/{goods_receipt_id}/confirm")
def confirm_goods_receipt(goods_receipt_id: int,
                          user: dict = Depends(require("purchase_receiving.confirm"))) -> dict:
    with connection() as db:
        # 收货校验、待入库单生成和状态转换在同一写事务内完成，重试不能产生第二张入库单。
        db.execute("BEGIN IMMEDIATE")
        source = db.execute("SELECT * FROM purchase_goods_receipts WHERE id = ?",
                            (goods_receipt_id,)).fetchone()
        if not source:
            raise HTTPException(404, "采购收货单不存在")
        if source["status"] != "draft":
            raise HTTPException(409, "此采购收货单已处理")
        lines = db.execute("SELECT * FROM purchase_goods_receipt_lines WHERE goods_receipt_id = ?",
                           (goods_receipt_id,)).fetchall()
        payload = GoodsReceiptInput(purchase_order_id=source["purchase_order_id"],
                                    warehouse_id=source["warehouse_id"], reference=source["reference"],
                                    lines=[GoodsReceiptLineInput(**dict(line)) for line in lines])
        order, known = checked_lines(db, payload)
        accepted = [line for line in lines if Decimal(line["accepted_quantity"]) > 0]
        inbound_id = None
        if accepted:
            inbound_id = db.execute("""INSERT INTO receipts(supplier_id, reference, created_by)
                VALUES (?, ?, ?)""", (order["supplier_id"], source["reference"], user["id"])).lastrowid
            db.execute("INSERT INTO receipt_warehouses(receipt_id, warehouse_id) VALUES (?, ?)",
                       (inbound_id, source["warehouse_id"]))
            for line in accepted:
                receipt_line_id = db.execute("""INSERT INTO receipt_lines(receipt_id, material_id, quantity)
                    VALUES (?, ?, ?)""", (inbound_id, known[line["purchase_order_line_id"]]["material_id"],
                                           line["accepted_quantity"])).lastrowid
                db.execute("""INSERT INTO receipt_order_links(receipt_line_id, purchase_order_line_id)
                    VALUES (?, ?)""", (receipt_line_id, line["purchase_order_line_id"]))
        db.execute("""UPDATE purchase_goods_receipts SET status = 'confirmed', confirmed_by = ?,
            confirmed_at = CURRENT_TIMESTAMP, inbound_receipt_id = ? WHERE id = ?""",
            (user["id"], inbound_id, goods_receipt_id))
        return goods_receipt_data(db, goods_receipt_id)


@router.post("/purchase-goods-receipts/{goods_receipt_id}/cancel")
def cancel_goods_receipt(goods_receipt_id: int,
                         user: dict = Depends(require("purchase_receiving.cancel"))) -> dict:
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        cursor = db.execute("""UPDATE purchase_goods_receipts SET status = 'cancelled',
            cancelled_by = ?, cancelled_at = CURRENT_TIMESTAMP WHERE id = ? AND status = 'draft'""",
            (user["id"], goods_receipt_id))
        if not cursor.rowcount:
            if not db.execute("SELECT 1 FROM purchase_goods_receipts WHERE id = ?", (goods_receipt_id,)).fetchone():
                raise HTTPException(404, "采购收货单不存在")
            raise HTTPException(409, "只能取消采购收货草稿")
        return goods_receipt_data(db, goods_receipt_id)
