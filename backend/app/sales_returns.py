"""销售退货单：逐项关联已出库明细，确认后追加正向库存流水。"""

import sqlite3
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from .database import connection
from .inventory import require_warehouse
from .security import require

router = APIRouter(prefix="/api/v1")


class SalesReturnLineInput(BaseModel):
    shipment_line_id: int = Field(gt=0)
    quantity: Decimal

    @field_validator("quantity")
    @classmethod
    def valid_quantity(cls, value: Decimal) -> Decimal:
        # 退货沿用库存三位小数精度，不允许用超小数量绕过累计限制。
        if not value.is_finite() or value <= 0 or value > 1_000_000 or value.as_tuple().exponent < -3:
            raise ValueError("退货数量须大于零、最多三位小数且不超过一百万")
        return value


class SalesReturnInput(BaseModel):
    shipment_id: int = Field(gt=0)
    warehouse_id: int = Field(gt=0)
    reason: str = Field(min_length=1, max_length=200)
    lines: list[SalesReturnLineInput] = Field(min_length=1, max_length=100)

    @field_validator("reason")
    @classmethod
    def trim_reason(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("退货原因不能为空")
        return value.strip()


def returned_quantity(db: sqlite3.Connection, shipment_line_id: int) -> Decimal:
    # 草稿不占用可退量；只按已确认退货累计，取消单不影响历史出库。
    return sum((Decimal(row[0]) for row in db.execute("""SELECT srl.quantity
        FROM sales_return_lines srl JOIN sales_returns sr ON sr.id = srl.sales_return_id
        WHERE srl.shipment_line_id = ? AND sr.status = 'posted'""", (shipment_line_id,))), Decimal(0))


def checked_return_lines(db: sqlite3.Connection, shipment_id: int,
                         lines: list[tuple[int, Decimal]]) -> dict[int, sqlite3.Row]:
    shipment = db.execute("SELECT status FROM shipments WHERE id = ?", (shipment_id,)).fetchone()
    if not shipment:
        raise HTTPException(422, "原出库单不存在")
    if shipment["status"] != "posted":
        raise HTTPException(409, "只有已确认出库单可退货")
    known = {row["id"]: row for row in db.execute("""SELECT sl.id, sl.quantity,
        sol.material_id FROM shipment_lines sl
        JOIN sales_order_lines sol ON sol.id = sl.sales_order_line_id
        WHERE sl.shipment_id = ?""", (shipment_id,))}
    result: dict[int, sqlite3.Row] = {}
    for line_id, quantity in lines:
        item = known.get(line_id)
        if not item:
            raise HTTPException(422, "退货明细不属于原出库单")
        if quantity > Decimal(item["quantity"]) - returned_quantity(db, line_id):
            raise HTTPException(409, f"出库明细 #{line_id} 超出可退数量")
        result[line_id] = item
    return result


def sales_return_data(db: sqlite3.Connection, return_id: int) -> dict:
    row = db.execute("""SELECT sr.*, s.sales_order_id, c.name AS customer_name,
        w.name AS warehouse_name, u.username AS created_by_name
        FROM sales_returns sr JOIN shipments s ON s.id = sr.shipment_id
        JOIN sales_orders so ON so.id = s.sales_order_id
        JOIN customers c ON c.id = so.customer_id
        JOIN warehouses w ON w.id = sr.warehouse_id
        JOIN users u ON u.id = sr.created_by WHERE sr.id = ?""", (return_id,)).fetchone()
    if not row:
        raise HTTPException(404, "销售退货单不存在")
    lines = []
    total = Decimal(0)
    for item in db.execute("""SELECT srl.id, srl.shipment_line_id, sol.material_id,
        m.sku, m.name AS material_name, m.unit, srl.quantity, sol.unit_price
        FROM sales_return_lines srl
        JOIN shipment_lines sl ON sl.id = srl.shipment_line_id
        JOIN sales_order_lines sol ON sol.id = sl.sales_order_line_id
        JOIN materials m ON m.id = sol.material_id
        WHERE srl.sales_return_id = ? ORDER BY srl.id""", (return_id,)):
        line_total = (Decimal(item["quantity"]) * Decimal(item["unit_price"])).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP)
        total += line_total
        lines.append({**dict(item), "line_total": str(line_total)})
    return {**dict(row), "lines": lines, "total_amount": str(total)}


