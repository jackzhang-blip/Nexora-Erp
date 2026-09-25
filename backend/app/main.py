"""Nexora ERP 本地业务 API。"""

import secrets
import sqlite3
import time
import ipaddress
from contextlib import asynccontextmanager
from decimal import Decimal

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, field_validator

from .database import connection, migrate
from .security import bearer, current_user, hash_password, require, token_hash, user_details, verify_password


@asynccontextmanager
async def lifespan(_: FastAPI):
    # 启动时检查并升级本地数据库；不依赖桌面页面是否已经打开。
    migrate()
    yield


app = FastAPI(title="Nexora ERP API", version="0.1.0", lifespan=lifespan)


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class AccountInput(BaseModel):
    username: str = Field(min_length=3, max_length=40, pattern=r"^[A-Za-z0-9_]+$")
    password: str = Field(min_length=12, max_length=128)


class LoginInput(BaseModel):
    username: str
    password: str


class UserInput(AccountInput):
    roles: list[str] = Field(min_length=1)


class RolesInput(BaseModel):
    roles: list[str] = Field(min_length=1)


class SupplierInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("供应商名称不能为空")
        return value.strip()


class MaterialInput(BaseModel):
    sku: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=120)
    unit: str = Field(min_length=1, max_length=20)

    @field_validator("sku", "name", "unit")
    @classmethod
    def trim_fields(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("字段不能为空")
        return value.strip()


class ReceiptLineInput(BaseModel):
    material_id: int = Field(gt=0)
    quantity: Decimal

    @field_validator("quantity")
    @classmethod
    def valid_quantity(cls, value: Decimal) -> Decimal:
        # 用十进制字符串保存数量，避免浮点数改变库存精度。
        if not value.is_finite() or value <= 0 or value > 1_000_000 or value.as_tuple().exponent < -3:
            raise ValueError("数量须大于零、最多三位小数且不超过一百万")
        return value


class ReceiptInput(BaseModel):
    supplier_id: int = Field(gt=0)
    reference: str = Field(default="", max_length=100)
    lines: list[ReceiptLineInput] = Field(min_length=1, max_length=100)


def validate_roles(db: sqlite3.Connection, roles: list[str]) -> list[str]:
    unique = sorted(set(roles))
    known = {row[0] for row in db.execute("SELECT code FROM roles")}
    if not unique or not set(unique) <= known:
        raise HTTPException(422, "角色无效")
    return unique


def receipt_data(db: sqlite3.Connection, receipt_id: int) -> dict:
    row = db.execute("""
        SELECT r.*, s.name AS supplier_name, u.username AS created_by_name
        FROM receipts r JOIN suppliers s ON s.id = r.supplier_id
        JOIN users u ON u.id = r.created_by WHERE r.id = ?
    """, (receipt_id,)).fetchone()
    if not row:
        raise HTTPException(404, "入库单不存在")
    lines = db.execute("""
        SELECT rl.id, rl.material_id, m.sku, m.name AS material_name, m.unit, rl.quantity
        FROM receipt_lines rl JOIN materials m ON m.id = rl.material_id
        WHERE rl.receipt_id = ? ORDER BY rl.id
    """, (receipt_id,)).fetchall()
    return {**dict(row), "lines": [dict(line) for line in lines]}


@app.get("/api/v1/health", response_model=HealthResponse, tags=["health"])
def health() -> HealthResponse:
    # 健康检查仅说明进程存活，不向未登录用户透露业务数据。
    return HealthResponse(status="ok", service="nexora-api", version=app.version)


@app.get("/api/v1/setup/status")
def setup_status() -> dict:
    with connection() as db:
        return {"needs_setup": db.execute("SELECT NOT EXISTS(SELECT 1 FROM users)").fetchone()[0] == 1}


@app.get("/api/v1/server/info")
def server_info() -> dict:
    # 发现阶段只公开实例身份和兼容版本，不返回用户或业务资料。
    with connection() as db:
        row = db.execute("SELECT id, name FROM server_identity LIMIT 1").fetchone()
        return {"id": row["id"], "name": row["name"], "version": app.version,
                "ready": db.execute("SELECT EXISTS(SELECT 1 FROM users)").fetchone()[0] == 1}


@app.post("/api/v1/setup/admin", status_code=201)
def bootstrap_admin(payload: AccountInput, request: Request) -> dict:
    # 首次管理员只能由本机调用，防止服务刚启动时被局域网中的其他设备抢注。
    try:
        client_ip = ipaddress.ip_address(request.client.host)
    except (AttributeError, ValueError):
        raise HTTPException(403, "只能在服务端本机创建首位管理员") from None
    if not client_ip.is_loopback:
        raise HTTPException(403, "只能在服务端本机创建首位管理员")
    with connection() as db:
        # 写锁保证两个同时发起的首次创建请求只能成功一个。
        db.execute("BEGIN IMMEDIATE")
        if db.execute("SELECT 1 FROM users LIMIT 1").fetchone():
            raise HTTPException(409, "管理员已经创建")
        cursor = db.execute("INSERT INTO users(username, password_hash) VALUES (?, ?)",
                            (payload.username.lower(), hash_password(payload.password)))
        db.execute("INSERT INTO user_roles(user_id, role_code) VALUES (?, 'admin')", (cursor.lastrowid,))
        return user_details(db, cursor.lastrowid)


@app.post("/api/v1/auth/login")
def login(payload: LoginInput) -> dict:
    with connection() as db:
        row = db.execute("SELECT id, password_hash FROM users WHERE username = ?",
                         (payload.username.lower(),)).fetchone()
        if not row or not verify_password(payload.password, row["password_hash"]):
            raise HTTPException(401, "用户名或密码错误")
        token = secrets.token_urlsafe(32)
        # 会话十二小时后过期；重新登录会得到独立令牌。
        db.execute("INSERT INTO sessions(token_hash, user_id, expires_at) VALUES (?, ?, ?)",
                   (token_hash(token), row["id"], int(time.time()) + 12 * 60 * 60))
        return {"token": token, "user": user_details(db, row["id"])}


@app.post("/api/v1/auth/logout", status_code=204)
def logout(credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
           _: dict = Depends(current_user)) -> None:
    with connection() as db:
        db.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash(credentials.credentials),))


