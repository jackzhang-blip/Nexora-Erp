"""采购订单及入库关联；订单数量只由已确认入库单消耗。"""

import sqlite3
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from .database import connection
from .purchase_returns import returned_quantity as purchase_returned_quantity
from .security import require

router = APIRouter(prefix="/api/v1")


class PurchaseOrderLineInput(BaseModel):
    material_id: int = Field(gt=0)
    quantity: Decimal
    unit_price: Decimal

    @field_validator("quantity")
    @classmethod
    def valid_quantity(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value <= 0 or value > 1_000_000 or value.as_tuple().exponent < -3:
            raise ValueError("数量须大于零、最多三位小数且不超过一百万")
        return value

    @field_validator("unit_price")
    @classmethod
    def valid_unit_price(cls, value: Decimal) -> Decimal:
        # 单价保留四位小数，金额展示按人民币分四舍五入。
        if not value.is_finite() or value < 0 or value > 1_000_000_000 or value.as_tuple().exponent < -4:
            raise ValueError("单价须非负、最多四位小数且不超过十亿")
        return value


class PurchaseOrderInput(BaseModel):
    supplier_id: int = Field(gt=0)
    reference: str = Field(default="", max_length=100)
    lines: list[PurchaseOrderLineInput] = Field(min_length=1, max_length=100)


def received_quantity(db: sqlite3.Connection, order_line_id: int) -> Decimal:
    # 只计算已确认入库，草稿不能预占订单数量；不用 SQLite SUM 避免浮点尾差。
    return sum((Decimal(row[0]) for row in db.execute("""
        SELECT rl.quantity FROM receipt_order_links link
        JOIN receipt_lines rl ON rl.id = link.receipt_line_id
        JOIN receipts r ON r.id = rl.receipt_id
        LEFT JOIN receipt_reversals rev ON rev.receipt_id = r.id
        WHERE link.purchase_order_line_id = ? AND r.status = 'posted' AND rev.id IS NULL
    """, (order_line_id,))), Decimal(0))


def returned_quantity(db: sqlite3.Connection, order_line_id: int) -> Decimal:
    # 原订单的已入库量保持毛额；退供应商数量另外展示，避免历史状态漂移。
    return sum((purchase_returned_quantity(db, row[0]) for row in db.execute("""
        SELECT link.receipt_line_id FROM receipt_order_links link
        WHERE link.purchase_order_line_id = ?""", (order_line_id,))), Decimal(0))


def order_data(db: sqlite3.Connection, order_id: int) -> dict:
    row = db.execute("""SELECT po.*, s.name AS supplier_name,
        u.username AS created_by_name FROM purchase_orders po
        JOIN suppliers s ON s.id = po.supplier_id
        JOIN users u ON u.id = po.created_by WHERE po.id = ?""", (order_id,)).fetchone()
    if not row:
        raise HTTPException(404, "采购订单不存在")
    lines = []
    total = Decimal(0)
    for entry in db.execute("""SELECT pol.id, pol.material_id, m.sku, m.name AS material_name,
        m.unit, pol.quantity, pol.unit_price FROM purchase_order_lines pol
        JOIN materials m ON m.id = pol.material_id
        WHERE pol.purchase_order_id = ? ORDER BY pol.id""", (order_id,)):
        quantity = Decimal(entry["quantity"])
        price = Decimal(entry["unit_price"])
        received = received_quantity(db, entry["id"])
        returned = returned_quantity(db, entry["id"])
        line_total = (quantity * price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total += line_total
        lines.append({**dict(entry), "received_quantity": str(received),
                      "returned_quantity": str(returned), "net_received_quantity": str(received - returned),
                      "remaining_quantity": str(quantity - received), "line_total": str(line_total)})
    return {**dict(row), "lines": lines, "total_amount": str(total)}


def order_receipt_lines(db: sqlite3.Connection, order_id: int, supplier_id: int,
                        lines: list[tuple[int, Decimal]]) -> dict[int, int]:
    order = db.execute("SELECT supplier_id, status FROM purchase_orders WHERE id = ?", (order_id,)).fetchone()
    if not order:
        raise HTTPException(422, "采购订单不存在")
    if order["supplier_id"] != supplier_id:
        raise HTTPException(422, "入库单供应商与采购订单不一致")
    if order["status"] not in ("confirmed", "partially_received"):
        raise HTTPException(409, "采购订单当前不可入库")
    known = {row["material_id"]: row for row in db.execute(
        "SELECT id, material_id, quantity FROM purchase_order_lines WHERE purchase_order_id = ?", (order_id,))}
    result: dict[int, int] = {}
    for material_id, quantity in lines:
        item = known.get(material_id)
        if not item:
            raise HTTPException(422, "入库物料不属于此采购订单")
        if quantity > Decimal(item["quantity"]) - received_quantity(db, item["id"]):
            raise HTTPException(409, f"物料 #{material_id} 超出采购订单未入库数量")
        result[material_id] = item["id"]
    return result


def linked_order_for_receipt(db: sqlite3.Connection, receipt_id: int) -> int | None:
    rows = db.execute("""SELECT pol.purchase_order_id, rl.material_id, rl.quantity
        FROM receipt_lines rl LEFT JOIN receipt_order_links link ON link.receipt_line_id = rl.id
        LEFT JOIN purchase_order_lines pol ON pol.id = link.purchase_order_line_id
        WHERE rl.receipt_id = ?""", (receipt_id,)).fetchall()
    order_ids = {row["purchase_order_id"] for row in rows}
    if order_ids == {None}:
        return None
    if len(order_ids) != 1 or None in order_ids:
        raise HTTPException(409, "入库单关联的采购订单不一致")
    return order_ids.pop()


def validate_receipt_post(db: sqlite3.Connection, receipt_id: int, supplier_id: int) -> int | None:
    order_id = linked_order_for_receipt(db, receipt_id)
    if order_id is None:
        return None
    lines = [(row["material_id"], Decimal(row["quantity"])) for row in db.execute(
        "SELECT material_id, quantity FROM receipt_lines WHERE receipt_id = ?", (receipt_id,))]
    order_receipt_lines(db, order_id, supplier_id, lines)
    return order_id


def update_order_receipt_status(db: sqlite3.Connection, order_id: int) -> None:
    lines = db.execute("SELECT id, quantity FROM purchase_order_lines WHERE purchase_order_id = ?",
                       (order_id,)).fetchall()
    received = [received_quantity(db, line["id"]) for line in lines]
    status = ("confirmed" if all(quantity == 0 for quantity in received) else
              "received" if all(quantity == Decimal(line["quantity"])
                                for quantity, line in zip(received, lines)) else "partially_received")
    db.execute("UPDATE purchase_orders SET status = ? WHERE id = ?", (status, order_id))


@router.get("/purchase-orders")
def list_purchase_orders(_: dict = Depends(require("inventory.view"))) -> list[dict]:
    with connection() as db:
        ids = [row[0] for row in db.execute("SELECT id FROM purchase_orders ORDER BY id DESC")]
        return [order_data(db, order_id) for order_id in ids]


@router.post("/purchase-orders", status_code=201)
def create_purchase_order(payload: PurchaseOrderInput,
                          user: dict = Depends(require("purchase_order.create"))) -> dict:
    if len({line.material_id for line in payload.lines}) != len(payload.lines):
        raise HTTPException(422, "一张采购订单不能重复选择同一物料")
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        if not db.execute("SELECT 1 FROM suppliers WHERE id = ?", (payload.supplier_id,)).fetchone():
            raise HTTPException(422, "供应商不存在")
        for line in payload.lines:
            if not db.execute("SELECT 1 FROM materials WHERE id = ?", (line.material_id,)).fetchone():
                raise HTTPException(422, "物料不存在")
        cursor = db.execute("INSERT INTO purchase_orders(supplier_id, reference, created_by) VALUES (?, ?, ?)",
                            (payload.supplier_id, payload.reference.strip(), user["id"]))
        db.executemany("""INSERT INTO purchase_order_lines(
            purchase_order_id, material_id, quantity, unit_price) VALUES (?, ?, ?, ?)""",
            [(cursor.lastrowid, line.material_id, str(line.quantity), str(line.unit_price))
             for line in payload.lines])
        return order_data(db, cursor.lastrowid)


@router.post("/purchase-orders/{order_id}/confirm")
def confirm_purchase_order(order_id: int,
                           user: dict = Depends(require("purchase_order.confirm"))) -> dict:
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT status FROM purchase_orders WHERE id = ?", (order_id,)).fetchone()
        if not row:
            raise HTTPException(404, "采购订单不存在")
        if row["status"] != "draft":
            raise HTTPException(409, "只能确认草稿采购订单")
        db.execute("""UPDATE purchase_orders SET status = 'confirmed', confirmed_by = ?,
            confirmed_at = CURRENT_TIMESTAMP WHERE id = ?""", (user["id"], order_id))
        return order_data(db, order_id)


@router.post("/purchase-orders/{order_id}/cancel")
def cancel_purchase_order(order_id: int,
                          user: dict = Depends(require("purchase_order.cancel"))) -> dict:
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT status FROM purchase_orders WHERE id = ?", (order_id,)).fetchone()
        if not row:
            raise HTTPException(404, "采购订单不存在")
        # 已有确认入库的数据不能通过取消订单抹去；后续退货应走独立单据。
        if row["status"] not in ("draft", "confirmed"):
            raise HTTPException(409, "已入库或已取消的采购订单不可取消")
        db.execute("""UPDATE purchase_orders SET status = 'cancelled', cancelled_by = ?,
            cancelled_at = CURRENT_TIMESTAMP WHERE id = ?""", (user["id"], order_id))
        return order_data(db, order_id)
