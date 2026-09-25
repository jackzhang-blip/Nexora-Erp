"""本地 SQLite 连接与版本迁移。"""

import os
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


def database_path() -> Path:
    # 测试和部署可覆盖路径；默认数据放在用户目录，避免写入安装目录。
    return Path(os.environ.get("NEXORA_DB_PATH", Path.home() / ".nexora-erp" / "nexora.db"))


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    db = sqlite3.connect(path, timeout=10)
    if os.name != "nt":
        # ERP 业务数据库仅允许当前系统用户读取，即使数据目录位于共享父目录。
        os.chmod(path, 0o600)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA busy_timeout = 10000")
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def migrate() -> None:
    with connection() as db:
        version = db.execute("PRAGMA user_version").fetchone()[0]
        if version > 3:
            raise RuntimeError(f"数据库版本 {version} 高于当前程序支持的版本")
        if version == 0:
            # 整个初始迁移放在一个事务中，避免中途失败留下半套表。
            db.executescript("""
            BEGIN IMMEDIATE;
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE roles (
                code TEXT PRIMARY KEY,
                label TEXT NOT NULL
            );
            CREATE TABLE permissions (
                code TEXT PRIMARY KEY
            );
            CREATE TABLE role_permissions (
                role_code TEXT NOT NULL REFERENCES roles(code),
                permission_code TEXT NOT NULL REFERENCES permissions(code),
                PRIMARY KEY (role_code, permission_code)
            );
            CREATE TABLE user_roles (
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                role_code TEXT NOT NULL REFERENCES roles(code),
                PRIMARY KEY (user_id, role_code)
            );
            CREATE TABLE sessions (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                expires_at INTEGER NOT NULL
            );
            CREATE TABLE suppliers (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE materials (
                id INTEGER PRIMARY KEY,
                sku TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                unit TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE receipts (
                id INTEGER PRIMARY KEY,
                supplier_id INTEGER NOT NULL REFERENCES suppliers(id),
                reference TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'posted')),
                created_by INTEGER NOT NULL REFERENCES users(id),
                posted_by INTEGER REFERENCES users(id),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                posted_at TEXT
            );
            CREATE TABLE receipt_lines (
                id INTEGER PRIMARY KEY,
                receipt_id INTEGER NOT NULL REFERENCES receipts(id),
                material_id INTEGER NOT NULL REFERENCES materials(id),
                quantity TEXT NOT NULL,
                UNIQUE (receipt_id, material_id)
            );
            CREATE TABLE stock_movements (
                id INTEGER PRIMARY KEY,
                material_id INTEGER NOT NULL REFERENCES materials(id),
                quantity TEXT NOT NULL,
                receipt_line_id INTEGER NOT NULL UNIQUE REFERENCES receipt_lines(id),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            INSERT INTO roles(code, label) VALUES
                ('admin', '管理员'), ('buyer', '采购员'),
                ('warehouse', '仓库员'), ('viewer', '查看员');
            INSERT INTO permissions(code) VALUES
                ('users.manage'), ('catalog.manage'), ('inventory.view'),
                ('receipt.create'), ('receipt.post');
            INSERT INTO role_permissions(role_code, permission_code) VALUES
                ('admin', 'users.manage'), ('admin', 'catalog.manage'),
                ('admin', 'inventory.view'), ('admin', 'receipt.create'),
                ('admin', 'receipt.post'),
                ('buyer', 'catalog.manage'), ('buyer', 'inventory.view'),
                ('buyer', 'receipt.create'),
                ('warehouse', 'catalog.manage'), ('warehouse', 'inventory.view'),
                ('warehouse', 'receipt.post'),
                ('viewer', 'inventory.view');
            PRAGMA user_version = 1;
            COMMIT;
            """)
        if version < 2:
            # 服务端身份与业务数据库一起保存，升级旧数据库不会改变任何业务记录。
            db.execute("BEGIN IMMEDIATE")
            db.execute("CREATE TABLE server_identity (id TEXT PRIMARY KEY, name TEXT NOT NULL)")
            db.execute("INSERT INTO server_identity(id, name) VALUES (?, ?)",
                       (str(uuid.uuid4()), os.environ.get("NEXORA_INSTANCE_NAME", "Nexora ERP 服务端")))
            db.execute("PRAGMA user_version = 2")
            db.commit()
        if version < 3:
            # 旧用户默认保持启用；内置角色标记为只读，避免误改造成全员权限漂移。
            db.execute("BEGIN IMMEDIATE")
            db.execute("ALTER TABLE users ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))")
            db.execute("ALTER TABLE roles ADD COLUMN is_builtin INTEGER NOT NULL DEFAULT 0 CHECK (is_builtin IN (0, 1))")
            db.execute("UPDATE roles SET is_builtin = 1 WHERE code IN ('admin', 'buyer', 'warehouse', 'viewer')")
            db.execute("PRAGMA user_version = 3")
