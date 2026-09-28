"""验证多仓库库存、调拨原子性和服务端权限。"""

from fastapi.testclient import TestClient

from app.main import app


def test_multi_warehouse_transfer_and_audit(monkeypatch, tmp_path):
    monkeypatch.setenv("NEXORA_DB_PATH", str(tmp_path / "inventory.db"))
    with TestClient(app, client=("127.0.0.1", 12000)) as client:
        base = "/api/v1"
        client.post(f"{base}/setup/admin", json={"username": "admin", "password": "secure-pass-123"})
        token = client.post(f"{base}/auth/login", json={
            "username": "admin", "password": "secure-pass-123"}).json()["token"]
        admin = {"Authorization": f"Bearer {token}"}
        viewer = client.post(f"{base}/users", headers=admin, json={
            "username": "viewer", "password": "secure-pass-123", "roles": ["viewer"]})
        assert viewer.status_code == 201
        viewer_token = client.post(f"{base}/auth/login", json={
            "username": "viewer", "password": "secure-pass-123"}).json()["token"]
        view = {"Authorization": f"Bearer {viewer_token}"}

        # 创建仓库和入库单必须由服务端检查权限；旧客户端仍默认主仓库。
        assert client.post(f"{base}/warehouses", headers=view, json={
            "code": "EAST", "name": "东仓"}).status_code == 403
        second = client.post(f"{base}/warehouses", headers=admin, json={
            "code": "east", "name": "东仓"})
        assert second.status_code == 201
        assert second.json()["code"] == "EAST"
        assert client.post(f"{base}/warehouses", headers=admin, json={
            "code": "EAST", "name": "重复仓库"}).status_code == 409
        supplier = client.post(f"{base}/suppliers", headers=admin, json={"name": "供应商"}).json()["id"]
        material = client.post(f"{base}/materials", headers=admin, json={
            "sku": "SKU", "name": "物料", "unit": "件"}).json()["id"]
        receipt = client.post(f"{base}/receipts", headers=admin, json={
            "supplier_id": supplier, "lines": [{"material_id": material, "quantity": "2.125"}]})
        assert receipt.status_code == 201
        assert receipt.json()["warehouse_id"] == 1
        assert client.post(f"{base}/receipts/{receipt.json()['id']}/post", headers=admin).status_code == 200

        draft = {"from_warehouse_id": 1, "to_warehouse_id": second.json()["id"],
                 "lines": [{"material_id": material, "quantity": "2.124"}]}
        assert client.post(f"{base}/transfers", headers=view, json=draft).status_code == 403
        assert client.post(f"{base}/transfers", headers=admin, json={
            **draft, "to_warehouse_id": 1}).status_code == 422
        assert client.post(f"{base}/transfers", headers=admin, json={
            **draft, "lines": [{"material_id": material, "quantity": "2.126"}]}).status_code == 201
        insufficient = client.get(f"{base}/transfers", headers=admin).json()[0]["id"]
        assert client.post(f"{base}/transfers/{insufficient}/post", headers=admin).status_code == 409
        assert client.get(f"{base}/stock?warehouse_id=1", headers=view).json()[0]["quantity"] == "2.125"
        assert len(client.get(f"{base}/movements", headers=view).json()) == 1

        transfer = client.post(f"{base}/transfers", headers=admin, json=draft).json()
        assert client.post(f"{base}/transfers/{transfer['id']}/post", headers=view).status_code == 403
        posted = client.post(f"{base}/transfers/{transfer['id']}/post", headers=admin)
        assert posted.status_code == 200
        assert posted.json()["status"] == "posted"
        assert client.post(f"{base}/transfers/{transfer['id']}/post", headers=admin).status_code == 409
        assert client.get(f"{base}/stock?warehouse_id=1", headers=view).json()[0]["quantity"] == "0.001"
        assert client.get(f"{base}/stock?warehouse_id=2", headers=view).json()[0]["quantity"] == "2.124"
        assert client.get(f"{base}/stock", headers=view).json()[0]["quantity"] == "2.125"
        assert client.get(f"{base}/stock?warehouse_id=999", headers=view).status_code == 422
        movements = client.get(f"{base}/movements", headers=view).json()
        assert [item["source_type"] for item in movements] == ["transfer_in", "transfer_out", "receipt"]
        assert [item["quantity"] for item in movements] == ["2.124", "-2.124", "2.125"]
        assert all(item["created_by"] for item in movements)
