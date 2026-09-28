"""多仓库库存与调拨；已确认流水只追加，不直接修改余额。"""

import sqlite3
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from .database import connection
from .security import require

router = APIRouter(prefix="/api/v1")


class WarehouseInput(BaseModel):
    code: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=80)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.upper()

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("仓库名称不能为空")
        return value.strip()


class TransferLineInput(BaseModel):
    material_id: int = Field(gt=0)
    quantity: Decimal

    @field_validator("quantity")
    @classmethod
    def valid_quantity(cls, value: Decimal) -> Decimal:
        # 与入库单使用同一精度约束，防止调拨时凭空产生小数尾差。
        if not value.is_finite() or value <= 0 or value > 1_000_000 or value.as_tuple().exponent < -3:
            raise ValueError("数量须大于零、最多三位小数且不超过一百万")
        return value


class TransferInput(BaseModel):
    from_warehouse_id: int = Field(gt=0)
    to_warehouse_id: int = Field(gt=0)
    reference: str = Field(default="", max_length=100)
    lines: list[TransferLineInput] = Field(min_length=1, max_length=100)


def require_warehouse(db: sqlite3.Connection, warehouse_id: int) -> None:
    if not db.execute("SELECT 1 FROM warehouses WHERE id = ?", (warehouse_id,)).fetchone():
        raise HTTPException(422, "仓库不存在")


def balance(db: sqlite3.Connection, warehouse_id: int, material_id: int) -> Decimal:
    # SQLite SUM 会把十进制文本转成浮点数；逐笔使用 Decimal 才能保持库存精度。
    return sum((Decimal(row[0]) for row in db.execute(
        "SELECT quantity FROM stock_movements WHERE warehouse_id = ? AND material_id = ?",
        (warehouse_id, material_id))), Decimal(0))


def transfer_data(db: sqlite3.Connection, transfer_id: int) -> dict:
    row = db.execute("""SELECT t.*, src.name AS from_warehouse_name,
        dst.name AS to_warehouse_name, u.username AS created_by_name
        FROM transfers t JOIN warehouses src ON src.id = t.from_warehouse_id
        JOIN warehouses dst ON dst.id = t.to_warehouse_id
        JOIN users u ON u.id = t.created_by WHERE t.id = ?""", (transfer_id,)).fetchone()
    if not row:
        raise HTTPException(404, "调拨单不存在")
    lines = db.execute("""SELECT tl.id, tl.material_id, m.sku, m.name AS material_name,
        m.unit, tl.quantity FROM transfer_lines tl JOIN materials m ON m.id = tl.material_id
        WHERE tl.transfer_id = ? ORDER BY tl.id""", (transfer_id,)).fetchall()
    return {**dict(row), "lines": [dict(line) for line in lines]}


@router.get("/warehouses")
def list_warehouses(_: dict = Depends(require("inventory.view"))) -> list[dict]:
    with connection() as db:
        return [dict(row) for row in db.execute("SELECT id, code, name FROM warehouses ORDER BY id")]


@router.post("/warehouses", status_code=201)
def create_warehouse(payload: WarehouseInput, _: dict = Depends(require("warehouse.manage"))) -> dict:
    with connection() as db:
        try:
            cursor = db.execute("INSERT INTO warehouses(code, name) VALUES (?, ?)",
                                (payload.code, payload.name))
        except sqlite3.IntegrityError:
            raise HTTPException(409, "仓库编码或名称已存在") from None
        return {"id": cursor.lastrowid, **payload.model_dump()}


@router.get("/transfers")
def list_transfers(_: dict = Depends(require("inventory.view"))) -> list[dict]:
    with connection() as db:
        ids = [row[0] for row in db.execute("SELECT id FROM transfers ORDER BY id DESC")]
        return [transfer_data(db, transfer_id) for transfer_id in ids]


@router.post("/transfers", status_code=201)
def create_transfer(payload: TransferInput, user: dict = Depends(require("transfer.create"))) -> dict:
    if payload.from_warehouse_id == payload.to_warehouse_id:
        raise HTTPException(422, "来源仓库与目标仓库不能相同")
    if len({line.material_id for line in payload.lines}) != len(payload.lines):
        raise HTTPException(422, "一张调拨单不能重复选择同一物料")
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        require_warehouse(db, payload.from_warehouse_id)
        require_warehouse(db, payload.to_warehouse_id)
        for line in payload.lines:
            if not db.execute("SELECT 1 FROM materials WHERE id = ?", (line.material_id,)).fetchone():
                raise HTTPException(422, "物料不存在")
        cursor = db.execute("""INSERT INTO transfers(
            from_warehouse_id, to_warehouse_id, reference, created_by) VALUES (?, ?, ?, ?)""",
            (payload.from_warehouse_id, payload.to_warehouse_id, payload.reference.strip(), user["id"]))
        db.executemany("INSERT INTO transfer_lines(transfer_id, material_id, quantity) VALUES (?, ?, ?)",
                       [(cursor.lastrowid, line.material_id, str(line.quantity)) for line in payload.lines])
        return transfer_data(db, cursor.lastrowid)


@router.post("/transfers/{transfer_id}/post")
def post_transfer(transfer_id: int, user: dict = Depends(require("transfer.post"))) -> dict:
    with connection() as db:
        # 写锁覆盖库存检查、双向流水和状态变更，阻止并发调拨超出可用量。
        db.execute("BEGIN IMMEDIATE")
        transfer = db.execute("SELECT * FROM transfers WHERE id = ?", (transfer_id,)).fetchone()
        if not transfer:
            raise HTTPException(404, "调拨单不存在")
        if transfer["status"] != "draft":
            raise HTTPException(409, "此调拨单已经确认")
        lines = db.execute("SELECT id, material_id, quantity FROM transfer_lines WHERE transfer_id = ?",
                           (transfer_id,)).fetchall()
        for line in lines:
            quantity = Decimal(line["quantity"])
            if balance(db, transfer["from_warehouse_id"], line["material_id"]) < quantity:
                raise HTTPException(409, f"物料 #{line['material_id']} 在来源仓库的库存不足")
        for line in lines:
            quantity = Decimal(line["quantity"])
            # 一张单据生成等额出入两笔流水，并记录操作者与单据明细来源。
            db.executemany("""INSERT INTO stock_movements(
                warehouse_id, material_id, quantity, source_type, source_id, source_line_id, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?)""", [
                (transfer["from_warehouse_id"], line["material_id"], str(-quantity),
                 "transfer_out", transfer_id, line["id"], user["id"]),
                (transfer["to_warehouse_id"], line["material_id"], str(quantity),
                 "transfer_in", transfer_id, line["id"], user["id"]),
            ])
        db.execute("""UPDATE transfers SET status = 'posted', posted_by = ?,
            posted_at = CURRENT_TIMESTAMP WHERE id = ?""", (user["id"], transfer_id))
        return transfer_data(db, transfer_id)
