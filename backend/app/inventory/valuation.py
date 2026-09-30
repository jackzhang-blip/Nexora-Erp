"""按物料汇总的移动加权平均库存计价及可追溯人工核价。"""

import sqlite3
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.access.security import require
from app.core.database import connection

router = APIRouter(prefix="/api/v1/inventory/valuation")
CENT = Decimal("0.01")
FOUR_PLACES = Decimal("0.0001")
MANUAL_SOURCES = {"receipt", "other_inbound", "stocktake", "adjustment",
                  "production_completion"}
PAIRED_SOURCES = {
    "transfer_in": "transfer_out",
    "transfer_reversal_in": "transfer_reversal_out",
    "shipment_reversal": "shipment",
    "other_outbound_reversal": "other_outbound",
    "purchase_return_reversal": "purchase_return",
    "stocktake_reversal": "stocktake",
    "adjustment_reversal": "adjustment",
}


def money(value: Decimal) -> str:
    return str(value.quantize(CENT, rounding=ROUND_HALF_UP))


def unit_price(value: Decimal) -> str:
    return str(value.quantize(FOUR_PLACES, rounding=ROUND_HALF_UP))


class CostInput(BaseModel):
    movement_id: int = Field(gt=0)
    unit_cost: Decimal
    reference: str = Field(min_length=1, max_length=100)
    reason: str = Field(min_length=1, max_length=200)

    @field_validator("unit_cost")
    @classmethod
    def valid_cost(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value < 0 or value > 1_000_000_000 or value.as_tuple().exponent < -4:
            raise ValueError("核定单价须非负、最多四位小数且不超过十亿")
        return value

    @field_validator("reference", "reason")
    @classmethod
    def trim_required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("核价依据和原因不能为空")
        return value.strip()


def purchase_prices(db: sqlite3.Connection) -> dict[int, Decimal]:
    return {row["movement_id"]: Decimal(row["unit_price"]) for row in db.execute("""
        SELECT sm.id AS movement_id, pol.unit_price
        FROM stock_movements sm
        JOIN receipt_order_links link ON link.receipt_line_id = sm.source_line_id
        JOIN purchase_order_lines pol ON pol.id = link.purchase_order_line_id
        WHERE sm.source_type = 'receipt'
    """)}


def linked_source_lines(db: sqlite3.Connection) -> dict[tuple[str, int], tuple[str, int]]:
    links = {}
    for row in db.execute("SELECT id, shipment_line_id FROM sales_return_lines"):
        links[("sales_return", row["id"])] = ("shipment", row["shipment_line_id"])
    for row in db.execute("SELECT id, material_issue_line_id FROM material_return_lines"):
        links[("material_return", row["id"])] = ("material_issue", row["material_issue_line_id"])
    return links


def valuation_report(db: sqlite3.Connection) -> dict:
    """按流水 ID 重放；后登记的核价会重算未结期间的历史金额。"""
    rates = {}
    for row in db.execute("""SELECT movement_id, unit_cost, id FROM inventory_cost_inputs
        ORDER BY id"""):
        rates[row["movement_id"]] = (Decimal(row["unit_cost"]), row["id"])
    order_prices = purchase_prices(db)
    linked = linked_source_lines(db)
    quantities: dict[int, Decimal] = {}
    values: dict[int, Decimal | None] = {}
    source_costs: dict[tuple[str, int], Decimal | None] = {}
    movements = []
    unpriced = []
    for row in db.execute("""SELECT id, warehouse_id, material_id, quantity, source_type,
        source_id, source_line_id, created_at FROM stock_movements ORDER BY id"""):
        material_id = row["material_id"]
        quantity = Decimal(row["quantity"])
        before_quantity = quantities.get(material_id, Decimal(0))
        before_value = values.get(material_id, Decimal(0))
        unit_cost: Decimal | None
        cost_source = "moving_average"
        if quantity > 0:
            paired = linked.get((row["source_type"], row["source_line_id"]))
            if paired is None and row["source_type"] in PAIRED_SOURCES:
                paired = (PAIRED_SOURCES[row["source_type"]], row["source_line_id"])
            if row["id"] in order_prices:
                unit_cost = order_prices[row["id"]]
                cost_source = "purchase_order"
            elif row["id"] in rates:
                unit_cost = rates[row["id"]][0]
                cost_source = "manual"
            elif paired is not None:
                unit_cost = source_costs.get(paired)
                cost_source = "linked_movement" if unit_cost is not None else "unpriced"
            else:
                unit_cost = None
                cost_source = "unpriced"
                unpriced.append(row["id"])
        else:
            unit_cost = (before_value / before_quantity
                         if before_quantity > 0 and before_value is not None else None)
            if unit_cost is None:
                cost_source = "unpriced"
        amount = quantity * unit_cost if unit_cost is not None else None
        after_quantity = before_quantity + quantity
        if after_quantity == 0:
            # 全部出清后，新入库不继承旧期间未知成本或舍入尾差。
            after_value: Decimal | None = Decimal(0)
        elif before_value is None or amount is None:
            after_value = None
        else:
            after_value = before_value + amount
        quantities[material_id] = after_quantity
        values[material_id] = after_value
        source_costs[(row["source_type"], row["source_line_id"])] = unit_cost
        movements.append({**dict(row), "unit_cost": unit_price(unit_cost) if unit_cost is not None else None,
                          "amount": money(amount) if amount is not None else None,
                          "cost_source": cost_source,
                          "cost_input_id": rates[row["id"]][1] if row["id"] in rates else None})
    materials = []
    for row in db.execute("SELECT id, sku, name, unit FROM materials ORDER BY sku"):
        quantity = quantities.get(row["id"], Decimal(0))
        amount = values.get(row["id"], Decimal(0))
        materials.append({**dict(row), "quantity": str(quantity),
                          "amount": money(amount) if amount is not None else None,
                          "average_unit_cost": unit_price(amount / quantity)
                          if amount is not None and quantity > 0 else None})
    total = (None if any(item["amount"] is None for item in materials)
             else money(sum((Decimal(item["amount"]) for item in materials), Decimal(0))))
    return {"currency": "CNY", "method": "moving_weighted_average",
            "scope": "company", "total_amount": total, "materials": materials,
            "movements": movements, "unpriced_movement_ids": unpriced}


@router.get("")
def get_valuation(_: dict = Depends(require("inventory_valuation.view"))) -> dict:
    with connection() as db:
        db.execute("BEGIN")
        return valuation_report(db)


@router.get("/inputs")
def list_cost_inputs(_: dict = Depends(require("inventory_valuation.view"))) -> list[dict]:
    with connection() as db:
        return [dict(row) for row in db.execute("""SELECT i.*, u.username AS created_by_name
            FROM inventory_cost_inputs i JOIN users u ON u.id = i.created_by
            ORDER BY i.id DESC""")]


@router.post("/inputs", status_code=201)
def record_cost(payload: CostInput,
                user: dict = Depends(require("inventory_valuation.record"))) -> dict:
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        movement = db.execute("SELECT id, quantity, source_type FROM stock_movements WHERE id = ?",
                              (payload.movement_id,)).fetchone()
        if not movement:
            raise HTTPException(404, "库存流水不存在")
        if Decimal(movement["quantity"]) <= 0 or movement["source_type"] not in MANUAL_SOURCES:
            raise HTTPException(409, "此流水的成本须沿用原单据或移动平均，不可人工核价")
        if payload.movement_id in purchase_prices(db):
            raise HTTPException(409, "采购订单已有单价，不能覆盖原始价格")
        try:
            cursor = db.execute("""INSERT INTO inventory_cost_inputs(
                movement_id, unit_cost, reference, reason, created_by)
                VALUES (?, ?, ?, ?, ?)""", (payload.movement_id, str(payload.unit_cost),
                                             payload.reference.strip(), payload.reason.strip(), user["id"]))
        except sqlite3.IntegrityError:
            raise HTTPException(409, "同一流水不能重复使用核价依据编号") from None
        row = db.execute("""SELECT i.*, u.username AS created_by_name
            FROM inventory_cost_inputs i JOIN users u ON u.id = i.created_by WHERE i.id = ?""",
                         (cursor.lastrowid,)).fetchone()
        return dict(row)
