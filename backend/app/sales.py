"""客户、销售订单和出库单；订单完成量只由已确认出库计算。"""

import sqlite3
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from .database import connection
from .inventory import TransferLineInput, balance, require_warehouse
from .purchase import PurchaseOrderLineInput
from .sales_returns import returned_quantity
from .security import require

router = APIRouter(prefix="/api/v1")


class CustomerInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("客户名称不能为空")
        return value.strip()


class SalesOrderInput(BaseModel):
    customer_id: int = Field(gt=0)
    reference: str = Field(default="", max_length=100)
    # 销售和采购遵守同一物料数量、单价精度，避免两端金额算法漂移。
    lines: list[PurchaseOrderLineInput] = Field(min_length=1, max_length=100)


class ShipmentInput(BaseModel):
    sales_order_id: int = Field(gt=0)
    warehouse_id: int = Field(gt=0)
    reference: str = Field(default="", max_length=100)
    lines: list[TransferLineInput] = Field(min_length=1, max_length=100)


class ShipmentReverseInput(BaseModel):
    reason: str = Field(min_length=1, max_length=200)

    @field_validator("reason")
    @classmethod
    def trim_reason(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("冲销原因不能为空")
        return value.strip()


def shipped_quantity(db: sqlite3.Connection, order_line_id: int) -> Decimal:
    # 已冲销出库保留历史，但不再消耗订单的可出库数量。
    return sum((Decimal(row[0]) for row in db.execute("""SELECT sl.quantity
        FROM shipment_lines sl JOIN shipments s ON s.id = sl.shipment_id
        LEFT JOIN shipment_reversals rev ON rev.shipment_id = s.id
        WHERE sl.sales_order_line_id = ? AND s.status = 'posted' AND rev.id IS NULL""",
        (order_line_id,))), Decimal(0))


def returned_order_quantity(db: sqlite3.Connection, order_line_id: int) -> Decimal:
    # 退货另记正向库存流水；订单显示已退量，但历史已出库量保持原值。
    line_ids = [row[0] for row in db.execute("""SELECT sl.id FROM shipment_lines sl
        JOIN shipments s ON s.id = sl.shipment_id
        LEFT JOIN shipment_reversals rev ON rev.shipment_id = s.id
        WHERE sl.sales_order_line_id = ? AND s.status = 'posted' AND rev.id IS NULL""",
        (order_line_id,))]
    return sum((returned_quantity(db, line_id) for line_id in line_ids), Decimal(0))


def sales_order_data(db: sqlite3.Connection, order_id: int) -> dict:
    row = db.execute("""SELECT so.*, c.name AS customer_name, u.username AS created_by_name
        FROM sales_orders so JOIN customers c ON c.id = so.customer_id
        JOIN users u ON u.id = so.created_by WHERE so.id = ?""", (order_id,)).fetchone()
    if not row:
        raise HTTPException(404, "销售订单不存在")
    lines = []
    total = Decimal(0)
    for item in db.execute("""SELECT sol.id, sol.material_id, m.sku, m.name AS material_name,
        m.unit, sol.quantity, sol.unit_price FROM sales_order_lines sol
        JOIN materials m ON m.id = sol.material_id WHERE sol.sales_order_id = ? ORDER BY sol.id""",
        (order_id,)):
        quantity = Decimal(item["quantity"])
        price = Decimal(item["unit_price"])
        shipped = shipped_quantity(db, item["id"])
        returned = returned_order_quantity(db, item["id"])
        line_total = (quantity * price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total += line_total
        lines.append({**dict(item), "shipped_quantity": str(shipped),
                      "returned_quantity": str(returned), "net_delivered_quantity": str(shipped - returned),
                      "remaining_quantity": str(quantity - shipped), "line_total": str(line_total)})
    return {**dict(row), "lines": lines, "total_amount": str(total)}


def shipment_data(db: sqlite3.Connection, shipment_id: int) -> dict:
    row = db.execute("""SELECT s.*, w.name AS warehouse_name, c.name AS customer_name,
        u.username AS created_by_name,
        rev.id AS reversal_id, rev.reason AS reversal_reason,
        rev.created_by AS reversed_by, ru.username AS reversed_by_name,
        rev.created_at AS reversed_at FROM shipments s
        JOIN warehouses w ON w.id = s.warehouse_id
        JOIN sales_orders so ON so.id = s.sales_order_id
        JOIN customers c ON c.id = so.customer_id
        JOIN users u ON u.id = s.created_by
        LEFT JOIN shipment_reversals rev ON rev.shipment_id = s.id
        LEFT JOIN users ru ON ru.id = rev.created_by WHERE s.id = ?""", (shipment_id,)).fetchone()
    if not row:
        raise HTTPException(404, "出库单不存在")
    lines = db.execute("""SELECT sl.id, sol.material_id, m.sku, m.name AS material_name,
        m.unit, sl.quantity FROM shipment_lines sl
        JOIN sales_order_lines sol ON sol.id = sl.sales_order_line_id
        JOIN materials m ON m.id = sol.material_id WHERE sl.shipment_id = ? ORDER BY sl.id""",
        (shipment_id,)).fetchall()
    result_lines = []
    for item in lines:
        returned = returned_quantity(db, item["id"])
        result_lines.append({**dict(item), "returned_quantity": str(returned),
                             "returnable_quantity": str(Decimal(0) if row["reversal_id"] else
                                                        Decimal(item["quantity"]) - returned)})
    return {**dict(row), "lines": result_lines}


def checked_order_lines(db: sqlite3.Connection, order_id: int,
                        lines: list[tuple[int, Decimal]]) -> dict[int, int]:
    order = db.execute("SELECT status FROM sales_orders WHERE id = ?", (order_id,)).fetchone()
    if not order:
        raise HTTPException(422, "销售订单不存在")
    if order["status"] not in ("confirmed", "partially_shipped"):
        raise HTTPException(409, "销售订单当前不可出库")
    known = {row["material_id"]: row for row in db.execute(
        "SELECT id, material_id, quantity FROM sales_order_lines WHERE sales_order_id = ?", (order_id,))}
    result: dict[int, int] = {}
    for material_id, quantity in lines:
        item = known.get(material_id)
        if not item:
            raise HTTPException(422, "出库物料不属于此销售订单")
        if quantity > Decimal(item["quantity"]) - shipped_quantity(db, item["id"]):
            raise HTTPException(409, f"物料 #{material_id} 超出销售订单未出库数量")
        result[material_id] = item["id"]
    return result


def update_order_shipment_status(db: sqlite3.Connection, order_id: int) -> None:
    lines = db.execute("SELECT id, quantity FROM sales_order_lines WHERE sales_order_id = ?",
                       (order_id,)).fetchall()
    shipped = [shipped_quantity(db, line["id"]) for line in lines]
    status = ("confirmed" if all(quantity == 0 for quantity in shipped) else
              "shipped" if all(quantity == Decimal(line["quantity"])
                               for quantity, line in zip(shipped, lines)) else "partially_shipped")
    db.execute("UPDATE sales_orders SET status = ? WHERE id = ?", (status, order_id))


@router.get("/customers")
def list_customers(_: dict = Depends(require("sales.view"))) -> list[dict]:
    with connection() as db:
        return [dict(row) for row in db.execute("SELECT id, name FROM customers ORDER BY name")]


@router.post("/customers", status_code=201)
def create_customer(payload: CustomerInput, _: dict = Depends(require("customer.manage"))) -> dict:
    with connection() as db:
        try:
            cursor = db.execute("INSERT INTO customers(name) VALUES (?)", (payload.name,))
        except sqlite3.IntegrityError:
            raise HTTPException(409, "客户名称已存在") from None
        return {"id": cursor.lastrowid, "name": payload.name}


@router.get("/sales-orders")
def list_sales_orders(_: dict = Depends(require("sales.view"))) -> list[dict]:
    with connection() as db:
        ids = [row[0] for row in db.execute("SELECT id FROM sales_orders ORDER BY id DESC")]
        return [sales_order_data(db, order_id) for order_id in ids]


@router.post("/sales-orders", status_code=201)
def create_sales_order(payload: SalesOrderInput,
                       user: dict = Depends(require("sales_order.create"))) -> dict:
    if len({line.material_id for line in payload.lines}) != len(payload.lines):
        raise HTTPException(422, "一张销售订单不能重复选择同一物料")
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        if not db.execute("SELECT 1 FROM customers WHERE id = ?", (payload.customer_id,)).fetchone():
            raise HTTPException(422, "客户不存在")
        for line in payload.lines:
            if not db.execute("SELECT 1 FROM materials WHERE id = ?", (line.material_id,)).fetchone():
                raise HTTPException(422, "物料不存在")
        cursor = db.execute("""INSERT INTO sales_orders(customer_id, reference, created_by)
            VALUES (?, ?, ?)""", (payload.customer_id, payload.reference.strip(), user["id"]))
        db.executemany("""INSERT INTO sales_order_lines(
            sales_order_id, material_id, quantity, unit_price) VALUES (?, ?, ?, ?)""",
            [(cursor.lastrowid, line.material_id, str(line.quantity), str(line.unit_price))
             for line in payload.lines])
        return sales_order_data(db, cursor.lastrowid)


@router.post("/sales-orders/{order_id}/confirm")
def confirm_sales_order(order_id: int, user: dict = Depends(require("sales_order.confirm"))) -> dict:
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT status FROM sales_orders WHERE id = ?", (order_id,)).fetchone()
        if not row:
            raise HTTPException(404, "销售订单不存在")
        if row["status"] != "draft":
            raise HTTPException(409, "只能确认草稿销售订单")
        db.execute("""UPDATE sales_orders SET status = 'confirmed', confirmed_by = ?,
            confirmed_at = CURRENT_TIMESTAMP WHERE id = ?""", (user["id"], order_id))
        return sales_order_data(db, order_id)


@router.post("/sales-orders/{order_id}/cancel")
def cancel_sales_order(order_id: int, user: dict = Depends(require("sales_order.cancel"))) -> dict:
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT status FROM sales_orders WHERE id = ?", (order_id,)).fetchone()
        if not row:
            raise HTTPException(404, "销售订单不存在")
        # 已确认出库不能通过取消订单抹去，须走独立销售退货单。
        if row["status"] not in ("draft", "confirmed"):
            raise HTTPException(409, "已出库或已取消的销售订单不可取消")
        db.execute("""UPDATE sales_orders SET status = 'cancelled', cancelled_by = ?,
            cancelled_at = CURRENT_TIMESTAMP WHERE id = ?""", (user["id"], order_id))
        return sales_order_data(db, order_id)


@router.get("/shipments")
def list_shipments(_: dict = Depends(require("sales.view"))) -> list[dict]:
    with connection() as db:
        ids = [row[0] for row in db.execute("SELECT id FROM shipments ORDER BY id DESC")]
        return [shipment_data(db, shipment_id) for shipment_id in ids]


@router.post("/shipments", status_code=201)
def create_shipment(payload: ShipmentInput, user: dict = Depends(require("shipment.create"))) -> dict:
    if len({line.material_id for line in payload.lines}) != len(payload.lines):
        raise HTTPException(422, "一张出库单不能重复选择同一物料")
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        require_warehouse(db, payload.warehouse_id)
        order_line_ids = checked_order_lines(db, payload.sales_order_id,
                                             [(line.material_id, line.quantity) for line in payload.lines])
        cursor = db.execute("""INSERT INTO shipments(sales_order_id, warehouse_id, reference, created_by)
            VALUES (?, ?, ?, ?)""", (payload.sales_order_id, payload.warehouse_id,
                                       payload.reference.strip(), user["id"]))
        db.executemany("""INSERT INTO shipment_lines(shipment_id, sales_order_line_id, quantity)
            VALUES (?, ?, ?)""", [(cursor.lastrowid, order_line_ids[line.material_id], str(line.quantity))
                                  for line in payload.lines])
        return shipment_data(db, cursor.lastrowid)


@router.post("/shipments/{shipment_id}/post")
def post_shipment(shipment_id: int, user: dict = Depends(require("shipment.post"))) -> dict:
    with connection() as db:
        # 写锁覆盖订单剩余量、仓库余额和库存流水，阻止并发出库超量或负库存。
        db.execute("BEGIN IMMEDIATE")
        shipment = db.execute("SELECT * FROM shipments WHERE id = ?", (shipment_id,)).fetchone()
        if not shipment:
            raise HTTPException(404, "出库单不存在")
        if shipment["status"] != "draft":
            raise HTTPException(409, "此出库单已处理")
        lines = db.execute("""SELECT sl.id, sl.quantity, sol.material_id
            FROM shipment_lines sl JOIN sales_order_lines sol ON sol.id = sl.sales_order_line_id
            WHERE sl.shipment_id = ?""", (shipment_id,)).fetchall()
        checked_order_lines(db, shipment["sales_order_id"],
                            [(line["material_id"], Decimal(line["quantity"])) for line in lines])
        for line in lines:
            if balance(db, shipment["warehouse_id"], line["material_id"]) < Decimal(line["quantity"]):
                raise HTTPException(409, f"物料 #{line['material_id']} 在出库仓库的库存不足")
        for line in lines:
            db.execute("""INSERT INTO stock_movements(
                warehouse_id, material_id, quantity, source_type, source_id, source_line_id, created_by)
                VALUES (?, ?, ?, 'shipment', ?, ?, ?)""",
                (shipment["warehouse_id"], line["material_id"], str(-Decimal(line["quantity"])),
                 shipment_id, line["id"], user["id"]))
        db.execute("""UPDATE shipments SET status = 'posted', posted_by = ?,
            posted_at = CURRENT_TIMESTAMP WHERE id = ?""", (user["id"], shipment_id))
        update_order_shipment_status(db, shipment["sales_order_id"])
        return shipment_data(db, shipment_id)


@router.post("/shipments/{shipment_id}/reverse", status_code=201)
def reverse_shipment(shipment_id: int, payload: ShipmentReverseInput,
                     user: dict = Depends(require("shipment.reverse"))) -> dict:
    with connection() as db:
        # 有效销售退货依赖原出库，先处理退货再冲销出库，防止重复入库。
        db.execute("BEGIN IMMEDIATE")
        shipment = db.execute("SELECT status, warehouse_id, sales_order_id FROM shipments WHERE id = ?",
                              (shipment_id,)).fetchone()
        if not shipment:
            raise HTTPException(404, "出库单不存在")
        if shipment["status"] != "posted":
            raise HTTPException(409, "只有已确认出库单可冲销")
        if db.execute("SELECT 1 FROM shipment_reversals WHERE shipment_id = ?",
                      (shipment_id,)).fetchone():
            raise HTTPException(409, "此出库单已冲销")
        lines = db.execute("""SELECT sl.id, sl.quantity, sol.material_id
            FROM shipment_lines sl JOIN sales_order_lines sol ON sol.id = sl.sales_order_line_id
            WHERE sl.shipment_id = ?""", (shipment_id,)).fetchall()
        for line in lines:
            if returned_quantity(db, line["id"]) > 0:
                raise HTTPException(409, "原出库单仍有已确认销售退货，请先冲销退货")
        cursor = db.execute("""INSERT INTO shipment_reversals(shipment_id, reason, created_by)
            VALUES (?, ?, ?)""", (shipment_id, payload.reason, user["id"]))
        for line in lines:
            # 在原出库仓追加正向库存，不改写已确认的负向出库流水。
            db.execute("""INSERT INTO stock_movements(
                warehouse_id, material_id, quantity, source_type, source_id, source_line_id, created_by)
                VALUES (?, ?, ?, 'shipment_reversal', ?, ?, ?)""",
                (shipment["warehouse_id"], line["material_id"], line["quantity"],
                 cursor.lastrowid, line["id"], user["id"]))
        update_order_shipment_status(db, shipment["sales_order_id"])
        return shipment_data(db, shipment_id)


@router.post("/shipments/{shipment_id}/cancel")
def cancel_shipment(shipment_id: int, user: dict = Depends(require("shipment.cancel"))) -> dict:
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT status FROM shipments WHERE id = ?", (shipment_id,)).fetchone()
        if not row:
            raise HTTPException(404, "出库单不存在")
        if row["status"] != "draft":
            raise HTTPException(409, "只有出库草稿可取消；已出库须走销售退货单")
        db.execute("""UPDATE shipments SET status = 'cancelled', cancelled_by = ?,
            cancelled_at = CURRENT_TIMESTAMP WHERE id = ?""", (user["id"], shipment_id))
        return shipment_data(db, shipment_id)
