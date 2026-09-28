"""生产领料单与库存流水；确认时核对工单剩余需料和源仓库存。"""

import sqlite3
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from .database import connection
from .inventory import balance, require_warehouse
from .security import require
from .material_returns import returned_quantity
from .work_orders import issued_quantity

router = APIRouter(prefix="/api/v1")


class MaterialIssueLineInput(BaseModel):
    work_order_line_id: int = Field(gt=0)
    quantity: Decimal

    @field_validator("quantity")
    @classmethod
    def valid_quantity(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value <= 0 or value > 1_000_000 or value.as_tuple().exponent < -3:
            raise ValueError("领料数量须大于零、最多三位小数且不超过一百万")
        return value


class MaterialIssueInput(BaseModel):
    work_order_id: int = Field(gt=0)
    warehouse_id: int = Field(gt=0)
    reference: str = Field(default="", max_length=100)
    lines: list[MaterialIssueLineInput] = Field(min_length=1, max_length=100)


def material_issue_data(db: sqlite3.Connection, issue_id: int) -> dict:
    row = db.execute("""SELECT mi.*, w.name AS warehouse_name,
        u.username AS created_by_name FROM material_issues mi
        JOIN warehouses w ON w.id = mi.warehouse_id
        JOIN users u ON u.id = mi.created_by WHERE mi.id = ?""", (issue_id,)).fetchone()
    if not row:
        raise HTTPException(404, "生产领料单不存在")
    lines = db.execute("""SELECT mil.id, mil.work_order_line_id, wol.component_material_id,
        m.sku, m.name AS material_name, m.unit, mil.quantity
        FROM material_issue_lines mil
        JOIN work_order_lines wol ON wol.id = mil.work_order_line_id
        JOIN materials m ON m.id = wol.component_material_id
        WHERE mil.material_issue_id = ? ORDER BY mil.id""", (issue_id,)).fetchall()
    details = []
    for line in lines:
        returned = returned_quantity(db, line["id"])
        details.append({**dict(line), "returned_quantity": str(returned),
                        "returnable_quantity": str(Decimal(line["quantity"]) - returned)})
    return {**dict(row), "lines": details}


def checked_lines(db: sqlite3.Connection, order_id: int,
                  lines: list[tuple[int, Decimal]]) -> list[sqlite3.Row]:
    known = {row["id"]: row for row in db.execute("""SELECT id, component_material_id,
        required_quantity FROM work_order_lines WHERE work_order_id = ?""", (order_id,))}
    result = []
    for line_id, quantity in lines:
        row = known.get(line_id)
        if not row:
            raise HTTPException(422, "领料明细不属于此生产工单")
        if quantity > Decimal(row["required_quantity"]) - issued_quantity(db, line_id):
            raise HTTPException(409, f"组件 #{row['component_material_id']} 超出工单剩余需料")
        result.append(row)
    return result


@router.get("/material-issues")
def list_material_issues(_: dict = Depends(require("production.view"))) -> list[dict]:
    with connection() as db:
        ids = [row[0] for row in db.execute("SELECT id FROM material_issues ORDER BY id DESC")]
        return [material_issue_data(db, issue_id) for issue_id in ids]


@router.post("/material-issues", status_code=201)
def create_material_issue(payload: MaterialIssueInput,
                          user: dict = Depends(require("material_issue.create"))) -> dict:
    line_ids = [line.work_order_line_id for line in payload.lines]
    if len(set(line_ids)) != len(line_ids):
        raise HTTPException(422, "一张领料单不能重复选择同一组件")
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        order = db.execute("SELECT status FROM work_orders WHERE id = ?", (payload.work_order_id,)).fetchone()
        if not order:
            raise HTTPException(422, "生产工单不存在")
        if order["status"] not in ("released", "in_progress"):
            raise HTTPException(409, "只有已下达或生产中的工单可以领料")
        require_warehouse(db, payload.warehouse_id)
        checked_lines(db, payload.work_order_id,
                      [(line.work_order_line_id, line.quantity) for line in payload.lines])
        cursor = db.execute("""INSERT INTO material_issues(
            work_order_id, warehouse_id, reference, created_by) VALUES (?, ?, ?, ?)""",
            (payload.work_order_id, payload.warehouse_id, payload.reference.strip(), user["id"]))
        db.executemany("""INSERT INTO material_issue_lines(
            material_issue_id, work_order_line_id, quantity) VALUES (?, ?, ?)""",
            [(cursor.lastrowid, line.work_order_line_id, str(line.quantity)) for line in payload.lines])
        return material_issue_data(db, cursor.lastrowid)


@router.post("/material-issues/{issue_id}/post")
def post_material_issue(issue_id: int, user: dict = Depends(require("material_issue.post"))) -> dict:
    with connection() as db:
        # 同一写锁保护剩余需料、库存余额、负向流水和工单状态。
        db.execute("BEGIN IMMEDIATE")
        issue = db.execute("SELECT * FROM material_issues WHERE id = ?", (issue_id,)).fetchone()
        if not issue:
            raise HTTPException(404, "生产领料单不存在")
        if issue["status"] != "draft":
            raise HTTPException(409, "此生产领料单已处理")
        order = db.execute("SELECT status FROM work_orders WHERE id = ?", (issue["work_order_id"],)).fetchone()
        if order["status"] not in ("released", "in_progress"):
            raise HTTPException(409, "生产工单当前不可领料")
        lines = db.execute("""SELECT mil.id, mil.work_order_line_id, mil.quantity
            FROM material_issue_lines mil WHERE mil.material_issue_id = ?""", (issue_id,)).fetchall()
        checked = checked_lines(db, issue["work_order_id"],
                                [(line["work_order_line_id"], Decimal(line["quantity"])) for line in lines])
        for line, order_line in zip(lines, checked):
            if balance(db, issue["warehouse_id"], order_line["component_material_id"]) < Decimal(line["quantity"]):
                raise HTTPException(409, f"组件 #{order_line['component_material_id']} 在源仓库的库存不足")
        for line, order_line in zip(lines, checked):
            db.execute("""INSERT INTO stock_movements(
                warehouse_id, material_id, quantity, source_type, source_id, source_line_id, created_by)
                VALUES (?, ?, ?, 'material_issue', ?, ?, ?)""",
                (issue["warehouse_id"], order_line["component_material_id"],
                 str(-Decimal(line["quantity"])), issue_id, line["id"], user["id"]))
        db.execute("""UPDATE material_issues SET status = 'posted', posted_by = ?,
            posted_at = CURRENT_TIMESTAMP WHERE id = ?""", (user["id"], issue_id))
        db.execute("UPDATE work_orders SET status = 'in_progress' WHERE id = ? AND status = 'released'",
                   (issue["work_order_id"],))
        return material_issue_data(db, issue_id)


@router.post("/material-issues/{issue_id}/cancel")
def cancel_material_issue(issue_id: int, user: dict = Depends(require("material_issue.cancel"))) -> dict:
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT status FROM material_issues WHERE id = ?", (issue_id,)).fetchone()
        if not row:
            raise HTTPException(404, "生产领料单不存在")
        if row["status"] != "draft":
            raise HTTPException(409, "已确认领料不可取消，须另行办理退料更正")
        db.execute("""UPDATE material_issues SET status = 'cancelled', cancelled_by = ?,
            cancelled_at = CURRENT_TIMESTAMP WHERE id = ?""", (user["id"], issue_id))
        return material_issue_data(db, issue_id)
