import sqlite3

from fastapi.testclient import TestClient

from app.main import app
from app.database import migrate


def test_health_contract(monkeypatch, tmp_path):
    # 健康检查也会触发启动迁移，测试数据库必须与用户数据隔离。
    monkeypatch.setenv("NEXORA_DB_PATH", str(tmp_path / "health.db"))
    with TestClient(app) as client:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json() == {
            "status": "ok", "service": "nexora-api", "version": "0.1.0"
        }


def test_openapi_includes_health_schema(monkeypatch, tmp_path):
    monkeypatch.setenv("NEXORA_DB_PATH", str(tmp_path / "schema.db"))
    with TestClient(app) as client:
        schema = client.get("/openapi.json").json()
        assert "/api/v1/health" in schema["paths"]
        assert "HealthResponse" in schema["components"]["schemas"]


def test_server_identity_persists_and_remote_bootstrap_is_forbidden(monkeypatch, tmp_path):
    # 身份随 SQLite 一起保留，未初始化期间局域网设备不能抢注管理员。
    monkeypatch.setenv("NEXORA_DB_PATH", str(tmp_path / "identity.db"))
    monkeypatch.setenv("NEXORA_INSTANCE_NAME", "测试服务端")
    with TestClient(app, client=("192.168.1.25", 11223)) as remote:
        info = remote.get("/api/v1/server/info").json()
        assert info["name"] == "测试服务端"
        assert info["ready"] is False
        assert remote.post("/api/v1/setup/admin", json={
            "username": "attacker", "password": "secure-pass-123"
        }).status_code == 403
    with TestClient(app, client=("127.0.0.1", 11224)) as local:
        assert local.get("/api/v1/server/info").json()["id"] == info["id"]
        assert local.post("/api/v1/setup/admin", json={
            "username": "admin", "password": "secure-pass-123"
        }).status_code == 201
        assert local.get("/api/v1/server/info").json()["ready"] is True


def test_existing_v1_database_keeps_users(monkeypatch, tmp_path):
    # 升级只新增服务端身份，不能重建或清空上一阶段的业务库。
    database = tmp_path / "existing.db"
    monkeypatch.setenv("NEXORA_DB_PATH", str(database))
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, password_hash TEXT)")
        db.execute("INSERT INTO users VALUES (7, 'existing', 'unchanged')")
        db.execute("PRAGMA user_version = 1")
    migrate()
    with sqlite3.connect(database) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 2
        assert db.execute("SELECT username, password_hash FROM users WHERE id = 7").fetchone() == (
            "existing", "unchanged")
        assert db.execute("SELECT COUNT(*) FROM server_identity").fetchone()[0] == 1
