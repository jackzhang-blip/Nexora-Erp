"""从已确认业务单据推导应收应付，保留每笔金额的原始单据来源。"""

import sqlite3
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.core.database import connection
from app.access.security import require

router = APIRouter(prefix="/api/v1")


def money(value: Decimal) -> str:
    # 对外金额始终保留人民币分位，避免零余额和整数付款显示不同精度。
    return str(value.quantize(Decimal("0.01")))


class PaymentInput(BaseModel):
    kind: str
    order_id: int = Field(gt=0)
    action: str
    amount: Decimal
    reference: str = Field(min_length=1, max_length=100)
    note: str = Field(default="", max_length=200)

    @field_validator("kind")
    @classmethod
    def valid_kind(cls, value: str) -> str:
        if value not in ("receivable", "payable"):
            raise ValueError("往来类别无效")
        return value

    @field_validator("action")
    @classmethod
    def valid_action(cls, value: str) -> str:
        if value not in ("settlement", "refund"):
            raise ValueError("收付款类型无效")
        return value

    @field_validator("amount")
    @classmethod
    def valid_amount(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value <= 0 or value > 1_000_000_000_000 or value.as_tuple().exponent < -2:
            raise ValueError("金额须大于零、最多两位小数且不超过一万亿元")
        return value

    @field_validator("reference")
    @classmethod
    def trim_reference(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("收付款参考号不能为空")
        return value.strip()


class ReversalInput(BaseModel):
    reason: str = Field(min_length=1, max_length=200)

    @field_validator("reason")
    @classmethod
    def trim_reason(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("冲销原因不能为空")
        return value.strip()


def amount(quantity: str, unit_price: str | None, sign: int) -> str | None:
    if unit_price is None:
        # 未关联采购订单的历史入库没有单价，不能把应付金额猜成零。
        return None
    value = (Decimal(quantity) * Decimal(unit_price)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return str(value * sign if value else value)


def entry(row: sqlite3.Row, kind: str, source_type: str, sign: int) -> dict:
    return {
        "key": f"{source_type}:{row['source_line_id']}",
        "kind": kind,
        "party_id": row["party_id"],
        "party_name": row["party_name"],
        "source_type": source_type,
        "source_id": row["source_id"],
        "source_line_id": row["source_line_id"],
        "order_id": row["order_id"],
        "material_id": row["material_id"],
        "sku": row["sku"],
        "quantity": row["quantity"],
        "unit_price": row["unit_price"],
        "amount": amount(row["quantity"], row["unit_price"], sign),
        "currency": "CNY",
        "posted_by": row["posted_by"],
        "posted_at": row["posted_at"],
    }


def financial_entries(db: sqlite3.Connection) -> list[dict]:
    # 原单据一经确认不能由接口改价；每次查询从来源行推导，旧数据也可追溯。
    groups = (
        ("receivable", "shipment", 1, """SELECT sl.id AS source_line_id, s.id AS source_id,
            so.id AS order_id, c.id AS party_id, c.name AS party_name, sol.material_id,
            m.sku, sl.quantity, sol.unit_price, s.posted_by, s.posted_at
            FROM shipment_lines sl JOIN shipments s ON s.id = sl.shipment_id
            JOIN sales_order_lines sol ON sol.id = sl.sales_order_line_id
            JOIN sales_orders so ON so.id = sol.sales_order_id
            JOIN customers c ON c.id = so.customer_id
            JOIN materials m ON m.id = sol.material_id WHERE s.status = 'posted'"""),
        ("receivable", "shipment_reversal", -1, """SELECT sl.id AS source_line_id,
            rev.id AS source_id, so.id AS order_id, c.id AS party_id, c.name AS party_name,
            sol.material_id, m.sku, sl.quantity, sol.unit_price,
            rev.created_by AS posted_by, rev.created_at AS posted_at
            FROM shipment_reversals rev JOIN shipments s ON s.id = rev.shipment_id
            JOIN shipment_lines sl ON sl.shipment_id = s.id
            JOIN sales_order_lines sol ON sol.id = sl.sales_order_line_id
            JOIN sales_orders so ON so.id = sol.sales_order_id
            JOIN customers c ON c.id = so.customer_id
            JOIN materials m ON m.id = sol.material_id"""),
        ("receivable", "sales_return", -1, """SELECT srl.id AS source_line_id,
            sr.id AS source_id, so.id AS order_id, c.id AS party_id, c.name AS party_name,
            sol.material_id, m.sku, srl.quantity, sol.unit_price, sr.posted_by, sr.posted_at
            FROM sales_return_lines srl JOIN sales_returns sr ON sr.id = srl.sales_return_id
            JOIN shipment_lines sl ON sl.id = srl.shipment_line_id
            JOIN sales_order_lines sol ON sol.id = sl.sales_order_line_id
            JOIN sales_orders so ON so.id = sol.sales_order_id
            JOIN customers c ON c.id = so.customer_id
            JOIN materials m ON m.id = sol.material_id WHERE sr.status = 'posted'"""),
        ("receivable", "sales_return_reversal", 1, """SELECT srl.id AS source_line_id,
            rev.id AS source_id, so.id AS order_id, c.id AS party_id, c.name AS party_name,
            sol.material_id, m.sku, srl.quantity, sol.unit_price,
            rev.created_by AS posted_by, rev.created_at AS posted_at
            FROM sales_return_reversals rev JOIN sales_returns sr ON sr.id = rev.sales_return_id
            JOIN sales_return_lines srl ON srl.sales_return_id = sr.id
            JOIN shipment_lines sl ON sl.id = srl.shipment_line_id
            JOIN sales_order_lines sol ON sol.id = sl.sales_order_line_id
            JOIN sales_orders so ON so.id = sol.sales_order_id
            JOIN customers c ON c.id = so.customer_id
            JOIN materials m ON m.id = sol.material_id"""),
        ("payable", "receipt", 1, """SELECT rl.id AS source_line_id, r.id AS source_id,
            pol.purchase_order_id AS order_id, sup.id AS party_id, sup.name AS party_name,
            rl.material_id, m.sku, rl.quantity, pol.unit_price, r.posted_by, r.posted_at
            FROM receipt_lines rl JOIN receipts r ON r.id = rl.receipt_id
            JOIN suppliers sup ON sup.id = r.supplier_id
            JOIN materials m ON m.id = rl.material_id
            LEFT JOIN receipt_order_links link ON link.receipt_line_id = rl.id
            LEFT JOIN purchase_order_lines pol ON pol.id = link.purchase_order_line_id
            WHERE r.status = 'posted'"""),
        ("payable", "receipt_reversal", -1, """SELECT rl.id AS source_line_id,
            rev.id AS source_id, pol.purchase_order_id AS order_id,
            sup.id AS party_id, sup.name AS party_name, rl.material_id, m.sku,
            rl.quantity, pol.unit_price, rev.created_by AS posted_by, rev.created_at AS posted_at
            FROM receipt_reversals rev JOIN receipts r ON r.id = rev.receipt_id
            JOIN receipt_lines rl ON rl.receipt_id = r.id
            JOIN suppliers sup ON sup.id = r.supplier_id
            JOIN materials m ON m.id = rl.material_id
            LEFT JOIN receipt_order_links link ON link.receipt_line_id = rl.id
            LEFT JOIN purchase_order_lines pol ON pol.id = link.purchase_order_line_id"""),
        ("payable", "purchase_return", -1, """SELECT prl.id AS source_line_id,
            pr.id AS source_id, pol.purchase_order_id AS order_id,
            sup.id AS party_id, sup.name AS party_name, rl.material_id, m.sku,
            prl.quantity, pol.unit_price, pr.posted_by, pr.posted_at
            FROM purchase_return_lines prl JOIN purchase_returns pr ON pr.id = prl.purchase_return_id
            JOIN receipt_lines rl ON rl.id = prl.receipt_line_id
            JOIN receipts r ON r.id = rl.receipt_id
            JOIN suppliers sup ON sup.id = r.supplier_id
            JOIN materials m ON m.id = rl.material_id
            LEFT JOIN receipt_order_links link ON link.receipt_line_id = rl.id
            LEFT JOIN purchase_order_lines pol ON pol.id = link.purchase_order_line_id
            WHERE pr.status = 'posted'"""),
        ("payable", "purchase_return_reversal", 1, """SELECT prl.id AS source_line_id,
            rev.id AS source_id, pol.purchase_order_id AS order_id,
            sup.id AS party_id, sup.name AS party_name, rl.material_id, m.sku,
            prl.quantity, pol.unit_price, rev.created_by AS posted_by, rev.created_at AS posted_at
            FROM purchase_return_reversals rev
            JOIN purchase_returns pr ON pr.id = rev.purchase_return_id
            JOIN purchase_return_lines prl ON prl.purchase_return_id = pr.id
            JOIN receipt_lines rl ON rl.id = prl.receipt_line_id
            JOIN receipts r ON r.id = rl.receipt_id
            JOIN suppliers sup ON sup.id = r.supplier_id
            JOIN materials m ON m.id = rl.material_id
            LEFT JOIN receipt_order_links link ON link.receipt_line_id = rl.id
            LEFT JOIN purchase_order_lines pol ON pol.id = link.purchase_order_line_id"""),
    )
    result = [entry(row, kind, source_type, sign)
              for kind, source_type, sign, query in groups for row in db.execute(query)]
    users = {row["id"]: row["username"] for row in db.execute("SELECT id, username FROM users")}
    for item in result:
        # 展示操作者姓名，同时保留稳定的账号编号供审计追溯。
        item["posted_by_name"] = users.get(item["posted_by"])
    return sorted(result, key=lambda item: (item["posted_at"], item["source_type"], item["source_line_id"]),
                  reverse=True)


def report_data(entries: list[dict]) -> dict:
    totals = {"receivable": Decimal(0), "payable": Decimal(0)}
    unpriced = 0
    for item in entries:
        if item["amount"] is None:
            unpriced += 1
        else:
            totals[item["kind"]] += Decimal(item["amount"])
    # 此清单只汇总业务净额；收付款与未结金额由订单核对接口单独展示。
    return {"currency": "CNY", "receivable_amount": money(totals["receivable"]),
            "payable_amount": money(totals["payable"]), "unpriced_count": unpriced,
            "entries": entries}


@router.get("/finance/receivables-payables")
def list_receivables_payables(_: dict = Depends(require("finance.view"))) -> dict:
    with connection() as db:
        return report_data(financial_entries(db))


def party_data(db: sqlite3.Connection, kind: str, order_id: int) -> sqlite3.Row:
    if kind == "receivable":
        row = db.execute("""SELECT c.id AS party_id, c.name AS party_name FROM sales_orders so
            JOIN customers c ON c.id = so.customer_id WHERE so.id = ?""", (order_id,)).fetchone()
    else:
        row = db.execute("""SELECT s.id AS party_id, s.name AS party_name FROM purchase_orders po
            JOIN suppliers s ON s.id = po.supplier_id WHERE po.id = ?""", (order_id,)).fetchone()
    if not row:
        raise HTTPException(422, "往来订单不存在")
    return row


def account_data(db: sqlite3.Connection, kind: str, order_id: int,
                 entries: list[dict] | None = None) -> dict:
    row = party_data(db, kind, order_id)
    source = [item for item in (entries if entries is not None else financial_entries(db))
              if item["kind"] == kind and item["order_id"] == order_id and item["amount"] is not None]
    billed = sum((Decimal(item["amount"]) for item in source), Decimal(0))
    settled = sum((Decimal(payment[0]) for payment in db.execute("""SELECT amount FROM payment_records
        WHERE kind = ? AND order_id = ?""", (kind, order_id))), Decimal(0))
    return {"kind": kind, "order_id": order_id, **dict(row), "currency": "CNY",
            "business_amount": money(billed), "settled_amount": money(settled),
            "outstanding_amount": money(billed - settled),
            "source_keys": [item["key"] for item in source]}


@router.get("/finance/accounts")
def list_finance_accounts(_: dict = Depends(require("finance.view"))) -> list[dict]:
    with connection() as db:
        entries = financial_entries(db)
        keys = {(item["kind"], item["order_id"]) for item in entries if item["order_id"] is not None}
        return [account_data(db, kind, order_id, entries) for kind, order_id in sorted(keys)]


def payment_data(db: sqlite3.Connection, payment_id: int) -> dict:
    row = db.execute("""SELECT p.*, u.username AS created_by_name FROM payment_records p
        JOIN users u ON u.id = p.created_by WHERE p.id = ?""", (payment_id,)).fetchone()
    if not row:
        raise HTTPException(404, "收付款记录不存在")
    party = party_data(db, row["kind"], row["order_id"])
    return {**dict(row), **dict(party),
            "currency": "CNY"}


@router.get("/finance/payment-records")
def list_payment_records(_: dict = Depends(require("finance.view"))) -> list[dict]:
    with connection() as db:
        ids = [row[0] for row in db.execute("SELECT id FROM payment_records ORDER BY id DESC")]
        return [payment_data(db, payment_id) for payment_id in ids]


@router.get("/finance/overview")
def finance_overview(_: dict = Depends(require("finance.view"))) -> dict:
    with connection() as db:
        # 一个读取事务提供同一时刻的单据、订单余额和收付款快照。
        db.execute("BEGIN")
        entries = financial_entries(db)
        keys = {(item["kind"], item["order_id"]) for item in entries if item["order_id"] is not None}
        accounts = [account_data(db, kind, order_id, entries) for kind, order_id in sorted(keys)]
        ids = [row[0] for row in db.execute("SELECT id FROM payment_records ORDER BY id DESC")]
        return {"report": report_data(entries), "accounts": accounts,
                "payments": [payment_data(db, payment_id) for payment_id in ids]}


@router.post("/finance/payment-records", status_code=201)
def create_payment_record(payload: PaymentInput, user: dict = Depends(require("finance.record"))) -> dict:
    with connection() as db:
        # 写锁覆盖单据余额核对和新增记录，防止并行收付款超额。
        db.execute("BEGIN IMMEDIATE")
        account = account_data(db, payload.kind, payload.order_id)
        if not account["source_keys"]:
            raise HTTPException(409, "订单尚无已确认且已定价的业务单据")
        outstanding = Decimal(account["outstanding_amount"])
        if payload.action == "settlement" and payload.amount > outstanding:
            raise HTTPException(409, "收付款金额超过订单未结金额")
        if payload.action == "refund" and payload.amount > -outstanding:
            raise HTTPException(409, "退款金额超过订单贷方余额")
        signed = payload.amount if payload.action == "settlement" else -payload.amount
        try:
            cursor = db.execute("""INSERT INTO payment_records(
                kind, order_id, action, amount, reference, note, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?)""", (payload.kind, payload.order_id, payload.action,
                money(signed), payload.reference, payload.note.strip(), user["id"]))
        except sqlite3.IntegrityError:
            raise HTTPException(409, "此订单的收付款参考号已使用") from None
        return payment_data(db, cursor.lastrowid)


@router.post("/finance/payment-records/{payment_id}/reverse", status_code=201)
def reverse_payment_record(payment_id: int, payload: ReversalInput,
                           user: dict = Depends(require("finance.reverse"))) -> dict:
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        original = db.execute("SELECT * FROM payment_records WHERE id = ?", (payment_id,)).fetchone()
        if not original:
            raise HTTPException(404, "收付款记录不存在")
        if original["action"] == "reversal":
            raise HTTPException(409, "冲销记录不能再次冲销")
        if db.execute("SELECT 1 FROM payment_records WHERE reverses_id = ?", (payment_id,)).fetchone():
            raise HTTPException(409, "此收付款记录已冲销")
        # 反向记录保留原记录编号、操作者与原因，不改写或删除历史金额。
        cursor = db.execute("""INSERT INTO payment_records(
            kind, order_id, action, amount, reference, note, reverses_id, created_by)
            VALUES (?, ?, 'reversal', ?, ?, ?, ?, ?)""",
            (original["kind"], original["order_id"], money(-Decimal(original["amount"])),
             f"冲销 #{payment_id}", payload.reason, payment_id, user["id"]))
        return payment_data(db, cursor.lastrowid)
