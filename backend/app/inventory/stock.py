"""库存余额与流水查询接口。"""

from decimal import Decimal

from fastapi import APIRouter, Depends

from app.access.security import require
from app.core.database import connection
from app.inventory.warehouse import require_warehouse

router = APIRouter(prefix="/api/v1")


@router.get("/stock")
def list_stock(warehouse_id: int | None = None, _: dict = Depends(require("inventory.view"))) -> list[dict]:
    with connection() as db:
        if warehouse_id is not None:
            require_warehouse(db, warehouse_id)
        # SQLite 的 SUM 会转成浮点数，因此在 Python 中用 Decimal 计算库存。
        quantities: dict[int, Decimal] = {}
        for row in db.execute("SELECT material_id, quantity FROM stock_movements WHERE (? IS NULL OR warehouse_id = ?)",
                              (warehouse_id, warehouse_id)):
            quantities[row["material_id"]] = quantities.get(row["material_id"], Decimal(0)) + Decimal(row["quantity"])
        return [{**dict(row), "quantity": str(quantities.get(row["id"], Decimal(0)))}
                for row in db.execute("SELECT id, sku, name, unit FROM materials ORDER BY sku")]


@router.get("/movements")
def list_movements(_: dict = Depends(require("inventory.view"))) -> list[dict]:
    with connection() as db:
        return [dict(row) for row in db.execute("""
            SELECT sm.id, sm.warehouse_id, w.name AS warehouse_name,
                   sm.material_id, m.sku, m.name AS material_name, m.unit,
                   sm.quantity, sm.source_type, sm.source_id, sm.source_line_id,
                   CASE WHEN sm.source_type = 'receipt' THEN sm.source_id END AS receipt_id,
                   CASE WHEN sm.source_type = 'receipt_reversal' THEN sm.source_id END AS receipt_reversal_id,
                   CASE WHEN sm.source_type = 'other_inbound' THEN sm.source_id END AS other_inbound_id,
                   CASE WHEN sm.source_type = 'other_inbound_reversal' THEN sm.source_id END AS other_inbound_reversal_id,
                   CASE WHEN sm.source_type = 'other_outbound' THEN sm.source_id END AS other_outbound_id,
                   CASE WHEN sm.source_type = 'other_outbound_reversal' THEN sm.source_id END AS other_outbound_reversal_id,
                   CASE WHEN sm.source_type IN ('transfer_out', 'transfer_in') THEN sm.source_id END AS transfer_id,
                   CASE WHEN sm.source_type IN ('transfer_reversal_out', 'transfer_reversal_in') THEN sm.source_id END AS transfer_reversal_id,
                   CASE WHEN sm.source_type = 'stocktake' THEN sm.source_id END AS stocktake_id,
                   CASE WHEN sm.source_type = 'stocktake_reversal' THEN sm.source_id END AS stocktake_reversal_id,
                   CASE WHEN sm.source_type = 'shipment' THEN sm.source_id END AS shipment_id,
                   CASE WHEN sm.source_type = 'shipment_reversal' THEN sm.source_id END AS shipment_reversal_id,
                   CASE WHEN sm.source_type = 'sales_return' THEN sm.source_id END AS sales_return_id,
                   CASE WHEN sm.source_type = 'sales_return_reversal' THEN sm.source_id END AS sales_return_reversal_id,
                   CASE WHEN sm.source_type = 'purchase_return' THEN sm.source_id END AS purchase_return_id,
                   CASE WHEN sm.source_type = 'purchase_return_reversal' THEN sm.source_id END AS purchase_return_reversal_id,
                   CASE WHEN sm.source_type = 'material_issue' THEN sm.source_id END AS material_issue_id,
                   CASE WHEN sm.source_type = 'material_return' THEN sm.source_id END AS material_return_id,
                   CASE WHEN sm.source_type = 'production_completion' THEN sm.source_id END AS production_completion_id,
                   CASE WHEN sm.source_type = 'production_completion_reversal' THEN sm.source_id END AS production_completion_reversal_id,
                   sm.created_by, sm.created_at
            FROM stock_movements sm
            JOIN materials m ON m.id = sm.material_id
            JOIN warehouses w ON w.id = sm.warehouse_id
            ORDER BY sm.id DESC
        """)]