@app.get("/api/v1/auth/me")
def me(user: dict = Depends(current_user)) -> dict:
    return user


@app.get("/api/v1/roles")
def list_roles(_: dict = Depends(require("users.manage"))) -> list[dict]:
    with connection() as db:
        return [dict(row) for row in db.execute("SELECT code, label FROM roles ORDER BY code")]


@app.get("/api/v1/users")
def list_users(_: dict = Depends(require("users.manage"))) -> list[dict]:
    with connection() as db:
        return [user_details(db, row[0]) for row in db.execute("SELECT id FROM users ORDER BY id").fetchall()]


@app.post("/api/v1/users", status_code=201)
def create_user(payload: UserInput, _: dict = Depends(require("users.manage"))) -> dict:
    with connection() as db:
        roles = validate_roles(db, payload.roles)
        try:
            cursor = db.execute("INSERT INTO users(username, password_hash) VALUES (?, ?)",
                                (payload.username.lower(), hash_password(payload.password)))
        except sqlite3.IntegrityError:
            raise HTTPException(409, "用户名已存在") from None
        db.executemany("INSERT INTO user_roles(user_id, role_code) VALUES (?, ?)",
                       [(cursor.lastrowid, role) for role in roles])
        return user_details(db, cursor.lastrowid)


@app.put("/api/v1/users/{user_id}/roles")
def set_user_roles(user_id: int, payload: RolesInput,
                   _: dict = Depends(require("users.manage"))) -> dict:
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        if not db.execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone():
            raise HTTPException(404, "用户不存在")
        roles = validate_roles(db, payload.roles)
        if "admin" not in roles:
            # 最后一位管理员不可撤销，避免系统失去账号管理入口。
            admins = db.execute("SELECT COUNT(*) FROM user_roles WHERE role_code = 'admin'").fetchone()[0]
            is_admin = db.execute("SELECT 1 FROM user_roles WHERE user_id = ? AND role_code = 'admin'",
                                  (user_id,)).fetchone()
            if is_admin and admins <= 1:
                raise HTTPException(409, "至少需要保留一位管理员")
        db.execute("DELETE FROM user_roles WHERE user_id = ?", (user_id,))
        db.executemany("INSERT INTO user_roles(user_id, role_code) VALUES (?, ?)",
                       [(user_id, role) for role in roles])
        return user_details(db, user_id)


@app.get("/api/v1/suppliers")
def list_suppliers(_: dict = Depends(require("inventory.view"))) -> list[dict]:
    with connection() as db:
        return [dict(row) for row in db.execute("SELECT id, name FROM suppliers ORDER BY name")]


@app.post("/api/v1/suppliers", status_code=201)
def create_supplier(payload: SupplierInput, _: dict = Depends(require("catalog.manage"))) -> dict:
    with connection() as db:
        try:
            cursor = db.execute("INSERT INTO suppliers(name) VALUES (?)", (payload.name,))
        except sqlite3.IntegrityError:
            raise HTTPException(409, "供应商已存在") from None
        return {"id": cursor.lastrowid, "name": payload.name}


