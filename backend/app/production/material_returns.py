"""生产退料更正：沿原领料明细和仓库追加正向库存流水。"""

from sqlalchemy import select, update, func
from sqlalchemy.orm import Session
from sqlalchemy.engine import RowMapping
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.core.orm import orm_session, add_model
from app.core.models import (
    Material,
    MaterialIssue,
    MaterialIssueLine,
    MaterialReturn,
    MaterialReturnLine,
    StockMovement,
    User,
    Warehouse,
    WorkOrder,
    WorkOrderLine,
)
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


def returned_quantity(db: Session, issue_line_id: int) -> Decimal:
    # 草稿不改变工单净领料；只有确认退料才能恢复可领数量。
    return sum(
        (
            Decimal(row)
            for row in db.scalars(
                select(MaterialReturnLine.quantity)
                .select_from(MaterialReturnLine)
                .join(MaterialReturn, MaterialReturn.id == MaterialReturnLine.material_return_id)
                .where(
                    MaterialReturnLine.material_issue_line_id == issue_line_id,
                    MaterialReturn.status == "posted",
                )
            )
        ),
        Decimal(0),
    )


def checked_lines(db: Session, issue_id: int, lines: list[tuple[int, Decimal]]) -> dict[int, RowMapping]:
    issue = (
        db.execute(
            select(
                MaterialIssue.status,
                WorkOrder.status.label("work_order_status"),
                WorkOrder.id.label("work_order_id"),
                WorkOrder.target_quantity,
            )
            .select_from(MaterialIssue)
            .join(WorkOrder, (WorkOrder.id == MaterialIssue.work_order_id))
            .where((MaterialIssue.id == issue_id))
        )
        .mappings()
        .first()
    )
    if not issue:
        raise HTTPException(422, "原领料单不存在")
    if issue["status"] != "posted":
        raise HTTPException(409, "只有已确认领料单可退料")
    if issue["work_order_status"] != "in_progress":
        raise HTTPException(409, "只有生产中的工单可退料")
    known = {
        row["id"]: row
        for row in db.execute(
            select(
                MaterialIssueLine.id,
                MaterialIssueLine.work_order_line_id,
                WorkOrderLine.component_material_id,
                WorkOrderLine.required_quantity,
                MaterialIssueLine.quantity,
            )
            .select_from(MaterialIssueLine)
            .join(WorkOrderLine, (WorkOrderLine.id == MaterialIssueLine.work_order_line_id))
            .where((MaterialIssueLine.material_issue_id == issue_id))
        ).mappings()
    }
    result = {}
    posted_output, _, _ = posted_completion_totals(db, issue["work_order_id"])
    for line_id, quantity in lines:
        source = known.get(line_id)
        if not source:
            raise HTTPException(422, "退料明细不属于原领料单")
        if quantity > Decimal(source["quantity"]) - returned_quantity(db, line_id):
            raise HTTPException(409, f"领料明细 #{line_id} 超出可退数量")
        # 已报工消耗的最低需料不能再退回，否则成品入库会失去物料来源。
        minimum = required_for_output(
            Decimal(source["required_quantity"]), Decimal(issue["target_quantity"]), posted_output
        )
        if issued_quantity(db, source["work_order_line_id"]) - quantity < minimum:
            raise HTTPException(409, f"组件 #{source['component_material_id']} 已用于完工报工，不可退料")
        result[line_id] = source
    return result


def material_return_data(db: Session, return_id: int) -> dict:
    row = (
        db.execute(
            select(
                MaterialReturn.id,
                MaterialReturn.material_issue_id,
                MaterialReturn.reason,
                MaterialReturn.status,
                MaterialReturn.created_by,
                MaterialReturn.posted_by,
                MaterialReturn.cancelled_by,
                MaterialReturn.created_at,
                MaterialReturn.posted_at,
                MaterialReturn.cancelled_at,
                MaterialIssue.work_order_id,
                MaterialIssue.warehouse_id,
                Warehouse.name.label("warehouse_name"),
                User.username.label("created_by_name"),
            )
            .select_from(MaterialReturn)
            .join(MaterialIssue, (MaterialIssue.id == MaterialReturn.material_issue_id))
            .join(Warehouse, (Warehouse.id == MaterialIssue.warehouse_id))
            .join(User, (User.id == MaterialReturn.created_by))
            .where((MaterialReturn.id == return_id))
        )
        .mappings()
        .first()
    )
    if not row:
        raise HTTPException(404, "生产退料单不存在")
    lines = (
        db.execute(
            select(
                MaterialReturnLine.id,
                MaterialReturnLine.material_issue_line_id,
                MaterialIssueLine.work_order_line_id,
                WorkOrderLine.component_material_id,
                Material.sku,
                Material.name.label("material_name"),
                Material.unit,
                MaterialReturnLine.quantity,
            )
            .select_from(MaterialReturnLine)
            .join(MaterialIssueLine, (MaterialIssueLine.id == MaterialReturnLine.material_issue_line_id))
            .join(WorkOrderLine, (WorkOrderLine.id == MaterialIssueLine.work_order_line_id))
            .join(Material, (Material.id == WorkOrderLine.component_material_id))
            .where((MaterialReturnLine.material_return_id == return_id))
            .order_by(MaterialReturnLine.id)
        )
        .mappings()
        .all()
    )
    return {**dict(row), "lines": [dict(line) for line in lines]}


