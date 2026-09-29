"""生产工单成本归集：领料逐行核价，人工和制造费用独立留痕。"""

import sqlite3
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.core.database import connection
from app.production.material_returns import returned_quantity
from app.access.security import require

router = APIRouter(prefix="/api/v1")


def money(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


class MaterialValuationInput(BaseModel):
    material_issue_line_id: int = Field(gt=0)
    unit_cost: Decimal
    reference: str = Field(min_length=1, max_length=100)
    note: str = Field(default="", max_length=200)

    @field_validator("unit_cost")
    @classmethod
    def valid_unit_cost(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value < 0 or value > 1_000_000_000 or value.as_tuple().exponent < -4:
            raise ValueError("材料核定单价须非负、最多四位小数且不超过十亿")
        return value

    @field_validator("reference")
    @classmethod
    def trim_reference(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("成本依据编号不能为空")
        return value.strip()


class ChargeInput(BaseModel):
    work_order_id: int = Field(gt=0)
    kind: Literal["labor", "overhead"]
    amount: Decimal
    reference: str = Field(min_length=1, max_length=100)
    note: str = Field(default="", max_length=200)

    @field_validator("amount")
    @classmethod
    def valid_amount(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value <= 0 or value > 1_000_000_000_000 or value.as_tuple().exponent < -2:
            raise ValueError("费用金额须大于零、最多两位小数且不超过一万亿元")
        return value

    @field_validator("reference")
    @classmethod
    def trim_reference(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("成本依据编号不能为空")
        return value.strip()


class CostReversalInput(BaseModel):
    reason: str = Field(min_length=1, max_length=200)

    @field_validator("reason")
    @classmethod
    def trim_reason(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("冲销原因不能为空")
        return value.strip()


def entry_data(db: sqlite3.Connection, entry_id: int) -> dict:
    row = db.execute("""SELECT pce.*, u.username AS created_by_name,
        r.id AS reversal_id, r.reason AS reversal_reason,
        r.created_by AS reversed_by, r.created_at AS reversed_at,
        ru.username AS reversed_by_name, mil.quantity AS issue_quantity,
        m.sku AS material_sku, m.name AS material_name
        FROM production_cost_entries pce JOIN users u ON u.id = pce.created_by
        LEFT JOIN production_cost_reversals r ON r.entry_id = pce.id
        LEFT JOIN users ru ON ru.id = r.created_by
        LEFT JOIN material_issue_lines mil ON mil.id = pce.material_issue_line_id
        LEFT JOIN work_order_lines wol ON wol.id = mil.work_order_line_id
        LEFT JOIN materials m ON m.id = wol.component_material_id
        WHERE pce.id = ?""", (entry_id,)).fetchone()
    if not row:
        raise HTTPException(404, "生产成本记录不存在")
    result = dict(row)
    result["status"] = "reversed" if row["reversal_id"] is not None else "active"
    if row["kind"] == "material":
        net = Decimal(row["issue_quantity"]) - returned_quantity(db, row["material_issue_line_id"])
        result["net_quantity"] = str(net)
        result["current_amount"] = money(net * Decimal(row["unit_cost"])) if result["status"] == "active" else None
    else:
        result["net_quantity"] = None
        result["current_amount"] = row["amount"] if result["status"] == "active" else None
    return result


def cost_report(db: sqlite3.Connection) -> dict:
    # 未核价的净领料必须显式计数，总成本保持空值，不能误报为已完成核算。
    entries = [entry_data(db, row[0]) for row in db.execute(
        "SELECT id FROM production_cost_entries ORDER BY id DESC")]
    active_rates = {entry["material_issue_line_id"]: entry for entry in entries
                    if entry["status"] == "active" and entry["kind"] == "material"}
    charges: dict[int, dict[str, Decimal]] = {}
    for entry in entries:
        if entry["status"] == "active" and entry["kind"] in ("labor", "overhead"):
            charges.setdefault(entry["work_order_id"], {"labor": Decimal(0), "overhead": Decimal(0)})[
                entry["kind"]] += Decimal(entry["amount"])
    orders = []
    unpriced_lines = []
    for order in db.execute("""SELECT wo.id, wo.status, m.name AS product_name
        FROM work_orders wo JOIN boms b ON b.id = wo.bom_id
        JOIN materials m ON m.id = b.product_material_id ORDER BY wo.id DESC"""):
        known = Decimal(0)
        unpriced = 0
        for line in db.execute("""SELECT mil.id, mil.quantity, mi.id AS material_issue_id,
            m.sku, m.name AS material_name, m.unit FROM material_issue_lines mil
            JOIN material_issues mi ON mi.id = mil.material_issue_id
            JOIN work_order_lines wol ON wol.id = mil.work_order_line_id
            JOIN materials m ON m.id = wol.component_material_id
            WHERE mi.work_order_id = ? AND mi.status = 'posted'""", (order["id"],)):
            net = Decimal(line["quantity"]) - returned_quantity(db, line["id"])
            if net <= 0:
                continue
            valuation = active_rates.get(line["id"])
            if valuation is None:
                unpriced += 1
                unpriced_lines.append({"material_issue_line_id": line["id"],
                                       "material_issue_id": line["material_issue_id"],
                                       "work_order_id": order["id"], "sku": line["sku"],
                                       "material_name": line["material_name"], "unit": line["unit"],
                                       "net_quantity": str(net)})
            else:
                known += Decimal(valuation["current_amount"])
        labor = charges.get(order["id"], {}).get("labor", Decimal(0))
        overhead = charges.get(order["id"], {}).get("overhead", Decimal(0))
        orders.append({"work_order_id": order["id"], "product_name": order["product_name"],
                       "work_order_status": order["status"], "known_material_amount": money(known),
                       "labor_amount": money(labor), "overhead_amount": money(overhead),
                       "total_amount": None if unpriced else money(known + labor + overhead),
                       "unpriced_issue_count": unpriced})
    return {"currency": "CNY", "orders": orders, "entries": entries,
            "unpriced_lines": unpriced_lines}


@router.get("/production-costs")
def list_production_costs(_: dict = Depends(require("production_cost.view"))) -> dict:
    with connection() as db:
        # 汇总跨多张单据，使用同一读取快照避免同时退料或冲销造成前后不一致。
        db.execute("BEGIN")
        return cost_report(db)


@router.post("/production-costs/material-valuations", status_code=201)
def record_material_valuation(payload: MaterialValuationInput,
                              user: dict = Depends(require("production_cost.record"))) -> dict:
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        line = db.execute("""SELECT mi.work_order_id, mi.status FROM material_issue_lines mil
            JOIN material_issues mi ON mi.id = mil.material_issue_id
            WHERE mil.id = ?""", (payload.material_issue_line_id,)).fetchone()
        if not line:
            raise HTTPException(422, "领料明细不存在")
        if line["status"] != "posted":
            raise HTTPException(409, "只有已确认领料明细可以核价")
        if db.execute("""SELECT 1 FROM production_cost_entries pce
            WHERE pce.material_issue_line_id = ? AND NOT EXISTS (
                SELECT 1 FROM production_cost_reversals r WHERE r.entry_id = pce.id)""",
                (payload.material_issue_line_id,)).fetchone():
            raise HTTPException(409, "此领料明细已有有效核价记录，须先冲销原记录")
        cursor = db.execute("""INSERT INTO production_cost_entries(
            work_order_id, kind, material_issue_line_id, unit_cost, reference, note, created_by)
            VALUES (?, 'material', ?, ?, ?, ?, ?)""",
            (line["work_order_id"], payload.material_issue_line_id, str(payload.unit_cost),
             payload.reference, payload.note.strip(), user["id"]))
        return entry_data(db, cursor.lastrowid)


@router.post("/production-costs/charges", status_code=201)
def record_charge(payload: ChargeInput, user: dict = Depends(require("production_cost.record"))) -> dict:
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        order = db.execute("SELECT status FROM work_orders WHERE id = ?", (payload.work_order_id,)).fetchone()
        if not order:
            raise HTTPException(422, "生产工单不存在")
        if order["status"] not in ("released", "in_progress", "completed"):
            raise HTTPException(409, "只有已下达、生产中或已完工的工单可以归集费用")
        cursor = db.execute("""INSERT INTO production_cost_entries(
            work_order_id, kind, amount, reference, note, created_by)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (payload.work_order_id, payload.kind, money(payload.amount),
             payload.reference, payload.note.strip(), user["id"]))
        return entry_data(db, cursor.lastrowid)


@router.post("/production-costs/{entry_id}/reverse")
def reverse_cost_entry(entry_id: int, payload: CostReversalInput,
                       user: dict = Depends(require("production_cost.reverse"))) -> dict:
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        if not db.execute("SELECT 1 FROM production_cost_entries WHERE id = ?", (entry_id,)).fetchone():
            raise HTTPException(404, "生产成本记录不存在")
        if db.execute("SELECT 1 FROM production_cost_reversals WHERE entry_id = ?", (entry_id,)).fetchone():
            raise HTTPException(409, "此生产成本记录已冲销")
        db.execute("""INSERT INTO production_cost_reversals(entry_id, reason, created_by)
            VALUES (?, ?, ?)""", (entry_id, payload.reason, user["id"]))
        return entry_data(db, entry_id)
