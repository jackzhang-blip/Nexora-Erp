"""库存台账：同一筛选范围内按流水顺序计算期初、逐笔余额与期末。"""

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.access.security import require
from app.core.database import connection

router = APIRouter(prefix="/api/v1")


class LedgerQuery(BaseModel):
    warehouse_id: int | None = Field(default=None, gt=0)
    material_id: int | None = Field(default=None, gt=0)
    from_date: date | None = None
    to_date: date | None = None
    source_type: str | None = Field(default=None, max_length=60, pattern=r"^[a-z_]+$")


@router.post("/inventory-ledger/query")
def query_ledger(filters: LedgerQuery,
                 _: dict = Depends(require("inventory.view"))) -> dict:
    if filters.from_date and filters.to_date and filters.to_date < filters.from_date:
        raise HTTPException(422, "结束日期不能早于开始日期")
    with connection() as db:
        if filters.warehouse_id and not db.execute(
            "SELECT 1 FROM warehouses WHERE id = ?", (filters.warehouse_id,)).fetchone():
            raise HTTPException(422, "仓库不存在")
        if filters.material_id and not db.execute(
            "SELECT 1 FROM materials WHERE id = ?", (filters.material_id,)).fetchone():
            raise HTTPException(422, "物料不存在")
        # 所有参数都绑定到 SQL；来源筛选后余额表示该来源范围内的累计变动。
        movement_rows = db.execute("""SELECT sm.id, sm.warehouse_id, w.name AS warehouse_name,
            sm.material_id, m.sku, m.name AS material_name, m.unit, sm.quantity,
            sm.source_type, sm.source_id, sm.source_line_id, sm.created_at,
            u.username AS created_by_name
            FROM stock_movements sm JOIN warehouses w ON w.id = sm.warehouse_id
            JOIN materials m ON m.id = sm.material_id
            LEFT JOIN users u ON u.id = sm.created_by
            WHERE (? IS NULL OR sm.warehouse_id = ?)
              AND (? IS NULL OR sm.material_id = ?)
              AND (? IS NULL OR sm.source_type = ?)
              AND (? IS NULL OR DATE(sm.created_at) <= ?)
            ORDER BY sm.id""", (
                filters.warehouse_id, filters.warehouse_id,
                filters.material_id, filters.material_id,
                filters.source_type, filters.source_type,
                str(filters.to_date) if filters.to_date else None,
                str(filters.to_date) if filters.to_date else None)).fetchall()
        groups: dict[tuple[int, int], dict] = {}
        rows: list[dict] = []
        for item in movement_rows:
            key = (item["warehouse_id"], item["material_id"])
            group = groups.setdefault(key, {
                "warehouse_id": item["warehouse_id"], "warehouse_name": item["warehouse_name"],
                "material_id": item["material_id"], "sku": item["sku"],
                "material_name": item["material_name"], "unit": item["unit"],
                "opening_quantity": Decimal(0), "closing_quantity": Decimal(0)})
            quantity = Decimal(item["quantity"])
            if filters.from_date and item["created_at"][:10] < str(filters.from_date):
                group["opening_quantity"] += quantity
            else:
                group["closing_quantity"] += quantity
                rows.append({**dict(item), "balance_quantity": ""})
        balances = {key: value["opening_quantity"] for key, value in groups.items()}
        for row in rows:
            key = (row["warehouse_id"], row["material_id"])
            balances[key] += Decimal(row["quantity"])
            row["balance_quantity"] = str(balances[key])
        for group in groups.values():
            group["closing_quantity"] = str(group["opening_quantity"] + group["closing_quantity"])
            group["opening_quantity"] = str(group["opening_quantity"])
        return {"groups": list(groups.values()), "rows": rows}
