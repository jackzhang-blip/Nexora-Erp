"""仓库盘点单：保留账面快照，只通过确认差异流水调整库存。"""

import sqlite3
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.core.database import connection
from app.inventory.warehouse import balance, require_warehouse
from app.access.security import require

router = APIRouter(prefix="/api/v1")


class StocktakeLineInput(BaseModel):
    material_id: int = Field(gt=0)
    counted_quantity: Decimal

    @field_validator("counted_quantity")
    @classmethod
    def valid_count(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value < 0 or value > 1_000_000 or value.as_tuple().exponent < -3:
            raise ValueError("实盘数量须为零至一百万，最多三位小数")
        return value


class StocktakeInput(BaseModel):
    warehouse_id: int = Field(gt=0)
    reference: str = Field(default="", max_length=100)
    lines: list[StocktakeLineInput] = Field(min_length=1, max_length=100)


class StocktakeReverseInput(BaseModel):
    reason: str = Field(min_length=1, max_length=200)

    @field_validator("reason")
    @classmethod
    def valid_reason(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("冲销原因不能为空")
        return value.strip()


def movement_checkpoint(db: sqlite3.Connection, warehouse_id: int, material_id: int) -> int:
    # 即使期间出入库相抵后余额未变，流水编号仍能识别已经过时的实盘结果。
    return db.execute("""SELECT COALESCE(MAX(id), 0) FROM stock_movements
        WHERE warehouse_id = ? AND material_id = ?""", (warehouse_id, material_id)).fetchone()[0]


def stocktake_data(db: sqlite3.Connection, stocktake_id: int) -> dict:
    row = db.execute("""SELECT s.*, w.name AS warehouse_name, u.username AS created_by_name,
        r.id AS reversal_id, r.reason AS reversal_reason,
        r.created_by AS reversed_by, ru.username AS reversed_by_name,
        r.created_at AS reversed_at
        FROM stocktakes s JOIN warehouses w ON w.id = s.warehouse_id
        JOIN users u ON u.id = s.created_by
        LEFT JOIN stocktake_reversals r ON r.stocktake_id = s.id
        LEFT JOIN users ru ON ru.id = r.created_by WHERE s.id = ?""", (stocktake_id,)).fetchone()
    if not row:
        raise HTTPException(404, "盘点单不存在")
    lines = db.execute("""SELECT sl.id, sl.material_id, m.sku, m.name AS material_name,
        m.unit, sl.book_quantity, sl.counted_quantity FROM stocktake_lines sl
        JOIN materials m ON m.id = sl.material_id WHERE sl.stocktake_id = ? ORDER BY sl.id""",
        (stocktake_id,)).fetchall()
    return {**dict(row), "lines": [{**dict(line), "difference": str(
        Decimal(line["counted_quantity"]) - Decimal(line["book_quantity"]))} for line in lines]}


@router.get("/stocktakes")
def list_stocktakes(_: dict = Depends(require("inventory.view"))) -> list[dict]:
    with connection() as db:
        ids = [row[0] for row in db.execute("SELECT id FROM stocktakes ORDER BY id DESC")]
        return [stocktake_data(db, stocktake_id) for stocktake_id in ids]


@router.post("/stocktakes", status_code=201)
def create_stocktake(payload: StocktakeInput, user: dict = Depends(require("stocktake.create"))) -> dict:
    if len({line.material_id for line in payload.lines}) != len(payload.lines):
        raise HTTPException(422, "一张盘点单不能重复选择同一物料")
    with connection() as db:
        # 建单与读取账面库存共用写事务，形成可审计的一致快照。
        db.execute("BEGIN IMMEDIATE")
        require_warehouse(db, payload.warehouse_id)
        for line in payload.lines:
            if not db.execute("SELECT 1 FROM materials WHERE id = ?", (line.material_id,)).fetchone():
                raise HTTPException(422, "物料不存在")
        cursor = db.execute("""INSERT INTO stocktakes(warehouse_id, reference, created_by)
            VALUES (?, ?, ?)""", (payload.warehouse_id, payload.reference.strip(), user["id"]))
        db.executemany("""INSERT INTO stocktake_lines(
            stocktake_id, material_id, book_quantity, counted_quantity, movement_id)
            VALUES (?, ?, ?, ?, ?)""",
            [(cursor.lastrowid, line.material_id, str(balance(db, payload.warehouse_id, line.material_id)),
              str(line.counted_quantity), movement_checkpoint(db, payload.warehouse_id, line.material_id))
             for line in payload.lines])
        return stocktake_data(db, cursor.lastrowid)


@router.post("/stocktakes/{stocktake_id}/post")
def post_stocktake(stocktake_id: int, user: dict = Depends(require("stocktake.post"))) -> dict:
    with connection() as db:
        # 写锁覆盖快照核对、差异流水与状态，期间入库或调拨不会被盘点吞掉。
        db.execute("BEGIN IMMEDIATE")
        stocktake = db.execute("SELECT * FROM stocktakes WHERE id = ?", (stocktake_id,)).fetchone()
        if not stocktake:
            raise HTTPException(404, "盘点单不存在")
        if stocktake["status"] != "draft":
            raise HTTPException(409, "此盘点单已处理")
        lines = db.execute("SELECT * FROM stocktake_lines WHERE stocktake_id = ?", (stocktake_id,)).fetchall()
        for line in lines:
            if (balance(db, stocktake["warehouse_id"], line["material_id"]) != Decimal(line["book_quantity"])
                    or movement_checkpoint(db, stocktake["warehouse_id"], line["material_id"]) != line["movement_id"]):
                raise HTTPException(409, f"物料 #{line['material_id']} 的账面库存已变化，请重新盘点")
        for line in lines:
            difference = Decimal(line["counted_quantity"]) - Decimal(line["book_quantity"])
            if difference:
                # 零差异不生成虚假的库存变动；非零差异记录原单据、明细和操作者。
                db.execute("""INSERT INTO stock_movements(
                    warehouse_id, material_id, quantity, source_type, source_id, source_line_id, created_by)
                    VALUES (?, ?, ?, 'stocktake', ?, ?, ?)""",
                    (stocktake["warehouse_id"], line["material_id"], str(difference), stocktake_id,
                     line["id"], user["id"]))
        db.execute("""UPDATE stocktakes SET status = 'posted', posted_by = ?,
            posted_at = CURRENT_TIMESTAMP WHERE id = ?""", (user["id"], stocktake_id))
        return stocktake_data(db, stocktake_id)


@router.post("/stocktakes/{stocktake_id}/cancel")
def cancel_stocktake(stocktake_id: int, user: dict = Depends(require("stocktake.cancel"))) -> dict:
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT status FROM stocktakes WHERE id = ?", (stocktake_id,)).fetchone()
        if not row:
            raise HTTPException(404, "盘点单不存在")
        if row["status"] != "draft":
            raise HTTPException(409, "只有草稿盘点单可取消；已确认差异须另建更正单")
        db.execute("""UPDATE stocktakes SET status = 'cancelled', cancelled_by = ?,
            cancelled_at = CURRENT_TIMESTAMP WHERE id = ?""", (user["id"], stocktake_id))
        return stocktake_data(db, stocktake_id)


@router.post("/stocktakes/{stocktake_id}/reverse")
def reverse_stocktake(stocktake_id: int, payload: StocktakeReverseInput,
                      user: dict = Depends(require("stocktake.reverse"))) -> dict:
    with connection() as db:
        # 写锁覆盖重复冲销、当前库存核对与补偿流水，避免并发操作生成负库存。
        db.execute("BEGIN IMMEDIATE")
        stocktake = db.execute("SELECT * FROM stocktakes WHERE id = ?", (stocktake_id,)).fetchone()
        if not stocktake:
            raise HTTPException(404, "盘点单不存在")
        if stocktake["status"] != "posted":
            raise HTTPException(409, "只有已确认盘点单可冲销")
        if db.execute("SELECT 1 FROM stocktake_reversals WHERE stocktake_id = ?",
                      (stocktake_id,)).fetchone():
            raise HTTPException(409, "此盘点单已冲销")
        lines = db.execute("SELECT * FROM stocktake_lines WHERE stocktake_id = ?",
                           (stocktake_id,)).fetchall()
        for line in lines:
            difference = Decimal(line["counted_quantity"]) - Decimal(line["book_quantity"])
            if difference > 0 and balance(db, stocktake["warehouse_id"], line["material_id"]) < difference:
                raise HTTPException(409, f"物料 #{line['material_id']} 的当前库存不足以冲销盘盈，请先核对实物")
        reversal_id = db.execute("""INSERT INTO stocktake_reversals(stocktake_id, reason, created_by)
            VALUES (?, ?, ?)""", (stocktake_id, payload.reason, user["id"])).lastrowid
        for line in lines:
            difference = Decimal(line["counted_quantity"]) - Decimal(line["book_quantity"])
            if difference:
                # 冲销只追加反向流水；零差异盘点保留冲销记录但不制造零数量流水。
                db.execute("""INSERT INTO stock_movements(
                    warehouse_id, material_id, quantity, source_type, source_id, source_line_id, created_by)
                    VALUES (?, ?, ?, 'stocktake_reversal', ?, ?, ?)""",
                    (stocktake["warehouse_id"], line["material_id"], str(-difference), reversal_id,
                     line["id"], user["id"]))
        return stocktake_data(db, stocktake_id)
