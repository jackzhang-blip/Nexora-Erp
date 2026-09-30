"""已结算工单须先冲销结算，再修改其成本或完工来源。"""

import sqlite3

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.models import ProductionCostSettlement, ProductionSettlementReversal
from app.core.orm import orm_session, model_data


def active_settlement(db: sqlite3.Connection | Session, order_id: int) -> dict | None:
    if not isinstance(db, Session):
        # 旧业务调用方持有写锁时，短暂 ORM 读取也受同一数据库写事务保护。
        with orm_session() as session:
            return active_settlement(session, order_id)
    row = db.scalar(select(ProductionCostSettlement).where(
        ProductionCostSettlement.work_order_id == order_id,
        ~select(ProductionSettlementReversal.id).where(
            ProductionSettlementReversal.settlement_id == ProductionCostSettlement.id).exists()
    ).order_by(ProductionCostSettlement.id.desc()).limit(1))
    return model_data(row) if row is not None else None


def ensure_unsettled(db: sqlite3.Connection | Session, order_id: int) -> None:
    if active_settlement(db, order_id) is not None:
        raise HTTPException(409, "工单成本已结算，须先冲销成本结算再更正")
