"""Nexora ERP 本地业务 API。"""

import secrets
import sqlite3
import time
import ipaddress
import asyncio
import logging
import os
from contextlib import asynccontextmanager
from decimal import Decimal

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, field_validator

from .database import connection, migrate
from .discovery import DiscoveryPublisher
from .finance import router as finance_router
from .inventory import balance, require_warehouse, router as inventory_router
from .purchase import (linked_order_for_receipt, order_receipt_lines,
                       router as purchase_router, update_order_receipt_status, validate_receipt_post)
from .purchase_returns import returned_quantity as purchase_returned_quantity, router as purchase_returns_router
from .production import router as production_router
from .sales import router as sales_router
from .sales_returns import router as sales_returns_router
from .stocktake import router as stocktake_router
from .work_orders import router as work_orders_router
from .material_issues import router as material_issues_router
from .material_returns import router as material_returns_router
from .production_completions import router as production_completions_router
from .production_costs import router as production_costs_router
from .security import bearer, current_user, hash_password, require, token_hash, user_details, verify_password


@asynccontextmanager
async def lifespan(_: FastAPI):
    # 启动时检查并升级本地数据库；不依赖桌面页面是否已经打开。
    migrate()
    publisher = None
    task = None
    port = os.environ.get("NEXORA_DISCOVERY_PORT")
    if port is not None:
        with connection() as db:
            instance_id = db.execute("SELECT id FROM server_identity LIMIT 1").fetchone()[0]
        publisher = DiscoveryPublisher(instance_id, "0.1.0", int(port))

        async def publish_periodically():
            # 系统服务可能早于网卡启动；重复检查也能处理 IP 地址变化。
            while True:
                try:
                    await asyncio.to_thread(publisher.sync)
                except Exception:
                    logging.getLogger(__name__).exception("局域网发现状态更新失败")
                await asyncio.sleep(15)

        task = asyncio.create_task(publish_periodically())
    try:
        yield
    finally:
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        if publisher is not None:
            await asyncio.to_thread(publisher.close)


app = FastAPI(title="Nexora ERP API", version="0.1.0", lifespan=lifespan)
app.include_router(inventory_router)
app.include_router(purchase_router)
app.include_router(purchase_returns_router)
app.include_router(finance_router)
app.include_router(production_router)
app.include_router(work_orders_router)
app.include_router(material_issues_router)
app.include_router(material_returns_router)
app.include_router(production_completions_router)
app.include_router(production_costs_router)
app.include_router(stocktake_router)
app.include_router(sales_router)
app.include_router(sales_returns_router)


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


