"""验证销售退货关联原出库、累计可退量和库存流水原子性。"""

from fastapi.testclient import TestClient

from app.main import app


def test_sales_returns_partial_and_over_return(monkeypatch, tmp_path):
    monkeypatch.setenv("NEXORA_DB_PATH", str(tmp_path / "returns.db"))
    with TestClient(app, client=("127.0.0.1", 12000)) as client:
        base = "/api/v1"
        client.post(f"{base}/setup/admin", json={"username": "admin", "password": "secure-pass-123"})

        def login(username: str) -> dict:
            token = client.post(f"{base}/auth/login", json={
                "username": username, "password": "secure-pass-123"}).json()["token"]
            return {"Authorization": f"Bearer {token}"}

        admin = login("admin")
        for username, role in (("seller", "seller"), ("warehouse", "warehouse"), ("viewer", "viewer")):
            client.post(f"{base}/users", headers=admin, json={
                "username": username, "password": "secure-pass-123", "roles": [role]})
        seller, warehouse, viewer = login("seller"), login("warehouse"), login("viewer")
        customer = client.post(f"{base}/customers", headers=admin, json={"name": "客户甲"}).json()["id"]
        supplier = client.post(f"{base}/suppliers", headers=admin, json={"name": "供应商"}).json()["id"]
        material = client.post(f"{base}/materials", headers=admin, json={
            "sku": "RETURN", "name": "退货物料", "unit": "件"}).json()["id"]
        second = client.post(f"{base}/warehouses", headers=admin, json={
            "code": "RETURN", "name": "退货仓"}).json()["id"]
        receipt = client.post(f"{base}/receipts", headers=admin, json={
            "supplier_id": supplier, "lines": [{"material_id": material, "quantity": "2.125"}]}).json()["id"]
        client.post(f"{base}/receipts/{receipt}/post", headers=admin)
        order = client.post(f"{base}/sales-orders", headers=seller, json={
            "customer_id": customer, "lines": [{"material_id": material,
                                                  "quantity": "2.125", "unit_price": "10.0000"}]}).json()["id"]
        client.post(f"{base}/sales-orders/{order}/confirm", headers=seller)
        shipment = client.post(f"{base}/shipments", headers=warehouse, json={
            "sales_order_id": order, "warehouse_id": 1,
            "lines": [{"material_id": material, "quantity": "2.125"}]}).json()
        shipment_id = shipment["id"]
        line_id = shipment["lines"][0]["id"]
        payload = {"shipment_id": shipment_id, "warehouse_id": second, "reason": "客户退回",
                   "lines": [{"shipment_line_id": line_id, "quantity": "1.125"}]}
        assert client.post(f"{base}/sales-returns", headers=seller, json=payload).status_code == 409
        client.post(f"{base}/shipments/{shipment_id}/post", headers=warehouse)
        assert client.post(f"{base}/sales-returns", headers=viewer, json=payload).status_code == 403
        assert client.post(f"{base}/sales-returns", headers=seller, json={
            **payload, "reason": "   "}).status_code == 422
        assert client.post(f"{base}/sales-returns", headers=seller, json={
            **payload, "lines": payload["lines"] * 2}).status_code == 422
        assert client.post(f"{base}/sales-returns", headers=seller, json={
            **payload, "lines": [{"shipment_line_id": line_id, "quantity": "2.126"}]}).status_code == 409
        assert client.post(f"{base}/sales-returns", headers=seller, json={
            **payload, "lines": [{"shipment_line_id": line_id, "quantity": "0.0001"}]}).status_code == 422
        first = client.post(f"{base}/sales-returns", headers=seller, json=payload)
        assert first.status_code == 201
        first_id = first.json()["id"]
        assert first.json()["total_amount"] == "11.25"
        # 草稿不预占可退量，确认时重新核对；第二张草稿随后会超额。
        stale = client.post(f"{base}/sales-returns", headers=seller, json={
            **payload, "lines": [{"shipment_line_id": line_id, "quantity": "2.125"}]}).json()["id"]
        assert client.post(f"{base}/sales-returns/{first_id}/post", headers=seller).status_code == 403
        assert client.post(f"{base}/sales-returns/{first_id}/post", headers=warehouse).status_code == 200
        assert client.post(f"{base}/sales-returns/{first_id}/post", headers=warehouse).status_code == 409
        assert client.post(f"{base}/sales-returns/{first_id}/cancel", headers=warehouse).status_code == 409
        assert client.post(f"{base}/sales-returns/{stale}/post", headers=warehouse).status_code == 409
        assert client.post(f"{base}/sales-returns/{stale}/cancel", headers=seller).status_code == 200
        assert client.get(f"{base}/stock?warehouse_id=1", headers=admin).json()[0]["quantity"] == "0.000"
        assert client.get(f"{base}/stock?warehouse_id={second}", headers=admin).json()[0]["quantity"] == "1.125"
        returned = client.get(f"{base}/sales-orders", headers=seller).json()[0]
        assert returned["status"] == "shipped"
        assert returned["lines"][0]["returned_quantity"] == "1.125"
        assert returned["lines"][0]["net_delivered_quantity"] == "1.000"
        assert client.get(f"{base}/shipments", headers=seller).json()[0]["lines"][0]["returnable_quantity"] == "1.000"
        movements = client.get(f"{base}/movements", headers=admin).json()
        assert movements[0]["source_type"] == "sales_return"
        assert movements[0]["sales_return_id"] == first_id
        assert movements[0]["quantity"] == "1.125"
        assert movements[0]["warehouse_id"] == second
        assert movements[0]["created_by"] is not None

        # 剩余数量可再次退回；原出库流水和订单已出库状态始终保留。
        rest = client.post(f"{base}/sales-returns", headers=seller, json={
            **payload, "lines": [{"shipment_line_id": line_id, "quantity": "1.000"}]}).json()["id"]
        assert client.post(f"{base}/sales-returns/{rest}/post", headers=warehouse).status_code == 200
        assert client.get(f"{base}/shipments", headers=seller).json()[0]["lines"][0]["returnable_quantity"] == "0.000"
        assert client.post(f"{base}/sales-returns", headers=seller, json=payload).status_code == 409
