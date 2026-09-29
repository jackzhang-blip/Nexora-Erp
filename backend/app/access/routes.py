"""账号、角色与权限管理接口。"""

import ipaddress
import secrets
import sqlite3
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, field_validator

from app.access.security import bearer, current_user, hash_password, require, token_hash, user_details, verify_password
from app.core.database import connection

router = APIRouter(prefix="/api/v1")


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

@router.post("/setup/admin", status_code=201)
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


@router.post("/auth/login")
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


@router.post("/auth/logout", status_code=204)
def logout(credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
           _: dict = Depends(current_user)) -> None:
    with connection() as db:
        db.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash(credentials.credentials),))


@router.get("/auth/me")
def me(user: dict = Depends(current_user)) -> dict:
    return user


@router.post("/auth/change-password", status_code=204)
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


@router.get("/permissions")
def list_permissions(_: dict = Depends(require("users.manage"))) -> list[dict]:
    # 中文名称和父子关系全部取自数据库；角色授权仍只保存叶子操作的稳定代码。
    with connection() as db:
        rows = db.execute("""SELECT p.code, p.label, m.code AS module_code,
                                   m.label AS module_label, d.code AS document_code,
                                   d.label AS document_label
                            FROM permissions p
                            JOIN permission_groups d ON d.code = p.group_code
                            JOIN permission_groups m ON m.code = d.parent_code
                            ORDER BY m.sort_order, d.sort_order, p.code""")
        return [{"code": row["code"], "label": row["label"], "group_path": [
            {"code": row["module_code"], "label": row["module_label"]},
            {"code": row["document_code"], "label": row["document_label"]},
        ]} for row in rows]


@router.put("/permissions/{code}/label")
def update_permission_label(code: str, payload: PermissionLabelInput,
                            _: dict = Depends(require("users.manage"))) -> dict:
    # 只允许更改展示名称，权限代码与角色授权关系都保持不变。
    with connection() as db:
        updated = db.execute("UPDATE permissions SET label = ? WHERE code = ?",
                             (payload.label, code))
        if updated.rowcount == 0:
            raise HTTPException(404, "权限不存在")
        return {"code": code, "label": payload.label}


@router.get("/roles")
def list_roles(_: dict = Depends(require("users.manage"))) -> list[dict]:
    with connection() as db:
        return [role_details(db, row[0]) for row in db.execute("SELECT code FROM roles ORDER BY code").fetchall()]


@router.post("/roles", status_code=201)
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


@router.put("/roles/{role_code}")
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


@router.get("/users")
def list_users(_: dict = Depends(require("users.manage"))) -> list[dict]:
    with connection() as db:
        return [user_details(db, row[0]) for row in db.execute("SELECT id FROM users ORDER BY id").fetchall()]


@router.post("/users", status_code=201)
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


@router.put("/users/{user_id}/roles")
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


@router.put("/users/{user_id}/status")
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


@router.post("/users/{user_id}/reset-password", status_code=204)
def reset_user_password(user_id: int, payload: PasswordInput,
                        _: dict = Depends(require("users.manage"))) -> None:
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        if not db.execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone():
            raise HTTPException(404, "用户不存在")
        db.execute("UPDATE users SET password_hash = ? WHERE id = ?",
                   (hash_password(payload.password), user_id))
        db.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