@app.get("/api/v1/materials")
def list_materials(_: dict = Depends(require("inventory.view"))) -> list[dict]:
    with connection() as db:
        return [dict(row) for row in db.execute("SELECT id, sku, name, unit FROM materials ORDER BY sku")]


@app.post("/api/v1/materials", status_code=201)
def create_material(payload: MaterialInput, _: dict = Depends(require("catalog.manage"))) -> dict:
    with connection() as db:
        try:
            cursor = db.execute("INSERT INTO materials(sku, name, unit) VALUES (?, ?, ?)",
                                (payload.sku, payload.name, payload.unit))
        except sqlite3.IntegrityError:
            raise HTTPException(409, "物料编码已存在") from None
        return {"id": cursor.lastrowid, **payload.model_dump()}


@app.get("/api/v1/receipts")
def list_receipts(_: dict = Depends(require("inventory.view"))) -> list[dict]:
    with connection() as db:
        ids = [row[0] for row in db.execute("SELECT id FROM receipts ORDER BY id DESC")]
        return [receipt_data(db, receipt_id) for receipt_id in ids]


@app.post("/api/v1/receipts", status_code=201)
def create_receipt(payload: ReceiptInput, user: dict = Depends(require("receipt.create"))) -> dict:
    if len({line.material_id for line in payload.lines}) != len(payload.lines):
        raise HTTPException(422, "一张入库单不能重复选择同一物料")
    with connection() as db:
        if not db.execute("SELECT 1 FROM suppliers WHERE id = ?", (payload.supplier_id,)).fetchone():
            raise HTTPException(422, "供应商不存在")
        for line in payload.lines:
            if not db.execute("SELECT 1 FROM materials WHERE id = ?", (line.material_id,)).fetchone():
                raise HTTPException(422, "物料不存在")
        cursor = db.execute("""
            INSERT INTO receipts(supplier_id, reference, created_by) VALUES (?, ?, ?)
        """, (payload.supplier_id, payload.reference.strip(), user["id"]))
        db.executemany("""
            INSERT INTO receipt_lines(receipt_id, material_id, quantity) VALUES (?, ?, ?)
        """, [(cursor.lastrowid, line.material_id, str(line.quantity)) for line in payload.lines])
        return receipt_data(db, cursor.lastrowid)


@app.post("/api/v1/receipts/{receipt_id}/post")
def post_receipt(receipt_id: int, user: dict = Depends(require("receipt.post"))) -> dict:
    with connection() as db:
        # 状态变更和库存流水写入使用同一个写事务，重复确认会返回冲突。
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT status FROM receipts WHERE id = ?", (receipt_id,)).fetchone()
        if not row:
            raise HTTPException(404, "入库单不存在")
        if row["status"] != "draft":
            raise HTTPException(409, "此入库单已经确认")
        db.execute("""
            INSERT INTO stock_movements(material_id, quantity, receipt_line_id)
            SELECT material_id, quantity, id FROM receipt_lines WHERE receipt_id = ?
        """, (receipt_id,))
        db.execute("""
            UPDATE receipts SET status = 'posted', posted_by = ?, posted_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (user["id"], receipt_id))
        return receipt_data(db, receipt_id)


@app.get("/api/v1/stock")
def list_stock(_: dict = Depends(require("inventory.view"))) -> list[dict]:
    with connection() as db:
        # SQLite 的 SUM 会转成浮点数，因此在 Python 中用 Decimal 计算库存。
        quantities: dict[int, Decimal] = {}
        for row in db.execute("SELECT material_id, quantity FROM stock_movements"):
            quantities[row["material_id"]] = quantities.get(row["material_id"], Decimal(0)) + Decimal(row["quantity"])
        return [{**dict(row), "quantity": str(quantities.get(row["id"], Decimal(0)))}
                for row in db.execute("SELECT id, sku, name, unit FROM materials ORDER BY sku")]


@app.get("/api/v1/movements")
def list_movements(_: dict = Depends(require("inventory.view"))) -> list[dict]:
    with connection() as db:
        return [dict(row) for row in db.execute("""
            SELECT sm.id, sm.material_id, m.sku, m.name AS material_name, m.unit,
                   sm.quantity, rl.receipt_id, sm.created_at
            FROM stock_movements sm
            JOIN materials m ON m.id = sm.material_id
            JOIN receipt_lines rl ON rl.id = sm.receipt_line_id
            ORDER BY sm.id DESC
        """)]
