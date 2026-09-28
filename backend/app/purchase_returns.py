"""采购退货单：以原入库行为来源，确认后追加负向库存流水。"""

import sqlite3
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from .database import connection
from .inventory import balance
from .security import require

router = APIRouter(prefix="/api/v1")


class PurchaseReturnLineInput(BaseModel):
    receipt_line_id: int = Field(gt=0)
    quantity: Decimal

    @field_validator("quantity")
    @classmethod
    def valid_quantity(cls, value: Decimal) -> Decimal:
        # 与入库一致的三位精度，避免退货累计时出现不可核对的尾差。
        if not value.is_finite() or value <= 0 or value > 1_000_000 or value.as_tuple().exponent < -3:
            raise ValueError("退货数量须大于零、最多三位小数且不超过一百万")
        return value


class PurchaseReturnInput(BaseModel):
    receipt_id: int = Field(gt=0)
    reason: str = Field(min_length=1, max_length=200)
    lines: list[PurchaseReturnLineInput] = Field(min_length=1, max_length=100)

    @field_validator("reason")
    @classmethod
    def trim_reason(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("退货原因不能为空")
        return value.strip()


class PurchaseReturnReverseInput(BaseModel):
    reason: str = Field(min_length=1, max_length=200)

    @field_validator("reason")
    @classmethod
    def trim_reason(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("冲销原因不能为空")
        return value.strip()


def returned_quantity(db: sqlite3.Connection, receipt_line_id: int) -> Decimal:
    # 已冲销退货保留历史，但不再减少原入库的净收货数量。
    return sum((Decimal(row[0]) for row in db.execute("""SELECT prl.quantity
        FROM purchase_return_lines prl JOIN purchase_returns pr ON pr.id = prl.purchase_return_id
        LEFT JOIN purchase_return_reversals rev ON rev.purchase_return_id = pr.id
        WHERE prl.receipt_line_id = ? AND pr.status = 'posted' AND rev.id IS NULL""",
        (receipt_line_id,))), Decimal(0))


def checked_return_lines(db: sqlite3.Connection, receipt_id: int,
                         lines: list[tuple[int, Decimal]]) -> dict[int, sqlite3.Row]:
    receipt = db.execute("SELECT status FROM receipts WHERE id = ?", (receipt_id,)).fetchone()
    if not receipt:
        raise HTTPException(422, "原入库单不存在")
    if receipt["status"] != "posted":
        raise HTTPException(409, "只有已确认入库单可退货")
    known = {row["id"]: row for row in db.execute(
        "SELECT id, material_id, quantity FROM receipt_lines WHERE receipt_id = ?", (receipt_id,))}
    result: dict[int, sqlite3.Row] = {}
    for line_id, quantity in lines:
        item = known.get(line_id)
        if not item:
            raise HTTPException(422, "退货明细不属于原入库单")
        if quantity > Decimal(item["quantity"]) - returned_quantity(db, line_id):
            raise HTTPException(409, f"入库明细 #{line_id} 超出可退数量")
        result[line_id] = item
    return result


def purchase_return_data(db: sqlite3.Connection, return_id: int) -> dict:
    row = db.execute("""SELECT pr.*, r.supplier_id, s.name AS supplier_name,
        rw.warehouse_id, w.name AS warehouse_name, u.username AS created_by_name,
        rev.id AS reversal_id, rev.reason AS reversal_reason,
        rev.created_by AS reversed_by, ru.username AS reversed_by_name,
        rev.created_at AS reversed_at
        FROM purchase_returns pr JOIN receipts r ON r.id = pr.receipt_id
        JOIN suppliers s ON s.id = r.supplier_id
        JOIN receipt_warehouses rw ON rw.receipt_id = r.id
        JOIN warehouses w ON w.id = rw.warehouse_id
        JOIN users u ON u.id = pr.created_by
        LEFT JOIN purchase_return_reversals rev ON rev.purchase_return_id = pr.id
        LEFT JOIN users ru ON ru.id = rev.created_by WHERE pr.id = ?""", (return_id,)).fetchone()
    if not row:
        raise HTTPException(404, "采购退货单不存在")
    lines = []
    total = Decimal(0)
    priced = True
    for item in db.execute("""SELECT prl.id, prl.receipt_line_id, rl.material_id,
        m.sku, m.name AS material_name, m.unit, prl.quantity, pol.unit_price
        FROM purchase_return_lines prl
        JOIN receipt_lines rl ON rl.id = prl.receipt_line_id
        JOIN materials m ON m.id = rl.material_id
        LEFT JOIN receipt_order_links link ON link.receipt_line_id = rl.id
        LEFT JOIN purchase_order_lines pol ON pol.id = link.purchase_order_line_id
        WHERE prl.purchase_return_id = ? ORDER BY prl.id""", (return_id,)):
        price = item["unit_price"]
        line_total = None
        if price is not None:
            line_total = (Decimal(item["quantity"]) * Decimal(price)).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP)
            total += line_total
        else:
            # 历史自由入库无采购单价，金额保持未知，不能伪造为零元。
            priced = False
        lines.append({**dict(item), "line_total": str(line_total) if line_total is not None else None})
    return {**dict(row), "lines": lines, "total_amount": str(total) if priced else None}


@router.get("/purchase-returns")
def list_purchase_returns(_: dict = Depends(require("inventory.view"))) -> list[dict]:
    with connection() as db:
        ids = [row[0] for row in db.execute("SELECT id FROM purchase_returns ORDER BY id DESC")]
        return [purchase_return_data(db, return_id) for return_id in ids]


@router.post("/purchase-returns", status_code=201)
def create_purchase_return(payload: PurchaseReturnInput,
                           user: dict = Depends(require("purchase_return.create"))) -> dict:
    if len({line.receipt_line_id for line in payload.lines}) != len(payload.lines):
        raise HTTPException(422, "一张退货单不能重复选择同一入库明细")
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        checked_return_lines(db, payload.receipt_id,
                             [(line.receipt_line_id, line.quantity) for line in payload.lines])
        cursor = db.execute("""INSERT INTO purchase_returns(
            receipt_id, reason, created_by) VALUES (?, ?, ?)""",
            (payload.receipt_id, payload.reason, user["id"]))
        db.executemany("""INSERT INTO purchase_return_lines(
            purchase_return_id, receipt_line_id, quantity) VALUES (?, ?, ?)""",
            [(cursor.lastrowid, line.receipt_line_id, str(line.quantity)) for line in payload.lines])
        return purchase_return_data(db, cursor.lastrowid)


@router.post("/purchase-returns/{return_id}/post")
def post_purchase_return(return_id: int, user: dict = Depends(require("purchase_return.post"))) -> dict:
    with connection() as db:
        # 写锁覆盖累计退货量、仓库余额与流水，避免并发单据透支库存。
        db.execute("BEGIN IMMEDIATE")
        purchase_return = db.execute("SELECT * FROM purchase_returns WHERE id = ?", (return_id,)).fetchone()
        if not purchase_return:
            raise HTTPException(404, "采购退货单不存在")
        if purchase_return["status"] != "draft":
            raise HTTPException(409, "此采购退货单已处理")
        lines = db.execute("""SELECT id, receipt_line_id, quantity FROM purchase_return_lines
            WHERE purchase_return_id = ?""", (return_id,)).fetchall()
        source = checked_return_lines(db, purchase_return["receipt_id"],
                                      [(line["receipt_line_id"], Decimal(line["quantity"]))
                                       for line in lines])
        warehouse_id = db.execute("SELECT warehouse_id FROM receipt_warehouses WHERE receipt_id = ?",
                                  (purchase_return["receipt_id"],)).fetchone()[0]
        for line in lines:
            material_id = source[line["receipt_line_id"]]["material_id"]
            quantity = Decimal(line["quantity"])
            if balance(db, warehouse_id, material_id) < quantity:
                raise HTTPException(409, f"物料 #{material_id} 在原入库仓库库存不足；请先调回原仓库")
            db.execute("""INSERT INTO stock_movements(
                warehouse_id, material_id, quantity, source_type, source_id, source_line_id, created_by)
                VALUES (?, ?, ?, 'purchase_return', ?, ?, ?)""",
                (warehouse_id, material_id, str(-quantity), return_id, line["id"], user["id"]))
        db.execute("""UPDATE purchase_returns SET status = 'posted', posted_by = ?,
            posted_at = CURRENT_TIMESTAMP WHERE id = ?""", (user["id"], return_id))
        return purchase_return_data(db, return_id)


@router.post("/purchase-returns/{return_id}/cancel")
def cancel_purchase_return(return_id: int, user: dict = Depends(require("purchase_return.cancel"))) -> dict:
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT status FROM purchase_returns WHERE id = ?", (return_id,)).fetchone()
        if not row:
            raise HTTPException(404, "采购退货单不存在")
        if row["status"] != "draft":
            raise HTTPException(409, "只有退货草稿可取消；已确认退货须另建更正单")
        db.execute("""UPDATE purchase_returns SET status = 'cancelled', cancelled_by = ?,
            cancelled_at = CURRENT_TIMESTAMP WHERE id = ?""", (user["id"], return_id))
        return purchase_return_data(db, return_id)


@router.post("/purchase-returns/{return_id}/reverse", status_code=201)
def reverse_purchase_return(return_id: int, payload: PurchaseReturnReverseInput,
                            user: dict = Depends(require("purchase_return.reverse"))) -> dict:
    with connection() as db:
        # 一张已确认退货仅允许一次全量冲销；正向流水与冲销记录同事务提交。
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("""SELECT pr.status, rw.warehouse_id FROM purchase_returns pr
            JOIN receipt_warehouses rw ON rw.receipt_id = pr.receipt_id
            WHERE pr.id = ?""", (return_id,)).fetchone()
        if not row:
            raise HTTPException(404, "采购退货单不存在")
        if row["status"] != "posted":
            raise HTTPException(409, "只有已确认采购退货可冲销")
        if db.execute("SELECT 1 FROM purchase_return_reversals WHERE purchase_return_id = ?",
                      (return_id,)).fetchone():
            raise HTTPException(409, "此采购退货单已冲销")
        lines = db.execute("""SELECT prl.id, prl.quantity, rl.material_id
            FROM purchase_return_lines prl JOIN receipt_lines rl ON rl.id = prl.receipt_line_id
            WHERE prl.purchase_return_id = ?""", (return_id,)).fetchall()
        cursor = db.execute("""INSERT INTO purchase_return_reversals(
            purchase_return_id, reason, created_by) VALUES (?, ?, ?)""",
            (return_id, payload.reason, user["id"]))
        for line in lines:
            # 采购退货的反向实物回到原入库仓库，来源行仍指向原退货明细。
            db.execute("""INSERT INTO stock_movements(
                warehouse_id, material_id, quantity, source_type, source_id, source_line_id, created_by)
                VALUES (?, ?, ?, 'purchase_return_reversal', ?, ?, ?)""",
                (row["warehouse_id"], line["material_id"], line["quantity"],
                 cursor.lastrowid, line["id"], user["id"]))
        return purchase_return_data(db, return_id)