@router.get("/material-returns")
def list_material_returns(_: dict = Depends(require("production.view"))) -> list[dict]:
    with orm_session() as db:
        ids = [
            row
            for row in db.scalars(
                select(MaterialReturn.id).select_from(MaterialReturn).order_by(MaterialReturn.id.desc())
            )
        ]
        return [material_return_data(db, return_id) for return_id in ids]


@router.post("/material-returns", status_code=201)
def create_material_return(
    payload: MaterialReturnInput, user: dict = Depends(require("material_return.create"))
) -> dict:
    line_ids = [line.material_issue_line_id for line in payload.lines]
    if len(set(line_ids)) != len(line_ids):
        raise HTTPException(422, "一张退料单不能重复选择同一领料明细")
    with orm_session(write=True) as db:
        checked_lines(
            db,
            payload.material_issue_id,
            [(line.material_issue_line_id, line.quantity) for line in payload.lines],
        )
        cursor = add_model(
            db,
            MaterialReturn(
                material_issue_id=payload.material_issue_id, reason=payload.reason, created_by=user["id"]
            ),
        )
        db.add_all(
            [
                MaterialReturnLine(
                    material_return_id=cursor.id,
                    material_issue_line_id=line.material_issue_line_id,
                    quantity=str(line.quantity),
                )
                for line in payload.lines
            ]
        )
        return material_return_data(db, cursor.id)


@router.post("/material-returns/{return_id}/post")
def post_material_return(return_id: int, user: dict = Depends(require("material_return.post"))) -> dict:
    with orm_session(write=True) as db:
        # 写锁覆盖累计退料量与正向流水，防止两份草稿同时确认导致超退。
        material_return = (
            db.execute(
                select(
                    MaterialReturn.id,
                    MaterialReturn.material_issue_id,
                    MaterialReturn.reason,
                    MaterialReturn.status,
                    MaterialReturn.created_by,
                    MaterialReturn.posted_by,
                    MaterialReturn.cancelled_by,
                    MaterialReturn.created_at,
                    MaterialReturn.posted_at,
                    MaterialReturn.cancelled_at,
                )
                .select_from(MaterialReturn)
                .where((MaterialReturn.id == return_id))
            )
            .mappings()
            .first()
        )
        if not material_return:
            raise HTTPException(404, "生产退料单不存在")
        if material_return["status"] != "draft":
            raise HTTPException(409, "此生产退料单已处理")
        lines = (
            db.execute(
                select(
                    MaterialReturnLine.id,
                    MaterialReturnLine.material_issue_line_id,
                    MaterialReturnLine.quantity,
                )
                .select_from(MaterialReturnLine)
                .where((MaterialReturnLine.material_return_id == return_id))
            )
            .mappings()
            .all()
        )
        source = checked_lines(
            db,
            material_return["material_issue_id"],
            [(line["material_issue_line_id"], Decimal(line["quantity"])) for line in lines],
        )
        warehouse_id = db.scalar(
            select(MaterialIssue.warehouse_id)
            .select_from(MaterialIssue)
            .where(MaterialIssue.id == material_return["material_issue_id"])
        )
        for line in lines:
            add_model(
                db,
                StockMovement(
                    warehouse_id=warehouse_id,
                    material_id=source[line["material_issue_line_id"]]["component_material_id"],
                    quantity=line["quantity"],
                    source_type="material_return",
                    source_id=return_id,
                    source_line_id=line["id"],
                    created_by=user["id"],
                ),
            )
        db.execute(
            update(MaterialReturn)
            .where((MaterialReturn.id == return_id))
            .values(status="posted", posted_by=user["id"], posted_at=func.current_timestamp())
        )
        return material_return_data(db, return_id)


@router.post("/material-returns/{return_id}/cancel")
def cancel_material_return(return_id: int, user: dict = Depends(require("material_return.cancel"))) -> dict:
    with orm_session(write=True) as db:
        row = (
            db.execute(
                select(MaterialReturn.status)
                .select_from(MaterialReturn)
                .where((MaterialReturn.id == return_id))
            )
            .mappings()
            .first()
        )
        if not row:
            raise HTTPException(404, "生产退料单不存在")
        if row["status"] != "draft":
            raise HTTPException(409, "已确认退料不可取消，须另行更正")
        db.execute(
            update(MaterialReturn)
            .where((MaterialReturn.id == return_id))
            .values(status="cancelled", cancelled_by=user["id"], cancelled_at=func.current_timestamp())
        )
        return material_return_data(db, return_id)
