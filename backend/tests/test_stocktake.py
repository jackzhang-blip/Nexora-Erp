"""验证盘点差异只经确认单据入账，并拒绝过时快照和越权操作。"""

from fastapi.testclient import TestClient

from app.main import app


def test_stocktake_adjustment_stale_count_and_permissions(monkeypatch, tmp_path):
    monkeypatch.setenv("NEXORA_DB_PATH", str(tmp_path / "stocktake.db"))
    with TestClient(app, client=("127.0.0.1", 12000)) as client:
        base = "/api/v1"
        client.post(f"{base}/setup/admin", json={"username": "admin", "password": "secure-pass-123"})
        token = client.post(f"{base}/auth/login", json={
            "username": "admin", "password": "secure-pass-123"}).json()["token"]
        admin = {"Authorization": f"Bearer {token}"}
        client.post(f"{base}/users", headers=admin, json={
            "username": "viewer", "password": "secure-pass-123", "roles": ["viewer"]})
        viewer_token = client.post(f"{base}/auth/login", json={
            "username": "viewer", "password": "secure-pass-123"}).json()["token"]
        view = {"Authorization": f"Bearer {viewer_token}"}
        supplier = client.post(f"{base}/suppliers", headers=admin, json={"name": "供应商"}).json()["id"]
        material = client.post(f"{base}/materials", headers=admin, json={
            "sku": "COUNT", "name": "盘点物料", "unit": "件"}).json()["id"]
        receipt = client.post(f"{base}/receipts", headers=admin, json={
            "supplier_id": supplier, "lines": [{"material_id": material, "quantity": "3.125"}]}).json()["id"]
        client.post(f"{base}/receipts/{receipt}/post", headers=admin)
        warehouse = client.post(f"{base}/warehouses", headers=admin, json={
            "code": "SECOND", "name": "第二仓"}).json()["id"]

        # 盘点仅调整目标仓；草稿保留建单时的账面量与实盘量。
        payload = {"warehouse_id": 1, "reference": "月末盘点",
                   "lines": [{"material_id": material, "counted_quantity": "2.125"}]}
        assert client.post(f"{base}/stocktakes", headers=view, json=payload).status_code == 403
        assert client.post(f"{base}/stocktakes", headers=admin, json={
            **payload, "lines": payload["lines"] * 2}).status_code == 422
        assert client.post(f"{base}/stocktakes", headers=admin, json={
            **payload, "lines": [{"material_id": material, "counted_quantity": "1.0001"}]}).status_code == 422
        draft = client.post(f"{base}/stocktakes", headers=admin, json=payload)
        assert draft.status_code == 201
        stocktake_id = draft.json()["id"]
        assert draft.json()["lines"][0]["book_quantity"] == "3.125"
        assert draft.json()["lines"][0]["difference"] == "-1.000"
        assert client.post(f"{base}/stocktakes/{stocktake_id}/post", headers=view).status_code == 403
        assert client.post(f"{base}/stocktakes/{stocktake_id}/post", headers=admin).status_code == 200
        assert client.post(f"{base}/stocktakes/{stocktake_id}/post", headers=admin).status_code == 409
        assert client.post(f"{base}/stocktakes/{stocktake_id}/cancel", headers=admin).status_code == 409
        assert client.get(f"{base}/stock?warehouse_id=1", headers=view).json()[0]["quantity"] == "2.125"
        movements = client.get(f"{base}/movements", headers=view).json()
        assert movements[0]["source_type"] == "stocktake"
        assert movements[0]["stocktake_id"] == stocktake_id
        assert movements[0]["quantity"] == "-1.000"
        assert movements[0]["created_by"] is not None

        # 草稿之后的调拨会改变账面量；旧盘点不得吞掉调拨流水。
        stale = client.post(f"{base}/stocktakes", headers=admin, json=payload).json()["id"]
        transfer = client.post(f"{base}/transfers", headers=admin, json={
            "from_warehouse_id": 1, "to_warehouse_id": warehouse,
            "lines": [{"material_id": material, "quantity": "0.125"}]}).json()["id"]
        assert client.post(f"{base}/transfers/{transfer}/post", headers=admin).status_code == 200
        assert client.post(f"{base}/stocktakes/{stale}/post", headers=admin).status_code == 409
        assert client.post(f"{base}/stocktakes/{stale}/cancel", headers=admin).status_code == 200
        assert client.get(f"{base}/stock?warehouse_id=1", headers=view).json()[0]["quantity"] == "2.000"
        assert client.get(f"{base}/stock?warehouse_id={warehouse}", headers=view).json()[0]["quantity"] == "0.125"
        assert client.get(f"{base}/stocktakes", headers=view).json()[0]["status"] == "cancelled"

        # 无差异盘点可确认，但不制造一笔零数量流水。
        before = len(client.get(f"{base}/movements", headers=view).json())
        zero = client.post(f"{base}/stocktakes", headers=admin, json={
            "warehouse_id": warehouse, "lines": [{"material_id": material,
                                                     "counted_quantity": "0.125"}]}).json()["id"]
        assert client.post(f"{base}/stocktakes/{zero}/post", headers=admin).status_code == 200
        assert len(client.get(f"{base}/movements", headers=view).json()) == before

        # 出入相抵后余额虽未变，旧实盘仍不应覆盖期间发生的交易。
        unchanged_balance = client.post(f"{base}/stocktakes", headers=admin, json={
            "warehouse_id": 1, "lines": [{"material_id": material,
                                            "counted_quantity": "2.000"}]}).json()["id"]
        for source, target in ((1, warehouse), (warehouse, 1)):
            move = client.post(f"{base}/transfers", headers=admin, json={
                "from_warehouse_id": source, "to_warehouse_id": target,
                "lines": [{"material_id": material, "quantity": "0.125"}]}).json()["id"]
            assert client.post(f"{base}/transfers/{move}/post", headers=admin).status_code == 200
        assert client.get(f"{base}/stock?warehouse_id=1", headers=view).json()[0]["quantity"] == "2.000"
        assert client.post(f"{base}/stocktakes/{unchanged_balance}/post", headers=admin).status_code == 409