class RoleInput(BaseModel):
    code: str = Field(min_length=3, max_length=40, pattern=r"^[a-z][a-z0-9_]*$")
    label: str = Field(min_length=1, max_length=40)
    permissions: list[str]

    @field_validator("label")
    @classmethod
    def trim_label(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("角色名称不能为空")
        return value.strip()


class RoleUpdate(BaseModel):
    label: str = Field(min_length=1, max_length=40)
    permissions: list[str]

    @field_validator("label")
    @classmethod
    def trim_label(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("角色名称不能为空")
        return value.strip()


class PermissionLabelInput(BaseModel):
    label: str = Field(min_length=1, max_length=60)

    @field_validator("label")
    @classmethod
    def trim_label(cls, value: str) -> str:
        label = value.strip()
        # 授权列表面对中文用户，名称至少包含一个汉字，避免再次显示纯英文代码。
        if not label or not any("\u4e00" <= char <= "\u9fff" for char in label):
            raise ValueError("权限名称须包含中文")
        return label


class StatusInput(BaseModel):
    is_active: bool


class PasswordInput(BaseModel):
    password: str = Field(min_length=12, max_length=128)


class ChangePasswordInput(BaseModel):
    current_password: str
    new_password: str = Field(min_length=12, max_length=128)


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
    # 老客户端省略仓库时继续入主仓库；新客户端必须让用户明确选择。
    warehouse_id: int = Field(default=1, gt=0)
    purchase_order_id: int | None = Field(default=None, gt=0)
    reference: str = Field(default="", max_length=100)
    lines: list[ReceiptLineInput] = Field(min_length=1, max_length=100)


class ReceiptReverseInput(BaseModel):
    reason: str = Field(min_length=1, max_length=200)

    @field_validator("reason")
    @classmethod
    def trim_reason(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("冲销原因不能为空")
        return value.strip()


def validate_roles(db: sqlite3.Connection, roles: list[str]) -> list[str]:
    unique = sorted(set(roles))
    known = {row[0] for row in db.execute("SELECT code FROM roles")}
    if not unique or not set(unique) <= known:
        raise HTTPException(422, "角色无效")
    return unique


def validate_permissions(db: sqlite3.Connection, permissions: list[str]) -> list[str]:
    # 权限只能从服务端固定登记表选择，客户端不能创造任意权限代码。
    unique = sorted(set(permissions))
    known = {row[0] for row in db.execute("SELECT code FROM permissions")}
    if not set(unique) <= known:
        raise HTTPException(422, "权限代码无效")
    return unique


def role_details(db: sqlite3.Connection, code: str) -> dict:
    role = db.execute("SELECT code, label, is_builtin FROM roles WHERE code = ?", (code,)).fetchone()
    if not role:
        raise HTTPException(404, "角色不存在")
    permissions = [row[0] for row in db.execute(
        "SELECT permission_code FROM role_permissions WHERE role_code = ? ORDER BY permission_code", (code,))]
    return {"code": role["code"], "label": role["label"], "is_builtin": bool(role["is_builtin"]),
            "permissions": permissions}


def ensure_active_admin_remains(db: sqlite3.Connection, user_id: int) -> None:
    # 所有账号管理操作共用同一条约束，保证至少一位启用的内置管理员。
    target = db.execute("""
        SELECT 1 FROM users u JOIN user_roles ur ON ur.user_id = u.id
        WHERE u.id = ? AND u.is_active = 1 AND ur.role_code = 'admin'
    """, (user_id,)).fetchone()
    if not target:
        return
    count = db.execute("""
        SELECT COUNT(*) FROM users u JOIN user_roles ur ON ur.user_id = u.id
        WHERE u.is_active = 1 AND ur.role_code = 'admin'
    """).fetchone()[0]
    if count <= 1:
        raise HTTPException(409, "至少需要保留一位启用的管理员")


def receipt_data(db: sqlite3.Connection, receipt_id: int) -> dict:
    row = db.execute("""
        SELECT r.*, s.name AS supplier_name, u.username AS created_by_name,
               w.id AS warehouse_id, w.name AS warehouse_name,
               rev.id AS reversal_id, rev.reason AS reversal_reason,
               rev.created_by AS reversed_by, ru.username AS reversed_by_name,
               rev.created_at AS reversed_at
        FROM receipts r JOIN suppliers s ON s.id = r.supplier_id
        JOIN users u ON u.id = r.created_by
        JOIN receipt_warehouses rw ON rw.receipt_id = r.id
        JOIN warehouses w ON w.id = rw.warehouse_id
        LEFT JOIN receipt_reversals rev ON rev.receipt_id = r.id
        LEFT JOIN users ru ON ru.id = rev.created_by WHERE r.id = ?
    """, (receipt_id,)).fetchone()
    if not row:
        raise HTTPException(404, "入库单不存在")
    lines = db.execute("""
        SELECT rl.id, rl.material_id, m.sku, m.name AS material_name, m.unit, rl.quantity
        FROM receipt_lines rl JOIN materials m ON m.id = rl.material_id
        WHERE rl.receipt_id = ? ORDER BY rl.id
    """, (receipt_id,)).fetchall()
    detailed_lines = []
    for line in lines:
        # 同一次读取只汇总一次已退量，可退数量只由已确认单据推导。
        returned = purchase_returned_quantity(db, line["id"])
        detailed_lines.append({**dict(line), "returned_quantity": str(returned),
                               "returnable_quantity": str(Decimal(0) if row["reversal_id"] else
                                                          Decimal(line["quantity"]) - returned)})
    return {**dict(row), "purchase_order_id": linked_order_for_receipt(db, receipt_id),
            "lines": detailed_lines}


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
        row = db.execute("SELECT id, password_hash, is_active FROM users WHERE username = ?",
                         (payload.username.lower(),)).fetchone()
        if not row or not row["is_active"] or not verify_password(payload.password, row["password_hash"]):
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


@app.post("/api/v1/auth/change-password", status_code=204)
def change_password(payload: ChangePasswordInput, user: dict = Depends(current_user)) -> None:
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT password_hash FROM users WHERE id = ?", (user["id"],)).fetchone()
        if not verify_password(payload.current_password, row["password_hash"]):
            raise HTTPException(400, "当前密码不正确")
        db.execute("UPDATE users SET password_hash = ? WHERE id = ?",
                   (hash_password(payload.new_password), user["id"]))
        # 改密后所有旧会话立即失效，当前桌面端也须重新登录。
        db.execute("DELETE FROM sessions WHERE user_id = ?", (user["id"],))


@app.get("/api/v1/permissions")
def list_permissions(_: dict = Depends(require("users.manage"))) -> list[dict]:
    # 以数据库权限目录为唯一展示来源；代码只负责后端授权。
    with connection() as db:
        return [dict(row) for row in db.execute("SELECT code, label FROM permissions ORDER BY code")]


@app.put("/api/v1/permissions/{code}/label")
def update_permission_label(code: str, payload: PermissionLabelInput,
                            _: dict = Depends(require("users.manage"))) -> dict:
    # 只允许更改展示名称，权限代码与角色授权关系都保持不变。
    with connection() as db:
        updated = db.execute("UPDATE permissions SET label = ? WHERE code = ?",
                             (payload.label, code))
        if updated.rowcount == 0:
            raise HTTPException(404, "权限不存在")
        return {"code": code, "label": payload.label}


@app.get("/api/v1/roles")
def list_roles(_: dict = Depends(require("users.manage"))) -> list[dict]:
    with connection() as db:
        return [role_details(db, row[0]) for row in db.execute("SELECT code FROM roles ORDER BY code").fetchall()]


@app.post("/api/v1/roles", status_code=201)
def create_role(payload: RoleInput, _: dict = Depends(require("users.manage"))) -> dict:
    with connection() as db:
        permissions = validate_permissions(db, payload.permissions)
        try:
            db.execute("INSERT INTO roles(code, label) VALUES (?, ?)", (payload.code, payload.label))
        except sqlite3.IntegrityError:
            raise HTTPException(409, "角色代码已存在") from None
        db.executemany("INSERT INTO role_permissions(role_code, permission_code) VALUES (?, ?)",
                       [(payload.code, permission) for permission in permissions])
        return role_details(db, payload.code)


@app.put("/api/v1/roles/{role_code}")
def update_role(role_code: str, payload: RoleUpdate, _: dict = Depends(require("users.manage"))) -> dict:
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        role = role_details(db, role_code)
        if role["is_builtin"]:
            raise HTTPException(409, "内置角色不可修改")
        permissions = validate_permissions(db, payload.permissions)
        db.execute("UPDATE roles SET label = ? WHERE code = ?", (payload.label, role_code))
        db.execute("DELETE FROM role_permissions WHERE role_code = ?", (role_code,))
        db.executemany("INSERT INTO role_permissions(role_code, permission_code) VALUES (?, ?)",
                       [(role_code, permission) for permission in permissions])
        # 权限按请求实时查询，更新角色后现有用户会话立即按新权限执行。
        return role_details(db, role_code)


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
            ensure_active_admin_remains(db, user_id)
        db.execute("DELETE FROM user_roles WHERE user_id = ?", (user_id,))
        db.executemany("INSERT INTO user_roles(user_id, role_code) VALUES (?, ?)",
                       [(user_id, role) for role in roles])
        return user_details(db, user_id)


@app.put("/api/v1/users/{user_id}/status")
def set_user_status(user_id: int, payload: StatusInput,
                    _: dict = Depends(require("users.manage"))) -> dict:
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT is_active FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row:
            raise HTTPException(404, "用户不存在")
        if row["is_active"] and not payload.is_active:
            ensure_active_admin_remains(db, user_id)
        db.execute("UPDATE users SET is_active = ? WHERE id = ?", (int(payload.is_active), user_id))
        if not payload.is_active:
            # 停用时撤销全部会话；重新启用后必须输入密码登录。
            db.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        return user_details(db, user_id)


@app.post("/api/v1/users/{user_id}/reset-password", status_code=204)
def reset_user_password(user_id: int, payload: PasswordInput,
                        _: dict = Depends(require("users.manage"))) -> None:
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        if not db.execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone():
            raise HTTPException(404, "用户不存在")
        db.execute("UPDATE users SET password_hash = ? WHERE id = ?",
                   (hash_password(payload.password), user_id))
        db.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))


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
        db.execute("BEGIN IMMEDIATE")
        require_warehouse(db, payload.warehouse_id)
        if not db.execute("SELECT 1 FROM suppliers WHERE id = ?", (payload.supplier_id,)).fetchone():
            raise HTTPException(422, "供应商不存在")
        for line in payload.lines:
            if not db.execute("SELECT 1 FROM materials WHERE id = ?", (line.material_id,)).fetchone():
                raise HTTPException(422, "物料不存在")
        order_line_ids = (order_receipt_lines(db, payload.purchase_order_id, payload.supplier_id,
            [(line.material_id, line.quantity) for line in payload.lines])
            if payload.purchase_order_id is not None else {})
        cursor = db.execute("""
            INSERT INTO receipts(supplier_id, reference, created_by) VALUES (?, ?, ?)
        """, (payload.supplier_id, payload.reference.strip(), user["id"]))
        db.execute("INSERT INTO receipt_warehouses(receipt_id, warehouse_id) VALUES (?, ?)",
                   (cursor.lastrowid, payload.warehouse_id))
        for line in payload.lines:
            line_cursor = db.execute("""INSERT INTO receipt_lines(receipt_id, material_id, quantity)
                VALUES (?, ?, ?)""", (cursor.lastrowid, line.material_id, str(line.quantity)))
            if payload.purchase_order_id is not None:
                db.execute("INSERT INTO receipt_order_links(receipt_line_id, purchase_order_line_id) VALUES (?, ?)",
                           (line_cursor.lastrowid, order_line_ids[line.material_id]))
        return receipt_data(db, cursor.lastrowid)


@app.post("/api/v1/receipts/{receipt_id}/post")
def post_receipt(receipt_id: int, user: dict = Depends(require("receipt.post"))) -> dict:
    with connection() as db:
        # 状态变更和库存流水写入使用同一个写事务，重复确认会返回冲突。
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT status, supplier_id FROM receipts WHERE id = ?", (receipt_id,)).fetchone()
        if not row:
            raise HTTPException(404, "入库单不存在")
        if row["status"] != "draft":
            raise HTTPException(409, "此入库单已经确认")
        order_id = validate_receipt_post(db, receipt_id, row["supplier_id"])
        db.execute("""
            INSERT INTO stock_movements(warehouse_id, material_id, quantity, source_type,
                                        source_id, source_line_id, created_by)
            SELECT rw.warehouse_id, rl.material_id, rl.quantity, 'receipt', ?, rl.id, ?
            FROM receipt_lines rl JOIN receipt_warehouses rw ON rw.receipt_id = rl.receipt_id
            WHERE rl.receipt_id = ?
        """, (receipt_id, user["id"], receipt_id))
        db.execute("""
            UPDATE receipts SET status = 'posted', posted_by = ?, posted_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (user["id"], receipt_id))
        if order_id is not None:
            update_order_receipt_status(db, order_id)
        return receipt_data(db, receipt_id)


@app.post("/api/v1/receipts/{receipt_id}/reverse", status_code=201)
def reverse_receipt(receipt_id: int, payload: ReceiptReverseInput,
                    user: dict = Depends(require("receipt.reverse"))) -> dict:
    with connection() as db:
        # 写锁覆盖退货依赖、当前库存、冲销流水和订单进度，避免并发改变核对结果。
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("""SELECT r.status, rw.warehouse_id FROM receipts r
            JOIN receipt_warehouses rw ON rw.receipt_id = r.id WHERE r.id = ?""",
            (receipt_id,)).fetchone()
        if not row:
            raise HTTPException(404, "入库单不存在")
        if row["status"] != "posted":
            raise HTTPException(409, "只有已确认入库单可冲销")
        if db.execute("SELECT 1 FROM receipt_reversals WHERE receipt_id = ?",
                      (receipt_id,)).fetchone():
            raise HTTPException(409, "此入库单已冲销")
        lines = db.execute("SELECT id, material_id, quantity FROM receipt_lines WHERE receipt_id = ?",
                           (receipt_id,)).fetchall()
        for line in lines:
            if purchase_returned_quantity(db, line["id"]) > 0:
                raise HTTPException(409, "原入库单仍有已确认采购退货，请先冲销退货")
            if balance(db, row["warehouse_id"], line["material_id"]) < Decimal(line["quantity"]):
                raise HTTPException(409, f"原入库仓物料 #{line['material_id']} 库存不足，无法冲销")
        cursor = db.execute("""INSERT INTO receipt_reversals(receipt_id, reason, created_by)
            VALUES (?, ?, ?)""", (receipt_id, payload.reason, user["id"]))
        for line in lines:
            # 保留原正向入库流水，再用关联原明细的负向流水抵消误入库数量。
            db.execute("""INSERT INTO stock_movements(
                warehouse_id, material_id, quantity, source_type, source_id, source_line_id, created_by)
                VALUES (?, ?, ?, 'receipt_reversal', ?, ?, ?)""",
                (row["warehouse_id"], line["material_id"], str(-Decimal(line["quantity"])),
                 cursor.lastrowid, line["id"], user["id"]))
        order_id = linked_order_for_receipt(db, receipt_id)
        if order_id is not None:
            update_order_receipt_status(db, order_id)
        return receipt_data(db, receipt_id)


@app.get("/api/v1/stock")
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


@app.get("/api/v1/movements")
def list_movements(_: dict = Depends(require("inventory.view"))) -> list[dict]:
    with connection() as db:
        return [dict(row) for row in db.execute("""
            SELECT sm.id, sm.warehouse_id, w.name AS warehouse_name,
                   sm.material_id, m.sku, m.name AS material_name, m.unit,
                   sm.quantity, sm.source_type, sm.source_id, sm.source_line_id,
                   CASE WHEN sm.source_type = 'receipt' THEN sm.source_id END AS receipt_id,
                   CASE WHEN sm.source_type = 'receipt_reversal' THEN sm.source_id END AS receipt_reversal_id,
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
