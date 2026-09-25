"""验证用户生命周期和自定义角色在真实 SQLite 会话中的授权行为。"""

from fastapi.testclient import TestClient

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
        worker_data = client.post(f"{base}/users", headers=admin, json={
            "username": "worker", "password": "worker-password-123", "roles": ["viewer"]
        }).json()
        worker = login("worker", "worker-password-123")
        assert worker_data["is_active"] is True
        assert client.get(f"{base}/permissions", headers=worker).status_code == 403
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
