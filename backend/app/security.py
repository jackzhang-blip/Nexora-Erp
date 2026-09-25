"""账号密码、会话与角色授权。"""

import hashlib
import hmac
import secrets
import time

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .database import connection

bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    # 每个账号使用独立盐值；scrypt 可直接由 Python 标准库提供。
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt$16384$8$1${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, n, r, p, salt, digest = stored.split("$")
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p))
        return hmac.compare_digest(actual, bytes.fromhex(digest))
    except (ValueError, TypeError):
        return False


def token_hash(token: str) -> str:
    # 数据库仅保存令牌摘要，客户端持有的原始令牌不落盘。
    return hashlib.sha256(token.encode()).hexdigest()


def user_details(db, user_id: int) -> dict:
    user = db.execute("SELECT id, username FROM users WHERE id = ?", (user_id,)).fetchone()
    roles = [row[0] for row in db.execute("SELECT role_code FROM user_roles WHERE user_id = ? ORDER BY role_code", (user_id,))]
    permissions = [row[0] for row in db.execute("""
        SELECT DISTINCT rp.permission_code FROM role_permissions rp
        JOIN user_roles ur ON ur.role_code = rp.role_code
        WHERE ur.user_id = ? ORDER BY rp.permission_code
    """, (user_id,))]
    return {"id": user["id"], "username": user["username"], "roles": roles, "permissions": permissions}


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(401, "请先登录")
    with connection() as db:
        row = db.execute("""
            SELECT user_id FROM sessions WHERE token_hash = ? AND expires_at > ?
        """, (token_hash(credentials.credentials), int(time.time()))).fetchone()
        if not row:
            raise HTTPException(401, "登录已失效，请重新登录")
        return user_details(db, row["user_id"])


def require(permission: str):
    # 权限判断始终在服务端执行，界面状态不能替代授权。
    def check(user: dict = Depends(current_user)) -> dict:
        if permission not in user["permissions"]:
            raise HTTPException(403, "没有执行此操作的权限")
        return user
    return check
