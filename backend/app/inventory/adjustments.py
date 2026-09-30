"""独立库存调整单：异人审批与仓库确认后才追加库存流水。"""

from sqlalchemy import select, update, func, literal
from sqlalchemy.orm import Session, aliased

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.access.security import require
from app.core.orm import orm_session, add_model
from app.core.models import (
    Material,
    StockAdjustment,
    StockAdjustmentLine,
    StockAdjustmentReversal,
    StockMovement,
    User,
    Warehouse,
)
from app.inventory.warehouse import balance, require_warehouse

UserCreator = aliased(User)
UserPoster = aliased(User)
UserReverser = aliased(User)
UserReviewer = aliased(User)

router = APIRouter(prefix="/api/v1")


class AdjustmentLineInput(BaseModel):
    material_id: int = Field(gt=0)
    quantity: Decimal

    @field_validator("quantity")
    @classmethod
    def valid_quantity(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value == 0 or abs(value) > 1_000_000 or value.as_tuple().exponent < -3:
            raise ValueError("调整量不能为零，绝对值不超过一百万且最多三位小数")
        return value


class AdjustmentInput(BaseModel):
    warehouse_id: int = Field(gt=0)
    reason: str = Field(min_length=1, max_length=200)
    reference: str = Field(default="", max_length=100)
    lines: list[AdjustmentLineInput] = Field(min_length=1, max_length=100)

    @field_validator("reason")
    @classmethod
    def valid_reason(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("调整原因不能为空")
        return value.strip()


class ReasonInput(BaseModel):
    reason: str = Field(min_length=1, max_length=200)

    @field_validator("reason")
    @classmethod
    def valid_reason(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("原因不能为空")
        return value.strip()


def adjustment_data(db: Session, adjustment_id: int) -> dict:
    row = (
        db.execute(
            select(
                StockAdjustment.id,
                StockAdjustment.warehouse_id,
                StockAdjustment.reason,
                StockAdjustment.reference,
                StockAdjustment.status,
                StockAdjustment.created_by,
                StockAdjustment.submitted_by,
                StockAdjustment.reviewed_by,
                StockAdjustment.posted_by,
                StockAdjustment.cancelled_by,
                StockAdjustment.review_reason,
                StockAdjustment.created_at,
                StockAdjustment.submitted_at,
                StockAdjustment.reviewed_at,
                StockAdjustment.posted_at,
                StockAdjustment.cancelled_at,
                Warehouse.name.label("warehouse_name"),
                UserCreator.username.label("created_by_name"),
                UserReviewer.username.label("reviewed_by_name"),
                UserPoster.username.label("posted_by_name"),
                StockAdjustmentReversal.id.label("reversal_id"),
                StockAdjustmentReversal.reason.label("reversal_reason"),
                StockAdjustmentReversal.created_at.label("reversed_at"),
                StockAdjustmentReversal.created_by.label("reversed_by"),
                UserReverser.username.label("reversed_by_name"),
            )
            .select_from(StockAdjustment)
            .join(Warehouse, (Warehouse.id == StockAdjustment.warehouse_id))
            .join(UserCreator, (UserCreator.id == StockAdjustment.created_by))
            .outerjoin(UserReviewer, (UserReviewer.id == StockAdjustment.reviewed_by))
            .outerjoin(UserPoster, (UserPoster.id == StockAdjustment.posted_by))
            .outerjoin(StockAdjustmentReversal, (StockAdjustmentReversal.adjustment_id == StockAdjustment.id))
            .outerjoin(UserReverser, (UserReverser.id == StockAdjustmentReversal.created_by))
            .where((StockAdjustment.id == adjustment_id))
        )
        .mappings()
        .first()
    )
    if not row:
        raise HTTPException(404, "库存调整单不存在")
    lines = (
        db.execute(
            select(
                StockAdjustmentLine.id,
                StockAdjustmentLine.material_id,
                Material.sku,
                Material.name.label("material_name"),
                Material.unit,
                StockAdjustmentLine.quantity,
            )
            .select_from(StockAdjustmentLine)
            .join(Material, (Material.id == StockAdjustmentLine.material_id))
            .where((StockAdjustmentLine.adjustment_id == adjustment_id))
            .order_by(StockAdjustmentLine.id)
        )
        .mappings()
        .all()
    )
    return {**dict(row), "lines": [dict(line) for line in lines]}


@router.get("/stock-adjustments")
def list_adjustments(_: dict = Depends(require("adjustment.view"))) -> list[dict]:
    with orm_session() as db:
        ids = [
            row
            for row in db.scalars(
                select(StockAdjustment.id).select_from(StockAdjustment).order_by(StockAdjustment.id.desc())
            )
        ]
        return [adjustment_data(db, item_id) for item_id in ids]


@router.post("/stock-adjustments", status_code=201)
def create_adjustment(payload: AdjustmentInput, user: dict = Depends(require("adjustment.create"))) -> dict:
    if len({line.material_id for line in payload.lines}) != len(payload.lines):
        raise HTTPException(422, "一张调整单不能重复选择同一物料")
    with orm_session(write=True) as db:
        require_warehouse(db, payload.warehouse_id)
        for line in payload.lines:
            if (
                not db.execute(
                    select(literal(1)).select_from(Material).where((Material.id == line.material_id))
                )
                .mappings()
                .first()
            ):
                raise HTTPException(422, f"物料 #{line.material_id} 不存在")
        item_id = add_model(
            db,
            StockAdjustment(
                warehouse_id=payload.warehouse_id,
                reason=payload.reason,
                reference=payload.reference.strip(),
                created_by=user["id"],
            ),
        ).id
        db.add_all(
            [
                StockAdjustmentLine(
                    adjustment_id=item_id, material_id=line.material_id, quantity=str(line.quantity)
                )
                for line in payload.lines
            ]
        )
        return adjustment_data(db, item_id)


def transition(
    adjustment_id: int,
    current: str,
    target: str,
    actor: int,
    actor_column: str,
    time_column: str,
    reason: str | None = None,
) -> dict:
    # 属性只由服务端固定路由指定，状态核对与修改始终在同一写事务中。
    with orm_session(write=True) as db:
        row = (
            db.execute(
                select(StockAdjustment.status, StockAdjustment.created_by)
                .select_from(StockAdjustment)
                .where((StockAdjustment.id == adjustment_id))
            )
            .mappings()
            .first()
        )
        if not row:
            raise HTTPException(404, "库存调整单不存在")
        if row["status"] != current:
            raise HTTPException(409, f"只能处理{current}状态的调整单")
        if target in ("approved", "rejected") and row["created_by"] == actor:
            raise HTTPException(409, "建单人不能审批自己的库存调整单")
        changes = {"status": target, actor_column: actor, time_column: func.current_timestamp()}
        if reason is not None:
            changes["review_reason"] = reason
        db.execute(update(StockAdjustment).where(StockAdjustment.id == adjustment_id).values(**changes))
        return adjustment_data(db, adjustment_id)


@router.post("/stock-adjustments/{adjustment_id}/submit")
def submit_adjustment(adjustment_id: int, user: dict = Depends(require("adjustment.submit"))) -> dict:
    return transition(adjustment_id, "draft", "submitted", user["id"], "submitted_by", "submitted_at")


@router.post("/stock-adjustments/{adjustment_id}/approve")
def approve_adjustment(adjustment_id: int, user: dict = Depends(require("adjustment.review"))) -> dict:
    return transition(adjustment_id, "submitted", "approved", user["id"], "reviewed_by", "reviewed_at")


@router.post("/stock-adjustments/{adjustment_id}/reject")
def reject_adjustment(
    adjustment_id: int, payload: ReasonInput, user: dict = Depends(require("adjustment.review"))
) -> dict:
    return transition(
        adjustment_id, "submitted", "rejected", user["id"], "reviewed_by", "reviewed_at", payload.reason
    )


@router.post("/stock-adjustments/{adjustment_id}/cancel")
def cancel_adjustment(adjustment_id: int, user: dict = Depends(require("adjustment.cancel"))) -> dict:
    with orm_session(write=True) as db:
        row = (
            db.execute(
                select(StockAdjustment.status)
                .select_from(StockAdjustment)
                .where((StockAdjustment.id == adjustment_id))
            )
            .mappings()
            .first()
        )
        if not row:
            raise HTTPException(404, "库存调整单不存在")
        if row["status"] not in ("draft", "submitted", "approved", "rejected"):
            raise HTTPException(409, "此调整单已处理")
        db.execute(
            update(StockAdjustment)
            .where((StockAdjustment.id == adjustment_id))
            .values(status="cancelled", cancelled_by=user["id"], cancelled_at=func.current_timestamp())
        )
        return adjustment_data(db, adjustment_id)


@router.post("/stock-adjustments/{adjustment_id}/post")
def post_adjustment(adjustment_id: int, user: dict = Depends(require("adjustment.post"))) -> dict:
    with orm_session(write=True) as db:
        row = (
            db.execute(
                select(StockAdjustment.status, StockAdjustment.warehouse_id)
                .select_from(StockAdjustment)
                .where((StockAdjustment.id == adjustment_id))
            )
            .mappings()
            .first()
        )
        if not row:
            raise HTTPException(404, "库存调整单不存在")
        if row["status"] != "approved":
            raise HTTPException(409, "只有已审批调整单可确认")
        lines = (
            db.execute(
                select(
                    StockAdjustmentLine.id,
                    StockAdjustmentLine.adjustment_id,
                    StockAdjustmentLine.material_id,
                    StockAdjustmentLine.quantity,
                )
                .select_from(StockAdjustmentLine)
                .where((StockAdjustmentLine.adjustment_id == adjustment_id))
            )
            .mappings()
            .all()
        )
        for line in lines:
            if balance(db, row["warehouse_id"], line["material_id"]) + Decimal(line["quantity"]) < 0:
                raise HTTPException(409, f"物料 #{line['material_id']} 库存不足")
        for line in lines:
            add_model(
                db,
                StockMovement(
                    warehouse_id=row["warehouse_id"],
                    material_id=line["material_id"],
                    quantity=line["quantity"],
                    source_type="adjustment",
                    source_id=adjustment_id,
                    source_line_id=line["id"],
                    created_by=user["id"],
                ),
            )
        db.execute(
            update(StockAdjustment)
            .where((StockAdjustment.id == adjustment_id))
            .values(status="posted", posted_by=user["id"], posted_at=func.current_timestamp())
        )
        return adjustment_data(db, adjustment_id)


@router.post("/stock-adjustments/{adjustment_id}/reverse", status_code=201)
def reverse_adjustment(
    adjustment_id: int, payload: ReasonInput, user: dict = Depends(require("adjustment.reverse"))
) -> dict:
    with orm_session(write=True) as db:
        row = (
            db.execute(
                select(StockAdjustment.status, StockAdjustment.warehouse_id)
                .select_from(StockAdjustment)
                .where((StockAdjustment.id == adjustment_id))
            )
            .mappings()
            .first()
        )
        if not row:
            raise HTTPException(404, "库存调整单不存在")
        if (
            row["status"] != "posted"
            or db.execute(
                select(literal(1))
                .select_from(StockAdjustmentReversal)
                .where((StockAdjustmentReversal.adjustment_id == adjustment_id))
            )
            .mappings()
            .first()
        ):
            raise HTTPException(409, "只能冲销尚未冲销的已确认调整单")
        lines = (
            db.execute(
                select(
                    StockAdjustmentLine.id,
                    StockAdjustmentLine.adjustment_id,
                    StockAdjustmentLine.material_id,
                    StockAdjustmentLine.quantity,
                )
                .select_from(StockAdjustmentLine)
                .where((StockAdjustmentLine.adjustment_id == adjustment_id))
            )
            .mappings()
            .all()
        )
        for line in lines:
            if balance(db, row["warehouse_id"], line["material_id"]) - Decimal(line["quantity"]) < 0:
                raise HTTPException(409, f"物料 #{line['material_id']} 库存不足，无法冲销")
        reversal_id = add_model(
            db,
            StockAdjustmentReversal(
                adjustment_id=adjustment_id, reason=payload.reason, created_by=user["id"]
            ),
        ).id
        for line in lines:
            add_model(
                db,
                StockMovement(
                    warehouse_id=row["warehouse_id"],
                    material_id=line["material_id"],
                    quantity=str(-Decimal(line["quantity"])),
                    source_type="adjustment_reversal",
                    source_id=reversal_id,
                    source_line_id=line["id"],
                    created_by=user["id"],
                ),
            )
        return adjustment_data(db, adjustment_id)