@router.get("/sales-returns")
def list_sales_returns(_: dict = Depends(require("sales.view"))) -> list[dict]:
    with connection() as db:
        ids = [row[0] for row in db.execute("SELECT id FROM sales_returns ORDER BY id DESC")]
        return [sales_return_data(db, return_id) for return_id in ids]


@router.post("/sales-returns", status_code=201)
def create_sales_return(payload: SalesReturnInput,
                        user: dict = Depends(require("sales_return.create"))) -> dict:
    if len({line.shipment_line_id for line in payload.lines}) != len(payload.lines):
        raise HTTPException(422, "一张退货单不能重复选择同一出库明细")
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        require_warehouse(db, payload.warehouse_id)
        checked_return_lines(db, payload.shipment_id,
                             [(line.shipment_line_id, line.quantity) for line in payload.lines])
        cursor = db.execute("""INSERT INTO sales_returns(
            shipment_id, warehouse_id, reason, created_by) VALUES (?, ?, ?, ?)""",
            (payload.shipment_id, payload.warehouse_id, payload.reason, user["id"]))
        db.executemany("""INSERT INTO sales_return_lines(
            sales_return_id, shipment_line_id, quantity) VALUES (?, ?, ?)""",
            [(cursor.lastrowid, line.shipment_line_id, str(line.quantity)) for line in payload.lines])
        return sales_return_data(db, cursor.lastrowid)


@router.post("/sales-returns/{return_id}/post")
def post_sales_return(return_id: int, user: dict = Depends(require("sales_return.post"))) -> dict:
    with connection() as db:
        # 同一写事务重新核对累计已退量；两张草稿无法并发退超原出库量。
        db.execute("BEGIN IMMEDIATE")
        sale_return = db.execute("SELECT * FROM sales_returns WHERE id = ?", (return_id,)).fetchone()
        if not sale_return:
            raise HTTPException(404, "销售退货单不存在")
        if sale_return["status"] != "draft":
            raise HTTPException(409, "此销售退货单已处理")
        lines = db.execute("""SELECT id, shipment_line_id, quantity FROM sales_return_lines
            WHERE sales_return_id = ?""", (return_id,)).fetchall()
        source = checked_return_lines(db, sale_return["shipment_id"],
                                      [(line["shipment_line_id"], Decimal(line["quantity"]))
                                       for line in lines])
        for line in lines:
            # 原出库保留负向流水；退回的实物作为新来源入所选仓库。
            db.execute("""INSERT INTO stock_movements(
                warehouse_id, material_id, quantity, source_type, source_id, source_line_id, created_by)
                VALUES (?, ?, ?, 'sales_return', ?, ?, ?)""",
                (sale_return["warehouse_id"], source[line["shipment_line_id"]]["material_id"],
                 line["quantity"], return_id, line["id"], user["id"]))
        db.execute("""UPDATE sales_returns SET status = 'posted', posted_by = ?,
            posted_at = CURRENT_TIMESTAMP WHERE id = ?""", (user["id"], return_id))
        return sales_return_data(db, return_id)


@router.post("/sales-returns/{return_id}/cancel")
def cancel_sales_return(return_id: int, user: dict = Depends(require("sales_return.cancel"))) -> dict:
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT status FROM sales_returns WHERE id = ?", (return_id,)).fetchone()
        if not row:
            raise HTTPException(404, "销售退货单不存在")
        if row["status"] != "draft":
            raise HTTPException(409, "只有退货草稿可取消；已确认退货须另建更正单")
        db.execute("""UPDATE sales_returns SET status = 'cancelled', cancelled_by = ?,
            cancelled_at = CURRENT_TIMESTAMP WHERE id = ?""", (user["id"], return_id))
        return sales_return_data(db, return_id)
