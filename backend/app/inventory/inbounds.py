"""其他入库单：不产生采购应付的正向库存来源。"""

from sqlalchemy import select, update, func, literal
from sqlalchemy.orm import Session, aliased

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.access.security import require
from app.core.orm import orm_session, add_model
from app.core.models import (
    Material,
    StockMovement,
    User,
    Warehouse,
    WarehouseInbound,
    WarehouseInboundLine,
    WarehouseInboundReversal,
)
from app.inventory.warehouse import balance, require_warehouse

UserCreator = aliased(User)
UserPoster = aliased(User)
UserRu = aliased(User)

router = APIRouter(prefix="/api/v1")


class InboundLineInput(BaseModel):
    material_id: int = Field(gt=0)
    quantity: Decimal

    @field_validator("quantity")
    @classmethod
    def valid_quantity(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value <= 0 or value > 1_000_000 or value.as_tuple().exponent < -3:
            raise ValueError("数量须大于零、最多三位小数且不超过一百万")
        return value


class InboundInput(BaseModel):
    warehouse_id: int = Field(gt=0)
    reason: str
    note: str = Field(min_length=1, max_length=200)
    reference: str = Field(default="", max_length=100)
    lines: list[InboundLineInput] = Field(min_length=1, max_length=100)

    @field_validator("reason")
    @classmethod
    def valid_reason(cls, value: str) -> str:
        if value not in ("opening", "gift", "other"):
            raise ValueError("入库用途无效")
        return value

    @field_validator("note")
    @classmethod
    def valid_note(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("入库说明不能为空")
        return value.strip()


class ReverseInput(BaseModel):
    reason: str = Field(min_length=1, max_length=200)

    @field_validator("reason")
    @classmethod
    def valid_reason(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("冲销原因不能为空")
        return value.strip()


def inbound_data(db: Session, inbound_id: int) -> dict:
    row = (
        db.execute(
            select(
                WarehouseInbound.id,
                WarehouseInbound.warehouse_id,
                WarehouseInbound.reason,
                WarehouseInbound.note,
                WarehouseInbound.reference,
                WarehouseInbound.status,
                WarehouseInbound.created_by,
                WarehouseInbound.posted_by,
                WarehouseInbound.cancelled_by,
                WarehouseInbound.created_at,
                WarehouseInbound.posted_at,
                WarehouseInbound.cancelled_at,
                Warehouse.name.label("warehouse_name"),
                UserCreator.username.label("created_by_name"),
                UserPoster.username.label("posted_by_name"),
                WarehouseInboundReversal.id.label("reversal_id"),
                WarehouseInboundReversal.reason.label("reversal_reason"),
                WarehouseInboundReversal.created_by.label("reversed_by"),
                UserRu.username.label("reversed_by_name"),
                WarehouseInboundReversal.created_at.label("reversed_at"),
            )
            .select_from(WarehouseInbound)
            .join(Warehouse, (Warehouse.id == WarehouseInbound.warehouse_id))
            .join(UserCreator, (UserCreator.id == WarehouseInbound.created_by))
            .outerjoin(UserPoster, (UserPoster.id == WarehouseInbound.posted_by))
            .outerjoin(WarehouseInboundReversal, (WarehouseInboundReversal.inbound_id == WarehouseInbound.id))
            .outerjoin(UserRu, (UserRu.id == WarehouseInboundReversal.created_by))
            .where((WarehouseInbound.id == inbound_id))
        )
        .mappings()
        .first()
    )
    if not row:
        raise HTTPException(404, "其他入库单不存在")
    lines = (
        db.execute(
            select(
                WarehouseInboundLine.id,
                WarehouseInboundLine.material_id,
                Material.sku,
                Material.name.label("material_name"),
                Material.unit,
                WarehouseInboundLine.quantity,
            )
            .select_from(WarehouseInboundLine)
            .join(Material, (Material.id == WarehouseInboundLine.material_id))
            .where((WarehouseInboundLine.inbound_id == inbound_id))
            .order_by(WarehouseInboundLine.id)
        )
        .mappings()
        .all()
    )
    return {**dict(row), "lines": [dict(line) for line in lines]}


@router.get("/warehouse-inbounds")
def list_inbounds(_: dict = Depends(require("other_inbound.view"))) -> list[dict]:
    with orm_session() as db:
        ids = [
            row
            for row in db.scalars(
                select(WarehouseInbound.id).select_from(WarehouseInbound).order_by(WarehouseInbound.id.desc())
            )
        ]
        return [inbound_data(db, item_id) for item_id in ids]


@router.post("/warehouse-inbounds", status_code=201)
def create_inbound(payload: InboundInput, user: dict = Depends(require("other_inbound.create"))) -> dict:
    if len({line.material_id for line in payload.lines}) != len(payload.lines):
        raise HTTPException(422, "一张入库单不能重复选择同一物料")
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
        inbound_id = add_model(
            db,
            WarehouseInbound(
                warehouse_id=payload.warehouse_id,
                reason=payload.reason,
                note=payload.note,
                reference=payload.reference.strip(),
                created_by=user["id"],
            ),
        ).id
        db.add_all(
            [
                WarehouseInboundLine(
                    inbound_id=inbound_id, material_id=line.material_id, quantity=str(line.quantity)
                )
                for line in payload.lines
            ]
        )
        return inbound_data(db, inbound_id)


@router.post("/warehouse-inbounds/{inbound_id}/post")
def post_inbound(inbound_id: int, user: dict = Depends(require("other_inbound.post"))) -> dict:
    with orm_session(write=True) as db:
        # 状态与所有正向流水同事务提交，失败时整单不改变库存。
        source = (
            db.execute(
                select(WarehouseInbound.status, WarehouseInbound.warehouse_id)
                .select_from(WarehouseInbound)
                .where((WarehouseInbound.id == inbound_id))
            )
            .mappings()
            .first()
        )
        if not source:
            raise HTTPException(404, "其他入库单不存在")
        if source["status"] != "draft":
            raise HTTPException(409, "此入库单已处理")
        db.add_all(
            [
                StockMovement(
                    warehouse_id=values[0],
                    material_id=values[1],
                    quantity=values[2],
                    source_type=values[3],
                    source_id=values[4],
                    source_line_id=values[5],
                    created_by=values[6],
                )
                for values in db.execute(
                    select(
                        literal(source["warehouse_id"]),
                        WarehouseInboundLine.material_id,
                        WarehouseInboundLine.quantity,
                        literal("other_inbound"),
                        literal(inbound_id),
                        WarehouseInboundLine.id,
                        literal(user["id"]),
                    )
                    .select_from(WarehouseInboundLine)
                    .where((WarehouseInboundLine.inbound_id == inbound_id))
                )
            ]
        )
        db.execute(
            update(WarehouseInbound)
            .where((WarehouseInbound.id == inbound_id))
            .values(status="posted", posted_by=user["id"], posted_at=func.current_timestamp())
        )
        return inbound_data(db, inbound_id)


@router.post("/warehouse-inbounds/{inbound_id}/cancel")
def cancel_inbound(inbound_id: int, user: dict = Depends(require("other_inbound.cancel"))) -> dict:
    with orm_session(write=True) as db:
        cursor = db.execute(
            update(WarehouseInbound)
            .where(WarehouseInbound.id == inbound_id, WarehouseInbound.status == "draft")
            .values(status="cancelled", cancelled_by=user["id"], cancelled_at=func.current_timestamp())
        )
        if not cursor.rowcount:
            if (
                not db.execute(
                    select(literal(1))
                    .select_from(WarehouseInbound)
                    .where((WarehouseInbound.id == inbound_id))
                )
                .mappings()
                .first()
            ):
                raise HTTPException(404, "其他入库单不存在")
            raise HTTPException(409, "只能取消其他入库草稿")
        return inbound_data(db, inbound_id)


@router.post("/warehouse-inbounds/{inbound_id}/reverse", status_code=201)
def reverse_inbound(
    inbound_id: int, payload: ReverseInput, user: dict = Depends(require("other_inbound.reverse"))
) -> dict:
    with orm_session(write=True) as db:
        source = (
            db.execute(
                select(WarehouseInbound.status, WarehouseInbound.warehouse_id)
                .select_from(WarehouseInbound)
                .where((WarehouseInbound.id == inbound_id))
            )
            .mappings()
            .first()
        )
        if not source:
            raise HTTPException(404, "其他入库单不存在")
        if (
            source["status"] != "posted"
            or db.execute(
                select(literal(1))
                .select_from(WarehouseInboundReversal)
                .where((WarehouseInboundReversal.inbound_id == inbound_id))
            )
            .mappings()
            .first()
        ):
            raise HTTPException(409, "只能冲销尚未冲销的已确认其他入库")
        lines = (
            db.execute(
                select(
                    WarehouseInboundLine.id, WarehouseInboundLine.material_id, WarehouseInboundLine.quantity
                )
                .select_from(WarehouseInboundLine)
                .where((WarehouseInboundLine.inbound_id == inbound_id))
            )
            .mappings()
            .all()
        )
        for line in lines:
            if balance(db, source["warehouse_id"], line["material_id"]) < Decimal(line["quantity"]):
                raise HTTPException(409, f"物料 #{line['material_id']} 当前库存不足，不能冲销原入库")
        reversal_id = add_model(
            db, WarehouseInboundReversal(inbound_id=inbound_id, reason=payload.reason, created_by=user["id"])
        ).id
        for line in lines:
            add_model(
                db,
                StockMovement(
                    warehouse_id=source["warehouse_id"],
                    material_id=line["material_id"],
                    quantity=str(-Decimal(line["quantity"])),
                    source_type="other_inbound_reversal",
                    source_id=reversal_id,
                    source_line_id=line["id"],
                    created_by=user["id"],
                ),
            )
        return inbound_data(db, inbound_id)
