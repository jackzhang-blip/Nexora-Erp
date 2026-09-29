"""生产退料更正：沿原领料明细和仓库追加正向库存流水。"""

import sqlite3
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.core.database import connection
from app.access.security import require
from app.production.work_orders import issued_quantity, posted_completion_totals, required_for_output

router = APIRouter(prefix="/api/v1")


class MaterialReturnLineInput(BaseModel):
    material_issue_line_id: int = Field(gt=0)
    quantity: Decimal

    @field_validator("quantity")
    @classmethod
    def valid_quantity(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value <= 0 or value > 1_000_000 or value.as_tuple().exponent < -3:
            raise ValueError("退料数量须大于零、最多三位小数且不超过一百万")
        return value


class MaterialReturnInput(BaseModel):
    material_issue_id: int = Field(gt=0)
    reason: str = Field(min_length=1, max_length=200)
    lines: list[MaterialReturnLineInput] = Field(min_length=1, max_length=100)

    @field_validator("reason")
    @classmethod
    def trim_reason(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("退料原因不能为空")
        return value.strip()


def returned_quantity(db: sqlite3.Connection, issue_line_id: int) -> Decimal:
    # 草稿不改变工单净领料；只有确认退料才能恢复可领数量。
    return sum((Decimal(row[0]) for row in db.execute("""SELECT mrl.quantity
        FROM material_return_lines mrl JOIN material_returns mr ON mr.id = mrl.material_return_id
        WHERE mrl.material_issue_line_id = ? AND mr.status = 'posted'""", (issue_line_id,))), Decimal(0))


def checked_lines(db: sqlite3.Connection, issue_id: int,
                  lines: list[tuple[int, Decimal]]) -> dict[int, sqlite3.Row]:
    issue = db.execute("""SELECT mi.status, wo.status AS work_order_status,
        wo.id AS work_order_id, wo.target_quantity
        FROM material_issues mi JOIN work_orders wo ON wo.id = mi.work_order_id
        WHERE mi.id = ?""", (issue_id,)).fetchone()
    if not issue:
        raise HTTPException(422, "原领料单不存在")
    if issue["status"] != "posted":
        raise HTTPException(409, "只有已确认领料单可退料")
    if issue["work_order_status"] != "in_progress":
        raise HTTPException(409, "只有生产中的工单可退料")
    known = {row["id"]: row for row in db.execute("""SELECT mil.id, mil.work_order_line_id,
        wol.component_material_id, wol.required_quantity, mil.quantity FROM material_issue_lines mil
        JOIN work_order_lines wol ON wol.id = mil.work_order_line_id
        WHERE mil.material_issue_id = ?""", (issue_id,))}
    result = {}
    posted_output, _, _ = posted_completion_totals(db, issue["work_order_id"])
    for line_id, quantity in lines:
        source = known.get(line_id)
        if not source:
            raise HTTPException(422, "退料明细不属于原领料单")
        if quantity > Decimal(source["quantity"]) - returned_quantity(db, line_id):
            raise HTTPException(409, f"领料明细 #{line_id} 超出可退数量")
        # 已报工消耗的最低需料不能再退回，否则成品入库会失去物料来源。
        minimum = required_for_output(Decimal(source["required_quantity"]),
                                      Decimal(issue["target_quantity"]), posted_output)
        if issued_quantity(db, source["work_order_line_id"]) - quantity < minimum:
            raise HTTPException(409, f"组件 #{source['component_material_id']} 已用于完工报工，不可退料")
        result[line_id] = source
    return result


def material_return_data(db: sqlite3.Connection, return_id: int) -> dict:
    row = db.execute("""SELECT mr.*, mi.work_order_id, mi.warehouse_id,
        w.name AS warehouse_name, u.username AS created_by_name
        FROM material_returns mr JOIN material_issues mi ON mi.id = mr.material_issue_id
        JOIN warehouses w ON w.id = mi.warehouse_id
        JOIN users u ON u.id = mr.created_by WHERE mr.id = ?""", (return_id,)).fetchone()
    if not row:
        raise HTTPException(404, "生产退料单不存在")
    lines = db.execute("""SELECT mrl.id, mrl.material_issue_line_id, mil.work_order_line_id,
        wol.component_material_id, m.sku, m.name AS material_name, m.unit, mrl.quantity
        FROM material_return_lines mrl
        JOIN material_issue_lines mil ON mil.id = mrl.material_issue_line_id
        JOIN work_order_lines wol ON wol.id = mil.work_order_line_id
        JOIN materials m ON m.id = wol.component_material_id
        WHERE mrl.material_return_id = ? ORDER BY mrl.id""", (return_id,)).fetchall()
    return {**dict(row), "lines": [dict(line) for line in lines]}


@router.get("/material-returns")
def list_material_returns(_: dict = Depends(require("production.view"))) -> list[dict]:
    with connection() as db:
        ids = [row[0] for row in db.execute("SELECT id FROM material_returns ORDER BY id DESC")]
        return [material_return_data(db, return_id) for return_id in ids]


@router.post("/material-returns", status_code=201)
def create_material_return(payload: MaterialReturnInput,
                           user: dict = Depends(require("material_return.create"))) -> dict:
    line_ids = [line.material_issue_line_id for line in payload.lines]
    if len(set(line_ids)) != len(line_ids):
        raise HTTPException(422, "一张退料单不能重复选择同一领料明细")
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        checked_lines(db, payload.material_issue_id,
                      [(line.material_issue_line_id, line.quantity) for line in payload.lines])
        cursor = db.execute("""INSERT INTO material_returns(material_issue_id, reason, created_by)
            VALUES (?, ?, ?)""", (payload.material_issue_id, payload.reason, user["id"]))
        db.executemany("""INSERT INTO material_return_lines(
            material_return_id, material_issue_line_id, quantity) VALUES (?, ?, ?)""",
            [(cursor.lastrowid, line.material_issue_line_id, str(line.quantity)) for line in payload.lines])
        return material_return_data(db, cursor.lastrowid)


@router.post("/material-returns/{return_id}/post")
def post_material_return(return_id: int, user: dict = Depends(require("material_return.post"))) -> dict:
    with connection() as db:
        # 写锁覆盖累计退料量与正向流水，防止两份草稿同时确认导致超退。
        db.execute("BEGIN IMMEDIATE")
        material_return = db.execute("SELECT * FROM material_returns WHERE id = ?", (return_id,)).fetchone()
        if not material_return:
            raise HTTPException(404, "生产退料单不存在")
        if material_return["status"] != "draft":
            raise HTTPException(409, "此生产退料单已处理")
        lines = db.execute("""SELECT id, material_issue_line_id, quantity FROM material_return_lines
            WHERE material_return_id = ?""", (return_id,)).fetchall()
        source = checked_lines(db, material_return["material_issue_id"],
                               [(line["material_issue_line_id"], Decimal(line["quantity"]))
                                for line in lines])
        warehouse_id = db.execute("SELECT warehouse_id FROM material_issues WHERE id = ?",
                                  (material_return["material_issue_id"],)).fetchone()[0]
        for line in lines:
            db.execute("""INSERT INTO stock_movements(
                warehouse_id, material_id, quantity, source_type, source_id, source_line_id, created_by)
                VALUES (?, ?, ?, 'material_return', ?, ?, ?)""",
                (warehouse_id, source[line["material_issue_line_id"]]["component_material_id"],
                 line["quantity"], return_id, line["id"], user["id"]))
        db.execute("""UPDATE material_returns SET status = 'posted', posted_by = ?,
            posted_at = CURRENT_TIMESTAMP WHERE id = ?""", (user["id"], return_id))
        return material_return_data(db, return_id)


@router.post("/material-returns/{return_id}/cancel")
def cancel_material_return(return_id: int, user: dict = Depends(require("material_return.cancel"))) -> dict:
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT status FROM material_returns WHERE id = ?", (return_id,)).fetchone()
        if not row:
            raise HTTPException(404, "生产退料单不存在")
        if row["status"] != "draft":
            raise HTTPException(409, "已确认退料不可取消，须另行更正")
        db.execute("""UPDATE material_returns SET status = 'cancelled', cancelled_by = ?,
            cancelled_at = CURRENT_TIMESTAMP WHERE id = ?""", (user["id"], return_id))
        return material_return_data(db, return_id)
