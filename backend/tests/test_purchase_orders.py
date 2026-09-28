"""采购订单、分批入库和超量阻断的业务回归。"""

from fastapi.testclient import TestClient

from app.main import app


def test_purchase_order_receipt_lifecycle(monkeypatch, tmp_path):
    monkeypatch.setenv("NEXORA_DB_PATH", str(tmp_path / "orders.db"))
    with TestClient(app, client=("127.0.0.1", 12345)) as client:
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
        supplier = client.post(f"{base}/suppliers", headers=admin, json={"name": "甲供应商"}).json()["id"]
        other_supplier = client.post(f"{base}/suppliers", headers=admin, json={"name": "乙供应商"}).json()["id"]
        material = client.post(f"{base}/materials", headers=admin, json={
            "sku": "A", "name": "物料A", "unit": "件"}).json()["id"]
        other_material = client.post(f"{base}/materials", headers=admin, json={
            "sku": "B", "name": "物料B", "unit": "件"}).json()["id"]
        payload = {"supplier_id": supplier, "reference": "PO-EXT", "lines": [
            {"material_id": material, "quantity": "10.000", "unit_price": "2.3456"}]}

        # 服务端拒绝越权、重复物料及非法单价，草稿不能直接关联入库。
        assert client.post(f"{base}/purchase-orders", headers=view, json=payload).status_code == 403
        assert client.post(f"{base}/purchase-orders", headers=admin, json={
            **payload, "lines": payload["lines"] * 2}).status_code == 422
        assert client.post(f"{base}/purchase-orders", headers=admin, json={
            **payload, "lines": [{**payload["lines"][0], "unit_price": "-1"}]}).status_code == 422
        created = client.post(f"{base}/purchase-orders", headers=admin, json=payload)
        assert created.status_code == 201
        order_id = created.json()["id"]
        assert created.json()["status"] == "draft"
        assert created.json()["total_amount"] == "23.46"
        receipt_input = {"supplier_id": supplier, "warehouse_id": 1, "purchase_order_id": order_id,
                         "lines": [{"material_id": material, "quantity": "6"}]}
        assert client.post(f"{base}/receipts", headers=admin, json=receipt_input).status_code == 409
        assert client.post(f"{base}/purchase-orders/{order_id}/confirm", headers=view).status_code == 403
        assert client.post(f"{base}/purchase-orders/{order_id}/confirm", headers=admin).status_code == 200
        assert client.post(f"{base}/purchase-orders/{order_id}/confirm", headers=admin).status_code == 409
        assert client.post(f"{base}/receipts", headers=admin, json={
            **receipt_input, "supplier_id": other_supplier}).status_code == 422
        assert client.post(f"{base}/receipts", headers=admin, json={
            **receipt_input, "lines": [{"material_id": other_material, "quantity": "1"}]}).status_code == 422
        assert client.post(f"{base}/receipts", headers=admin, json={
            **receipt_input, "lines": [{"material_id": material, "quantity": "11"}]}).status_code == 409

        first = client.post(f"{base}/receipts", headers=admin, json=receipt_input)
        assert first.status_code == 201
        assert first.json()["purchase_order_id"] == order_id
        # 第二张草稿可先创建；确认时须重新计算已入库量，禁止并发草稿超量。
        pending = client.post(f"{base}/receipts", headers=admin, json={
            **receipt_input, "lines": [{"material_id": material, "quantity": "5"}]})
        assert pending.status_code == 201
        assert client.post(f"{base}/receipts/{first.json()['id']}/post", headers=admin).status_code == 200
        assert client.post(f"{base}/receipts/{pending.json()['id']}/post", headers=admin).status_code == 409
        mid = client.get(f"{base}/purchase-orders", headers=view).json()[0]
        assert mid["status"] == "partially_received"
        assert mid["lines"][0]["received_quantity"] == "6"
        assert mid["lines"][0]["remaining_quantity"] == "4.000"
        assert client.post(f"{base}/purchase-orders/{order_id}/cancel", headers=admin).status_code == 409

        final = client.post(f"{base}/receipts", headers=admin, json={
            **receipt_input, "lines": [{"material_id": material, "quantity": "4"}]})
        assert final.status_code == 201
        assert client.post(f"{base}/receipts/{final.json()['id']}/post", headers=admin).status_code == 200
        complete = client.get(f"{base}/purchase-orders", headers=view).json()[0]
        assert complete["status"] == "received"
        assert complete["lines"][0]["remaining_quantity"] == "0.000"
        assert client.get(f"{base}/stock", headers=view).json()[0]["quantity"] == "10"
        assert client.post(f"{base}/receipts", headers=admin, json={
            **receipt_input, "lines": [{"material_id": material, "quantity": "1"}]}).status_code == 409

        # 未入库订单可以取消，取消后不能再确认或入库；单据留存供审计。
        extra = client.post(f"{base}/purchase-orders", headers=admin, json=payload).json()["id"]
        assert client.post(f"{base}/purchase-orders/{extra}/cancel", headers=admin).status_code == 200
        assert client.post(f"{base}/purchase-orders/{extra}/confirm", headers=admin).status_code == 409
