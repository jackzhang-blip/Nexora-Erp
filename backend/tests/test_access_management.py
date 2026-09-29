"""验证用户生命周期和权限目录在真实 SQLite 会话中的授权行为。"""

import sqlite3

from fastapi.testclient import TestClient

from app.core.database import connection, migrate
from app.main import app


def test_access_management(monkeypatch, tmp_path):
    monkeypatch.setenv("NEXORA_DB_PATH", str(tmp_path / "access.db"))
    base = "/api/v1"
    with TestClient(app, client=("127.0.0.1", 12345)) as client:
        assert client.post(f"{base}/setup/admin", json={
            "username": "admin", "password": "admin-password-123"
        }).status_code == 201

        def login(username, password):
            response = client.post(f"{base}/auth/login", json={"username": username, "password": password})
            assert response.status_code == 200, response.text
            return {"Authorization": f"Bearer {response.json()['token']}"}

        admin = login("admin", "admin-password-123")
        permissions = client.get(f"{base}/permissions", headers=admin).json()
        # 已登记权限必须都有中文名称；漏配时不可退回编码或笼统的占位文案。
        assert permissions
        assert all(any("\u4e00" <= char <= "\u9fff" for char in item["label"])
                   and item["label"] != item["code"]
                   and not item["label"].startswith("未命名权限") for item in permissions)
        assert len({item["code"] for item in permissions}) == len(permissions)
        renamed = client.put(f"{base}/permissions/inventory.view/label", headers=admin,
                             json={"label": "  查看各仓库存量  "})
        assert renamed.status_code == 200, renamed.text
        assert renamed.json() == {"code": "inventory.view", "label": "查看各仓库存量"}
        with connection() as db:
            # 仅改变展示文案，角色授权继续引用原权限代码。
            assert db.execute("SELECT permission_code FROM role_permissions WHERE role_code = 'viewer'").fetchone()[0] == "inventory.view"
            assert db.execute("SELECT label FROM permissions WHERE code = 'inventory.view'").fetchone()[0] == "查看各仓库存量"
        worker_data = client.post(f"{base}/users", headers=admin, json={
            "username": "worker", "password": "worker-password-123", "roles": ["viewer"]
        }).json()
        worker = login("worker", "worker-password-123")
        assert worker_data["is_active"] is True
        assert client.get(f"{base}/permissions", headers=worker).status_code == 403
        assert client.put(f"{base}/permissions/inventory.view/label", headers=worker,
                          json={"label": "查看库存"}).status_code == 403
        assert client.put(f"{base}/permissions/not_found.view/label", headers=admin,
                          json={"label": "无效权限"}).status_code == 404
        for label in ["  ", "inventory.view", "A" * 61]:
            assert client.put(f"{base}/permissions/inventory.view/label", headers=admin,
                              json={"label": label}).status_code == 422
        assert client.post(f"{base}/roles", headers=worker, json={
            "code": "custom", "label": "自定义", "permissions": []
        }).status_code == 403

        # 自定义角色只接受服务端登记的权限；内置角色禁止修改。
        assert client.post(f"{base}/roles", headers=admin, json={
            "code": "stock_clerk", "label": "库存专员", "permissions": ["unknown.permission"]
        }).status_code == 422
        role = client.post(f"{base}/roles", headers=admin, json={
            "code": "stock_clerk", "label": "库存专员", "permissions": ["inventory.view"]
        })
        assert role.status_code == 201, role.text
        assert role.json()["is_builtin"] is False
        assert client.put(f"{base}/roles/admin", headers=admin, json={
            "label": "管理员", "permissions": []
        }).status_code == 409
        assert client.put(f"{base}/users/{worker_data['id']}/roles", headers=admin,
                          json={"roles": ["stock_clerk"]}).status_code == 200
        material = {"sku": "M-01", "name": "测试物料", "unit": "件"}
        assert client.post(f"{base}/materials", headers=worker, json=material).status_code == 403
        assert client.put(f"{base}/roles/stock_clerk", headers=admin, json={
            "label": "库存资料员", "permissions": ["inventory.view", "catalog.manage"]
        }).status_code == 200
        # 原登录令牌无需重发，服务端每次请求都按最新角色授权。
        assert client.post(f"{base}/materials", headers=worker, json=material).status_code == 201

        # 停用与重置密码都会撤销旧令牌；停用期间不能重新登录。
        assert client.put(f"{base}/users/{worker_data['id']}/status", headers=admin,
                          json={"is_active": False}).json()["is_active"] is False
        assert client.get(f"{base}/stock", headers=worker).status_code == 401
        assert client.post(f"{base}/auth/login", json={
            "username": "worker", "password": "worker-password-123"
        }).status_code == 401
        assert client.put(f"{base}/users/{worker_data['id']}/status", headers=admin,
                          json={"is_active": True}).status_code == 200
        worker = login("worker", "worker-password-123")
        assert client.post(f"{base}/users/{worker_data['id']}/reset-password", headers=admin,
                           json={"password": "new-worker-password-123"}).status_code == 204
        assert client.get(f"{base}/stock", headers=worker).status_code == 401
        assert client.post(f"{base}/auth/login", json={
            "username": "worker", "password": "worker-password-123"
        }).status_code == 401
        worker = login("worker", "new-worker-password-123")
        assert client.post(f"{base}/auth/change-password", headers=worker, json={
            "current_password": "wrong", "new_password": "final-worker-password-123"
        }).status_code == 400
        assert client.get(f"{base}/stock", headers=worker).status_code == 200
        assert client.post(f"{base}/auth/change-password", headers=worker, json={
            "current_password": "new-worker-password-123", "new_password": "final-worker-password-123"
        }).status_code == 204
        assert client.get(f"{base}/stock", headers=worker).status_code == 401
        login("worker", "final-worker-password-123")

        # 停用或撤销管理员权限时，始终保留一位启用的内置管理员。
        assert client.put(f"{base}/users/1/status", headers=admin,
                          json={"is_active": False}).status_code == 409
        second = client.post(f"{base}/users", headers=admin, json={
            "username": "backup", "password": "backup-password-123", "roles": ["admin"]
        }).json()
        backup = login("backup", "backup-password-123")
        assert client.put(f"{base}/users/1/status", headers=backup,
                          json={"is_active": False}).status_code == 200
        assert client.get(f"{base}/users", headers=admin).status_code == 401
        assert client.put(f"{base}/users/{second['id']}/roles", headers=backup,
                          json={"roles": ["viewer"]}).status_code == 409


def test_legacy_permission_codes_gain_labels(monkeypatch, tmp_path):
    path = tmp_path / "legacy-permissions.db"
    monkeypatch.setenv("NEXORA_DB_PATH", str(path))
    with sqlite3.connect(path) as db:
        # 模拟 v24 旧库：权限表只有代码，迁移须保留已有角色关联所用的代码。
        db.execute("CREATE TABLE permissions (code TEXT PRIMARY KEY)")
        db.execute("INSERT INTO permissions(code) VALUES ('bom.activate'), ('future.view')")
        db.execute("PRAGMA user_version = 24")
    migrate()
    with connection() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 25
        assert dict(db.execute("SELECT code, label FROM permissions").fetchall()) == {
            "bom.activate": "启用生产物料清单版本",
            "future.view": "未命名权限",
        }
        # 升级后新增权限必须同时登记中文名称，不再产生裸代码展示。
        try:
            db.execute("INSERT INTO permissions(code) VALUES ('new.view')")
        except sqlite3.IntegrityError:
            pass
        else:
            raise AssertionError("缺少名称的权限不应写入目录")
