"""验证 BOM 版本、单一启用规则、循环引用与角色权限。"""

from fastapi.testclient import TestClient

from app.main import app


def test_bom_versions_and_cycle_guard(monkeypatch, tmp_path):
    monkeypatch.setenv("NEXORA_DB_PATH", str(tmp_path / "boms.db"))
    with TestClient(app, client=("127.0.0.1", 12000)) as client:
        base = "/api/v1"
        client.post(f"{base}/setup/admin", json={"username": "admin", "password": "secure-pass-123"})

        def login(username: str) -> dict:
            token = client.post(f"{base}/auth/login", json={
                "username": username, "password": "secure-pass-123"}).json()["token"]
            return {"Authorization": f"Bearer {token}"}

        admin = login("admin")
        for username, role in (("planner", "planner"), ("warehouse", "warehouse"), ("viewer", "viewer")):
            client.post(f"{base}/users", headers=admin, json={
                "username": username, "password": "secure-pass-123", "roles": [role]})
        planner, warehouse, viewer = login("planner"), login("warehouse"), login("viewer")
        materials = {}
        for code in ("A", "B", "C", "D"):
            materials[code] = client.post(f"{base}/materials", headers=admin, json={
                "sku": f"BOM-{code}", "name": f"物料{code}", "unit": "件"}).json()["id"]

        def payload(product: str, component: str, quantity: str = "2.125") -> dict:
            return {"product_material_id": materials[product], "base_quantity": "1.000",
                    "note": "试产版本", "lines": [{"component_material_id": materials[component],
                                            "quantity": quantity}]}

        assert client.get(f"{base}/boms", headers=viewer).status_code == 403
        assert client.get(f"{base}/boms", headers=warehouse).status_code == 200
        assert client.post(f"{base}/boms", headers=warehouse, json=payload("A", "B")).status_code == 403
        assert client.post(f"{base}/boms", headers=planner, json=payload("A", "A")).status_code == 422
        assert client.post(f"{base}/boms", headers=planner, json={
            **payload("A", "B"), "lines": payload("A", "B")["lines"] * 2}).status_code == 422
        assert client.post(f"{base}/boms", headers=planner, json=payload("A", "B", "0.0001")).status_code == 422
        assert client.post(f"{base}/boms", headers=planner, json={
            **payload("A", "B"), "base_quantity": "0"}).status_code == 422
        assert client.post(f"{base}/boms", headers=planner, json={
            **payload("A", "B"), "product_material_id": 999999}).status_code == 422

        first = client.post(f"{base}/boms", headers=planner, json=payload("A", "B"))
        assert first.status_code == 201
        first_id = first.json()["id"]
        assert first.json()["version"] == 1
        assert first.json()["lines"][0]["quantity"] == "2.125"
        assert client.post(f"{base}/boms/{first_id}/activate", headers=warehouse).status_code == 403
        assert client.post(f"{base}/boms/{first_id}/activate", headers=planner).status_code == 200
        assert client.post(f"{base}/boms/{first_id}/activate", headers=planner).status_code == 409
        assert client.post(f"{base}/boms/{first_id}/cancel", headers=planner).status_code == 409
        second_id = client.post(f"{base}/boms", headers=planner, json=payload("B", "C")).json()["id"]
        assert client.post(f"{base}/boms/{second_id}/activate", headers=planner).status_code == 200

        # C -> A 与已启用的 A -> B -> C 构成环，启用必须拒绝并保留草稿。
        cyclic = client.post(f"{base}/boms", headers=planner, json=payload("C", "A")).json()["id"]
        assert client.post(f"{base}/boms/{cyclic}/activate", headers=planner).status_code == 409
        assert next(item for item in client.get(f"{base}/boms", headers=planner).json()
                    if item["id"] == cyclic)["status"] == "draft"
        assert client.post(f"{base}/boms/{cyclic}/cancel", headers=planner).status_code == 200
        assert client.post(f"{base}/boms/{cyclic}/activate", headers=planner).status_code == 409

        replacement = client.post(f"{base}/boms", headers=planner, json=payload("A", "D")).json()
        assert replacement["version"] == 2
        assert client.post(f"{base}/boms/{replacement['id']}/activate", headers=planner).status_code == 409
        assert client.post(f"{base}/boms/{first_id}/retire", headers=planner).status_code == 200
        assert client.post(f"{base}/boms/{first_id}/retire", headers=planner).status_code == 409
        assert client.post(f"{base}/boms/{replacement['id']}/activate", headers=planner).status_code == 200
        versions = [item for item in client.get(f"{base}/boms", headers=warehouse).json()
                    if item["product_material_id"] == materials["A"]]
        assert {item["status"] for item in versions} == {"active", "retired"}
        assert client.get(f"{base}/stock", headers=planner).json()[0]["quantity"] == "0"
