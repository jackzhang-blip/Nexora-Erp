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
        if version > 9:
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
        if version < 4:
            # 为历史入库和库存流水指定主仓库，再把流水改成可记录调拨等来源的通用账本。
            # 迁移全程持有写锁；任一步失败都会回滚，避免出现只有一半仓库字段的数据。
            if not db.in_transaction:
                db.execute("BEGIN IMMEDIATE")
            db.execute("""CREATE TABLE warehouses (
                id INTEGER PRIMARY KEY,
                code TEXT NOT NULL UNIQUE COLLATE NOCASE,
                name TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )""")
            db.execute("INSERT INTO warehouses(id, code, name) VALUES (1, 'MAIN', '主仓库')")
            db.execute("""CREATE TABLE receipt_warehouses (
                receipt_id INTEGER PRIMARY KEY REFERENCES receipts(id),
                warehouse_id INTEGER NOT NULL REFERENCES warehouses(id)
            )""")
            db.execute("INSERT INTO receipt_warehouses(receipt_id, warehouse_id) SELECT id, 1 FROM receipts")
            db.execute("ALTER TABLE stock_movements RENAME TO stock_movements_legacy")
            db.execute("""CREATE TABLE stock_movements (
                id INTEGER PRIMARY KEY,
                warehouse_id INTEGER NOT NULL REFERENCES warehouses(id),
                material_id INTEGER NOT NULL REFERENCES materials(id),
                quantity TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_id INTEGER NOT NULL,
                source_line_id INTEGER NOT NULL,
                created_by INTEGER REFERENCES users(id),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (source_type, source_line_id)
            )""")
            db.execute("""INSERT INTO stock_movements(
                id, warehouse_id, material_id, quantity, source_type, source_id,
                source_line_id, created_by, created_at)
                SELECT sm.id, rw.warehouse_id, sm.material_id, sm.quantity, 'receipt',
                       rl.receipt_id, rl.id, r.posted_by, sm.created_at
                FROM stock_movements_legacy sm
                JOIN receipt_lines rl ON rl.id = sm.receipt_line_id
                JOIN receipts r ON r.id = rl.receipt_id
                JOIN receipt_warehouses rw ON rw.receipt_id = r.id""")
            db.execute("DROP TABLE stock_movements_legacy")
            db.execute("CREATE INDEX stock_movements_balance ON stock_movements(warehouse_id, material_id)")
            db.execute("""CREATE TABLE transfers (
                id INTEGER PRIMARY KEY,
                from_warehouse_id INTEGER NOT NULL REFERENCES warehouses(id),
                to_warehouse_id INTEGER NOT NULL REFERENCES warehouses(id),
                reference TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'posted')),
                created_by INTEGER NOT NULL REFERENCES users(id),
                posted_by INTEGER REFERENCES users(id),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                posted_at TEXT,
                CHECK (from_warehouse_id <> to_warehouse_id)
            )""")
            db.execute("""CREATE TABLE transfer_lines (
                id INTEGER PRIMARY KEY,
                transfer_id INTEGER NOT NULL REFERENCES transfers(id),
                material_id INTEGER NOT NULL REFERENCES materials(id),
                quantity TEXT NOT NULL,
                UNIQUE (transfer_id, material_id)
            )""")
            db.executemany("INSERT INTO permissions(code) VALUES (?)",
                           [(code,) for code in ("warehouse.manage", "transfer.create", "transfer.post")])
            db.executemany("INSERT INTO role_permissions(role_code, permission_code) VALUES (?, ?)",
                           [(role, code) for role in ("admin", "warehouse")
                            for code in ("warehouse.manage", "transfer.create", "transfer.post")])
            db.execute("PRAGMA user_version = 4")
        if version < 5:
            # 采购订单和入库明细使用关联表，历史自由入库单无需改写或猜测订单来源。
            if not db.in_transaction:
                db.execute("BEGIN IMMEDIATE")
            db.execute("""CREATE TABLE purchase_orders (
                id INTEGER PRIMARY KEY,
                supplier_id INTEGER NOT NULL REFERENCES suppliers(id),
                reference TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN
                    ('draft', 'confirmed', 'partially_received', 'received', 'cancelled')),
                created_by INTEGER NOT NULL REFERENCES users(id),
                confirmed_by INTEGER REFERENCES users(id),
                cancelled_by INTEGER REFERENCES users(id),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                confirmed_at TEXT,
                cancelled_at TEXT
            )""")
            db.execute("""CREATE TABLE purchase_order_lines (
                id INTEGER PRIMARY KEY,
                purchase_order_id INTEGER NOT NULL REFERENCES purchase_orders(id),
                material_id INTEGER NOT NULL REFERENCES materials(id),
                quantity TEXT NOT NULL,
                unit_price TEXT NOT NULL,
                UNIQUE (purchase_order_id, material_id)
            )""")
            db.execute("""CREATE TABLE receipt_order_links (
                receipt_line_id INTEGER PRIMARY KEY REFERENCES receipt_lines(id),
                purchase_order_line_id INTEGER NOT NULL REFERENCES purchase_order_lines(id)
            )""")
            db.execute("CREATE INDEX receipt_order_links_order_line ON receipt_order_links(purchase_order_line_id)")
            db.executemany("INSERT INTO permissions(code) VALUES (?)",
                           [(code,) for code in ("purchase_order.create", "purchase_order.confirm",
                                                "purchase_order.cancel")])
            db.executemany("INSERT INTO role_permissions(role_code, permission_code) VALUES (?, ?)",
                           [(role, code) for role in ("admin", "buyer")
                            for code in ("purchase_order.create", "purchase_order.confirm",
                                         "purchase_order.cancel")])
            db.execute("PRAGMA user_version = 5")
        if version < 6:
            # 盘点保存建单时的账面量；确认时若账面量已变化，须重新盘点，避免覆盖期间交易。
            if not db.in_transaction:
                db.execute("BEGIN IMMEDIATE")
            db.execute("""CREATE TABLE stocktakes (
                id INTEGER PRIMARY KEY,
                warehouse_id INTEGER NOT NULL REFERENCES warehouses(id),
                reference TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'posted', 'cancelled')),
                created_by INTEGER NOT NULL REFERENCES users(id),
                posted_by INTEGER REFERENCES users(id),
                cancelled_by INTEGER REFERENCES users(id),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                posted_at TEXT,
                cancelled_at TEXT
            )""")
            db.execute("""CREATE TABLE stocktake_lines (
                id INTEGER PRIMARY KEY,
                stocktake_id INTEGER NOT NULL REFERENCES stocktakes(id),
                material_id INTEGER NOT NULL REFERENCES materials(id),
                book_quantity TEXT NOT NULL,
                counted_quantity TEXT NOT NULL,
                movement_id INTEGER NOT NULL,
                UNIQUE (stocktake_id, material_id)
            )""")
            db.executemany("INSERT INTO permissions(code) VALUES (?)",
                           [(code,) for code in ("stocktake.create", "stocktake.post", "stocktake.cancel")])
            db.executemany("INSERT INTO role_permissions(role_code, permission_code) VALUES (?, ?)",
                           [(role, code) for role in ("admin", "warehouse")
                            for code in ("stocktake.create", "stocktake.post", "stocktake.cancel")])
            db.execute("PRAGMA user_version = 6")
        if version < 7:
            # 销售订单与出库明细独立存储；确认出库时才消耗库存和订单剩余量。
            if not db.in_transaction:
                db.execute("BEGIN IMMEDIATE")
            db.execute("""CREATE TABLE customers (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )""")
            db.execute("""CREATE TABLE sales_orders (
                id INTEGER PRIMARY KEY,
                customer_id INTEGER NOT NULL REFERENCES customers(id),
                reference TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN
                    ('draft', 'confirmed', 'partially_shipped', 'shipped', 'cancelled')),
                created_by INTEGER NOT NULL REFERENCES users(id),
                confirmed_by INTEGER REFERENCES users(id),
                cancelled_by INTEGER REFERENCES users(id),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                confirmed_at TEXT,
                cancelled_at TEXT
            )""")
            db.execute("""CREATE TABLE sales_order_lines (
                id INTEGER PRIMARY KEY,
                sales_order_id INTEGER NOT NULL REFERENCES sales_orders(id),
                material_id INTEGER NOT NULL REFERENCES materials(id),
                quantity TEXT NOT NULL,
                unit_price TEXT NOT NULL,
                UNIQUE (sales_order_id, material_id)
            )""")
            db.execute("""CREATE TABLE shipments (
                id INTEGER PRIMARY KEY,
                sales_order_id INTEGER NOT NULL REFERENCES sales_orders(id),
                warehouse_id INTEGER NOT NULL REFERENCES warehouses(id),
                reference TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'posted', 'cancelled')),
                created_by INTEGER NOT NULL REFERENCES users(id),
                posted_by INTEGER REFERENCES users(id),
                cancelled_by INTEGER REFERENCES users(id),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                posted_at TEXT,
                cancelled_at TEXT
            )""")
            db.execute("""CREATE TABLE shipment_lines (
                id INTEGER PRIMARY KEY,
                shipment_id INTEGER NOT NULL REFERENCES shipments(id),
                sales_order_line_id INTEGER NOT NULL REFERENCES sales_order_lines(id),
                quantity TEXT NOT NULL,
                UNIQUE (shipment_id, sales_order_line_id)
            )""")
            db.execute("CREATE INDEX shipment_lines_order_line ON shipment_lines(sales_order_line_id)")
            db.execute("INSERT INTO roles(code, label, is_builtin) VALUES ('seller', '销售员', 1)")
            db.executemany("INSERT INTO permissions(code) VALUES (?)", [(code,) for code in (
                "sales.view", "customer.manage", "sales_order.create", "sales_order.confirm",
                "sales_order.cancel", "shipment.create", "shipment.post", "shipment.cancel")])
            grants = {"admin": ("sales.view", "customer.manage", "sales_order.create",
                                 "sales_order.confirm", "sales_order.cancel", "shipment.create", "shipment.post",
                                 "shipment.cancel"),
                      "seller": ("inventory.view", "sales.view", "customer.manage", "sales_order.create",
                                 "sales_order.confirm", "sales_order.cancel", "shipment.create", "shipment.cancel"),
                      "warehouse": ("sales.view", "shipment.create", "shipment.post", "shipment.cancel")}
            db.executemany("INSERT INTO role_permissions(role_code, permission_code) VALUES (?, ?)",
                           [(role, permission) for role, permissions in grants.items()
                            for permission in permissions])
            db.execute("PRAGMA user_version = 7")
        if version < 8:
            # 退货单关联原出库明细；保留原负库存流水，确认退货时另记正向流水。
            if not db.in_transaction:
                db.execute("BEGIN IMMEDIATE")
            db.execute("""CREATE TABLE sales_returns (
                id INTEGER PRIMARY KEY,
                shipment_id INTEGER NOT NULL REFERENCES shipments(id),
                warehouse_id INTEGER NOT NULL REFERENCES warehouses(id),
                reason TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'posted', 'cancelled')),
                created_by INTEGER NOT NULL REFERENCES users(id),
                posted_by INTEGER REFERENCES users(id),
                cancelled_by INTEGER REFERENCES users(id),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                posted_at TEXT,
                cancelled_at TEXT
            )""")
            db.execute("""CREATE TABLE sales_return_lines (
                id INTEGER PRIMARY KEY,
                sales_return_id INTEGER NOT NULL REFERENCES sales_returns(id),
                shipment_line_id INTEGER NOT NULL REFERENCES shipment_lines(id),
                quantity TEXT NOT NULL,
                UNIQUE (sales_return_id, shipment_line_id)
            )""")
            db.execute("CREATE INDEX sales_return_lines_shipment ON sales_return_lines(shipment_line_id)")
            db.executemany("INSERT INTO permissions(code) VALUES (?)", [(code,) for code in (
                "sales_return.create", "sales_return.post", "sales_return.cancel")])
            grants = {"admin": ("sales_return.create", "sales_return.post", "sales_return.cancel"),
                      "seller": ("sales_return.create", "sales_return.cancel"),
                      "warehouse": ("sales_return.create", "sales_return.post", "sales_return.cancel")}
            db.executemany("INSERT INTO role_permissions(role_code, permission_code) VALUES (?, ?)",
                           [(role, permission) for role, permissions in grants.items()
                            for permission in permissions])
            db.execute("PRAGMA user_version = 8")
        if version < 9:
            # 采购退货只关联已确认入库明细，原入库与正向流水始终保留。
            if not db.in_transaction:
                db.execute("BEGIN IMMEDIATE")
            db.execute("""CREATE TABLE purchase_returns (
                id INTEGER PRIMARY KEY,
                receipt_id INTEGER NOT NULL REFERENCES receipts(id),
                reason TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'posted', 'cancelled')),
                created_by INTEGER NOT NULL REFERENCES users(id),
                posted_by INTEGER REFERENCES users(id),
                cancelled_by INTEGER REFERENCES users(id),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                posted_at TEXT,
                cancelled_at TEXT
            )""")
            db.execute("""CREATE TABLE purchase_return_lines (
                id INTEGER PRIMARY KEY,
                purchase_return_id INTEGER NOT NULL REFERENCES purchase_returns(id),
                receipt_line_id INTEGER NOT NULL REFERENCES receipt_lines(id),
                quantity TEXT NOT NULL,
                UNIQUE (purchase_return_id, receipt_line_id)
            )""")
            db.execute("CREATE INDEX purchase_return_lines_receipt ON purchase_return_lines(receipt_line_id)")
            db.executemany("INSERT INTO permissions(code) VALUES (?)", [(code,) for code in (
                "purchase_return.create", "purchase_return.post", "purchase_return.cancel")])
            grants = {"admin": ("purchase_return.create", "purchase_return.post", "purchase_return.cancel"),
                      "buyer": ("purchase_return.create", "purchase_return.cancel"),
                      "warehouse": ("purchase_return.create", "purchase_return.post", "purchase_return.cancel")}
            db.executemany("INSERT INTO role_permissions(role_code, permission_code) VALUES (?, ?)",
                           [(role, permission) for role, permissions in grants.items()
                            for permission in permissions])
            db.execute("PRAGMA user_version = 9")
