"""账号、角色与权限管理接口。"""

import ipaddress
import json
import re
import secrets
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, field_validator

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from app.access.security import bearer, current_user, hash_password, require, token_hash, user_details, verify_password
from app.core.models import User, UserRole, Role, RolePermission, Permission, PermissionGroup, AuthSession, UserProfileChange
from app.core.orm import orm_session

router = APIRouter(prefix="/api/v1")


class AccountInput(BaseModel):
    username: str = Field(min_length=3, max_length=40, pattern=r"^[A-Za-z0-9_]+$")
    password: str = Field(min_length=12, max_length=128)


class LoginInput(BaseModel):
    username: str
    password: str


class UserProfileInput(BaseModel):
    # 兼容旧账号和旧客户端；资料可逐步补齐，空工号不参与唯一性约束。
    full_name: str = Field(default="", max_length=60)
    employee_no: str = Field(default="", max_length=40)
    phone: str = Field(default="", max_length=24)

    @field_validator("full_name", "employee_no", "phone", mode="before")
    @classmethod
    def trim_profile(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("employee_no")
    @classmethod
    def validate_employee_no(cls, value: str) -> str:
        if value and not re.fullmatch(r"[A-Za-z0-9_-]+", value):
            raise ValueError("工号仅支持英文、数字、下划线和短横线")
        return value

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        if value and not re.fullmatch(r"\+?[0-9][0-9 ()-]{5,22}[0-9]", value):
            raise ValueError("请输入有效的手机号或带区号的联系电话")
        return value


class UserUpdate(UserProfileInput):
    roles: list[str] = Field(min_length=1)


class UserInput(AccountInput, UserProfileInput):
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


def validate_roles(db: Session, roles: list[str]) -> list[str]:
    unique = sorted(set(roles))
    known = set(db.scalars(select(Role.code)))
    if not unique or not set(unique) <= known:
        raise HTTPException(422, "角色无效")
    return unique


def validate_permissions(db: Session, permissions: list[str]) -> list[str]:
    # 权限只能从服务端固定登记表选择，客户端不能创造任意权限代码。
    unique = sorted(set(permissions))
    known = set(db.scalars(select(Permission.code)))
    if not set(unique) <= known:
        raise HTTPException(422, "权限代码无效")
    return unique


def role_details(db: Session, code: str) -> dict:
    role = db.get(Role, code)
    if role is None:
        raise HTTPException(404, "角色不存在")
    permissions = list(db.scalars(select(RolePermission.permission_code)
        .where(RolePermission.role_code == code).order_by(RolePermission.permission_code)))
    return {"code": role.code, "label": role.label, "is_builtin": bool(role.is_builtin),
            "permissions": permissions}


def ensure_active_admin_remains(db: Session, user_id: int) -> None:
    # 所有账号管理操作共用同一约束，保证至少一位启用的内置管理员。
    admins = select(User.id).join(UserRole, UserRole.user_id == User.id).where(
        User.is_active == 1, UserRole.role_code == 'admin')
    if db.scalar(admins.where(User.id == user_id)) is None:
        return
    if db.scalar(select(func.count()).select_from(admins.subquery())) <= 1:
        raise HTTPException(409, "至少需要保留一位启用的管理员")


def replace_user_roles(db: Session, user_id: int, roles: list[str]) -> None:
    db.execute(delete(UserRole).where(UserRole.user_id == user_id))
    db.add_all([UserRole(user_id=user_id, role_code=role) for role in roles])
    db.flush()


@router.post("/setup/admin", status_code=201)
def bootstrap_admin(payload: AccountInput, request: Request) -> dict:
    # 首次管理员只能由本机调用，防止局域网设备抢注。
    try:
        client_ip = ipaddress.ip_address(request.client.host)
    except (AttributeError, ValueError):
        raise HTTPException(403, "只能在服务端本机创建首位管理员") from None
    if not client_ip.is_loopback:
        raise HTTPException(403, "只能在服务端本机创建首位管理员")
    with orm_session(write=True) as db:
        if db.scalar(select(User.id).limit(1)) is not None:
            raise HTTPException(409, "管理员已经创建")
        account = User(username=payload.username.lower(), password_hash=hash_password(payload.password))
        db.add(account)
        db.flush()
        db.add(UserRole(user_id=account.id, role_code='admin'))
        return user_details(db, account.id)


@router.post("/auth/login")
def login(payload: LoginInput) -> dict:
    with orm_session(write=True) as db:
        row = db.scalar(select(User).where(User.username == payload.username.lower()))
        if row is None or not row.is_active or not verify_password(payload.password, row.password_hash):
            raise HTTPException(401, "用户名或密码错误")
        token = secrets.token_urlsafe(32)
        # 会话十二小时后过期，数据库仅保存令牌摘要。
        db.add(AuthSession(token_hash=token_hash(token), user_id=row.id, expires_at=int(time.time()) + 12 * 60 * 60))
        return {"token": token, "user": user_details(db, row.id)}


@router.post("/auth/logout", status_code=204)
def logout(credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
           _: dict = Depends(current_user)) -> None:
    with orm_session(write=True) as db:
        db.execute(delete(AuthSession).where(AuthSession.token_hash == token_hash(credentials.credentials)))


@router.get("/auth/me")
def me(user: dict = Depends(current_user)) -> dict:
    return user


@router.post("/auth/change-password", status_code=204)
def change_password(payload: ChangePasswordInput, user: dict = Depends(current_user)) -> None:
    with orm_session(write=True) as db:
        account = db.get(User, user['id'])
        if not verify_password(payload.current_password, account.password_hash):
            raise HTTPException(400, "当前密码不正确")
        account.password_hash = hash_password(payload.new_password)
        # 改密后所有旧会话立即失效，当前桌面端也须重新登录。
        db.execute(delete(AuthSession).where(AuthSession.user_id == user['id']))


@router.get("/permissions")
def list_permissions(_: dict = Depends(require("users.manage"))) -> list[dict]:
    # 中文名称和父子关系全部取自数据库，角色只保存叶子操作的稳定代码。
    with orm_session() as db:
        document, module = aliased(PermissionGroup), aliased(PermissionGroup)
        rows = db.execute(select(Permission, document, module)
            .join(document, document.code == Permission.group_code)
            .join(module, module.code == document.parent_code)
            .order_by(module.sort_order, document.sort_order, Permission.code))
        return [{"code": permission.code, "label": permission.label, "group_path": [
            {"code": group.code, "label": group.label}, {"code": doc.code, "label": doc.label}
        ]} for permission, doc, group in rows]


@router.put("/permissions/{code}/label")
def update_permission_label(code: str, payload: PermissionLabelInput,
                            _: dict = Depends(require("users.manage"))) -> dict:
    with orm_session(write=True) as db:
        permission = db.get(Permission, code)
        if permission is None:
            raise HTTPException(404, "权限不存在")
        permission.label = payload.label
        return {"code": code, "label": payload.label}


@router.get("/roles")
def list_roles(_: dict = Depends(require("users.manage"))) -> list[dict]:
    with orm_session() as db:
        return [role_details(db, code) for code in db.scalars(select(Role.code).order_by(Role.code))]


@router.post("/roles", status_code=201)
def create_role(payload: RoleInput, _: dict = Depends(require("users.manage"))) -> dict:
    with orm_session(write=True) as db:
        permissions = validate_permissions(db, payload.permissions)
        try:
            db.add(Role(code=payload.code, label=payload.label))
            db.flush()
        except IntegrityError:
            raise HTTPException(409, "角色代码已存在") from None
        db.add_all([RolePermission(role_code=payload.code, permission_code=code) for code in permissions])
        return role_details(db, payload.code)


@router.put("/roles/{role_code}")
def update_role(role_code: str, payload: RoleUpdate, _: dict = Depends(require("users.manage"))) -> dict:
    with orm_session(write=True) as db:
        role = db.get(Role, role_code)
        if role is None:
            raise HTTPException(404, "角色不存在")
        if role.is_builtin:
            raise HTTPException(409, "内置角色不可修改")
        permissions = validate_permissions(db, payload.permissions)
        role.label = payload.label
        db.execute(delete(RolePermission).where(RolePermission.role_code == role_code))
        db.add_all([RolePermission(role_code=role_code, permission_code=code) for code in permissions])
        # 权限按请求实时查询，原会话无需重发令牌。
        return role_details(db, role_code)


@router.get("/users")
def list_users(_: dict = Depends(require("users.manage"))) -> list[dict]:
    with orm_session() as db:
        return [user_details(db, value) for value in db.scalars(select(User.id).order_by(User.id))]


@router.post("/users", status_code=201)
def create_user(payload: UserInput, _: dict = Depends(require("users.manage"))) -> dict:
    with orm_session(write=True) as db:
        roles = validate_roles(db, payload.roles)
        account = User(username=payload.username.lower(), password_hash=hash_password(payload.password),
            full_name=payload.full_name, employee_no=payload.employee_no, phone=payload.phone)
        try:
            db.add(account)
            db.flush()
        except IntegrityError:
            raise HTTPException(409, "用户名或工号已存在") from None
        db.add_all([UserRole(user_id=account.id, role_code=role) for role in roles])
        return user_details(db, account.id)


@router.put("/users/{user_id}")
def update_user(user_id: int, payload: UserUpdate,
                actor: dict = Depends(require("users.manage"))) -> dict:
    with orm_session(write=True) as db:
        # 资料、角色和审计在同一事务，任一校验失败均回滚。
        account = db.get(User, user_id)
        if account is None:
            raise HTTPException(404, "用户不存在")
        before = user_details(db, user_id)
        roles = validate_roles(db, payload.roles)
        if "admin" not in roles:
            ensure_active_admin_remains(db, user_id)
        try:
            account.full_name, account.employee_no, account.phone = payload.full_name, payload.employee_no, payload.phone
            db.flush()
        except IntegrityError:
            raise HTTPException(409, "工号已存在") from None
        replace_user_roles(db, user_id, roles)
        after = user_details(db, user_id)
        db.add(UserProfileChange(user_id=user_id, changed_by=actor['id'],
            before_json=json.dumps(before, ensure_ascii=False), after_json=json.dumps(after, ensure_ascii=False)))
        return after


@router.put("/users/{user_id}/roles")
def set_user_roles(user_id: int, payload: RolesInput,
                   _: dict = Depends(require("users.manage"))) -> dict:
    with orm_session(write=True) as db:
        if db.get(User, user_id) is None:
            raise HTTPException(404, "用户不存在")
        roles = validate_roles(db, payload.roles)
        if "admin" not in roles:
            ensure_active_admin_remains(db, user_id)
        replace_user_roles(db, user_id, roles)
        return user_details(db, user_id)


@router.put("/users/{user_id}/status")
def set_user_status(user_id: int, payload: StatusInput,
                    _: dict = Depends(require("users.manage"))) -> dict:
    with orm_session(write=True) as db:
        account = db.get(User, user_id)
        if account is None:
            raise HTTPException(404, "用户不存在")
        if account.is_active and not payload.is_active:
            ensure_active_admin_remains(db, user_id)
        account.is_active = int(payload.is_active)
        if not payload.is_active:
            # 停用时撤销全部会话，重新启用后必须登录。
            db.execute(delete(AuthSession).where(AuthSession.user_id == user_id))
        return user_details(db, user_id)


@router.post("/users/{user_id}/reset-password", status_code=204)
def reset_user_password(user_id: int, payload: PasswordInput,
                        _: dict = Depends(require("users.manage"))) -> None:
    with orm_session(write=True) as db:
        account = db.get(User, user_id)
        if account is None:
            raise HTTPException(404, "用户不存在")
        account.password_hash = hash_password(payload.password)
        db.execute(delete(AuthSession).where(AuthSession.user_id == user_id))
