"""从已确认业务单据推导应收应付，保留每笔金额的原始单据来源。"""

import sqlite3
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends

from .database import connection
from .security import require

router = APIRouter(prefix="/api/v1")


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
        ("receivable", "sales_return", -1, """SELECT srl.id AS source_line_id,
            sr.id AS source_id, so.id AS order_id, c.id AS party_id, c.name AS party_name,
            sol.material_id, m.sku, srl.quantity, sol.unit_price, sr.posted_by, sr.posted_at
            FROM sales_return_lines srl JOIN sales_returns sr ON sr.id = srl.sales_return_id
            JOIN shipment_lines sl ON sl.id = srl.shipment_line_id
            JOIN sales_order_lines sol ON sol.id = sl.sales_order_line_id
            JOIN sales_orders so ON so.id = sol.sales_order_id
            JOIN customers c ON c.id = so.customer_id
            JOIN materials m ON m.id = sol.material_id WHERE sr.status = 'posted'"""),
        ("payable", "receipt", 1, """SELECT rl.id AS source_line_id, r.id AS source_id,
            pol.purchase_order_id AS order_id, sup.id AS party_id, sup.name AS party_name,
            rl.material_id, m.sku, rl.quantity, pol.unit_price, r.posted_by, r.posted_at
            FROM receipt_lines rl JOIN receipts r ON r.id = rl.receipt_id
            JOIN suppliers sup ON sup.id = r.supplier_id
            JOIN materials m ON m.id = rl.material_id
            LEFT JOIN receipt_order_links link ON link.receipt_line_id = rl.id
            LEFT JOIN purchase_order_lines pol ON pol.id = link.purchase_order_line_id
            WHERE r.status = 'posted'"""),
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
    )
    result = [entry(row, kind, source_type, sign)
              for kind, source_type, sign, query in groups for row in db.execute(query)]
    users = {row["id"]: row["username"] for row in db.execute("SELECT id, username FROM users")}
    for item in result:
        # 展示操作者姓名，同时保留稳定的账号编号供审计追溯。
        item["posted_by_name"] = users.get(item["posted_by"])
    return sorted(result, key=lambda item: (item["posted_at"], item["source_type"], item["source_line_id"]),
                  reverse=True)


@router.get("/finance/receivables-payables")
def list_receivables_payables(_: dict = Depends(require("finance.view"))) -> dict:
    with connection() as db:
        entries = financial_entries(db)
    totals = {"receivable": Decimal(0), "payable": Decimal(0)}
    unpriced = 0
    for item in entries:
        if item["amount"] is None:
            unpriced += 1
        else:
            totals[item["kind"]] += Decimal(item["amount"])
    # 余额目前只扣减业务退货；收付款接入后另列已结金额和未结金额。
    return {"currency": "CNY", "receivable_amount": str(totals["receivable"]),
            "payable_amount": str(totals["payable"]), "unpriced_count": unpriced,
            "entries": entries}
