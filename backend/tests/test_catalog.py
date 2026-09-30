"""基础资料维护、供货多对多关系和历史引用保护。"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import connection, migrate


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("NEXORA_DB_PATH", str(tmp_path / "catalog.db"))
    with TestClient(app, client=("127.0.0.1", 12000)) as client:
        client.post("/api/v1/setup/admin", json={"username": "admin", "password": "secure-pass-123"})
        token = client.post("/api/v1/auth/login", json={"username": "admin", "password": "secure-pass-123"}).json()["token"]
        client.headers["Authorization"] = f"Bearer {token}"
        yield client


def create(client, resource, payload):
    result = client.post(f"/api/v1/{resource}", json=payload)
    assert result.status_code == 201, result.text
    return result.json()["id"]


@pytest.mark.parametrize("resource,original,updated", [
    ("materials", {"sku": "R-1", "name": "电阻 10k", "unit": "件"}, {"sku": "R-2", "name": "电阻 20k", "unit": "个"}),
    ("suppliers", {"name": "甲厂"}, {"name": "乙厂"}),
    ("warehouses", {"code": "EAST", "name": "东仓"}, {"code": "WEST", "name": "西仓"}),
])
def test_crud_validation_and_conflicts(client, resource, original, updated):
    record = create(client, resource, original)
    path = f"/api/v1/{resource}/{record}"
    assert client.post(f"/api/v1/{resource}", json=original).status_code == 409
    assert client.put(path, json={**updated, "name": "   "}).status_code == 422
    assert client.put(path, json=updated).json() == {"id": record, **updated}
    other = create(client, resource, original)
    assert client.put(f"/api/v1/{resource}/{other}", json=updated).status_code == 409
    assert {"id": record, **updated} in client.get(f"/api/v1/{resource}").json()
    assert client.delete(path).status_code == 204
    assert client.delete(path).status_code == 404
    assert client.put(path, json=updated).status_code == 404


def test_many_to_many_and_unbind(client):
    suppliers = [create(client, "suppliers", {"name": name}) for name in ["甲厂", "乙厂"]]
    materials = [create(client, "materials", {"sku": sku, "name": sku, "unit": "件"}) for sku in ["R-10K", "C-100N"]]
    for supplier in suppliers:
        for material in materials:
            path = f"/api/v1/suppliers/{supplier}/materials/{material}"
            assert client.put(path).status_code == 204
            assert client.put(path).status_code == 204
    assert len(client.get("/api/v1/supplier-materials").json()) == 4
    assert client.put(f"/api/v1/suppliers/9999/materials/{materials[0]}").status_code == 404
    assert client.put(f"/api/v1/suppliers/{suppliers[0]}/materials/9999").status_code == 404
    assert client.delete(f"/api/v1/suppliers/{suppliers[0]}/materials/{materials[0]}").status_code == 204
    assert len(client.get("/api/v1/supplier-materials").json()) == 3
    assert len(client.get("/api/v1/materials").json()) == 2
    assert client.delete(f"/api/v1/suppliers/{suppliers[0]}").status_code == 204
    assert len(client.get("/api/v1/supplier-materials").json()) == 2
    assert client.delete(f"/api/v1/materials/{materials[0]}").status_code == 204
    assert client.get("/api/v1/supplier-materials").json() == [{"supplier_id": suppliers[1], "material_id": materials[1]}]


def test_referenced_records_cannot_be_deleted_and_links_survive_rollback(client):
    supplier = create(client, "suppliers", {"name": "甲厂"})
    material = create(client, "materials", {"sku": "R", "name": "电阻", "unit": "件"})
    warehouse = create(client, "warehouses", {"code": "EAST", "name": "东仓"})
    client.put(f"/api/v1/suppliers/{supplier}/materials/{material}")
    create(client, "receipts", {"supplier_id": supplier, "warehouse_id": warehouse, "lines": [{"material_id": material, "quantity": "1"}]})
    for resource, record in [("materials", material), ("suppliers", supplier), ("warehouses", warehouse), ("warehouses", 1)]:
        assert client.delete(f"/api/v1/{resource}/{record}").status_code == 409
    assert client.get("/api/v1/supplier-materials").json() == [{"supplier_id": supplier, "material_id": material}]


def test_viewer_cannot_modify_catalog(client):
    create(client, "users", {"username": "viewer", "password": "secure-pass-123", "roles": ["viewer"]})
    token = client.post("/api/v1/auth/login", json={"username": "viewer", "password": "secure-pass-123"}).json()["token"]
    client.headers["Authorization"] = f"Bearer {token}"
    for resource, payload in [("materials", {"sku": "R", "name": "R", "unit": "件"}), ("suppliers", {"name": "甲"}), ("warehouses", {"code": "E", "name": "东"})]:
        assert client.get(f"/api/v1/{resource}").status_code == 200
        assert client.post(f"/api/v1/{resource}", json=payload).status_code == 403
        assert client.put(f"/api/v1/{resource}/1", json=payload).status_code == 403
        assert client.delete(f"/api/v1/{resource}/1").status_code == 403
    assert client.get("/api/v1/supplier-materials").status_code == 200
    assert client.put("/api/v1/suppliers/1/materials/1").status_code == 403
    assert client.delete("/api/v1/suppliers/1/materials/1").status_code == 403


def test_v27_migration_preserves_existing_materials(client):
    material = create(client, "materials", {"sku": "OLD", "name": "旧物料", "unit": "件"})
    with connection() as db:
        db.execute("DROP TABLE inventory_cost_inputs")
        db.execute("DELETE FROM role_permissions WHERE permission_code LIKE 'inventory_valuation.%'")
        db.execute("DELETE FROM permissions WHERE code LIKE 'inventory_valuation.%'")
        db.execute("DELETE FROM permission_groups WHERE code = 'finance.inventory_valuation'")
        db.execute("DELETE FROM role_permissions WHERE permission_code = 'purchase_return.submit'")
        db.execute("DELETE FROM permissions WHERE code = 'purchase_return.submit'")
        db.execute("DELETE FROM role_permissions WHERE permission_code IN ('purchase_report.view', 'inventory_report.view')")
        db.execute("DELETE FROM permissions WHERE code IN ('purchase_report.view', 'inventory_report.view')")
        db.execute("DELETE FROM permission_groups WHERE code IN ('purchase.reports', 'warehouse.reports')")
        db.execute("DROP TABLE stock_adjustment_reversals")
        db.execute("DROP TABLE stock_adjustment_lines")
        db.execute("DROP TABLE stock_adjustments")
        db.execute("DELETE FROM role_permissions WHERE permission_code LIKE 'adjustment.%'")
        db.execute("DELETE FROM permissions WHERE code LIKE 'adjustment.%'")
        db.execute("DELETE FROM permission_groups WHERE code = 'warehouse.adjustment'")
        db.execute("DROP TABLE warehouse_outbound_reversals")
        db.execute("DROP TABLE warehouse_outbound_lines")
        db.execute("DROP TABLE warehouse_outbounds")
        db.execute("DELETE FROM role_permissions WHERE permission_code LIKE 'other_outbound.%'")
        db.execute("DELETE FROM permissions WHERE code LIKE 'other_outbound.%'")
        db.execute("DELETE FROM permission_groups WHERE code = 'warehouse.other_outbound'")
        db.execute("DROP TABLE warehouse_inbound_reversals")
        db.execute("DROP TABLE warehouse_inbound_lines")
        db.execute("DROP TABLE warehouse_inbounds")
        db.execute("DELETE FROM role_permissions WHERE permission_code LIKE 'other_inbound.%'")
        db.execute("DELETE FROM permissions WHERE code LIKE 'other_inbound.%'")
        db.execute("DELETE FROM permission_groups WHERE code = 'warehouse.other_inbound'")
        db.execute("DROP TABLE purchase_goods_receipt_lines")
        db.execute("DROP TABLE purchase_goods_receipts")
        db.execute("DELETE FROM role_permissions WHERE permission_code LIKE 'purchase_receiving.%'")
        db.execute("DELETE FROM permissions WHERE code LIKE 'purchase_receiving.%'")
        db.execute("DELETE FROM permission_groups WHERE code = 'purchase.receiving'")
        # 模拟旧库时同步移除第 29 版采购申请结构。
        db.execute("DROP TABLE purchase_order_request_links")
        db.execute("DROP TABLE purchase_request_lines")
        db.execute("DROP TABLE purchase_requests")
        db.execute("DELETE FROM role_permissions WHERE permission_code LIKE 'purchase_request.%'")
        db.execute("DELETE FROM permissions WHERE code LIKE 'purchase_request.%'")
        db.execute("DELETE FROM permission_groups WHERE code = 'purchase.purchase_request'")
        db.execute("DROP TABLE supplier_materials")
        db.execute("PRAGMA user_version = 27")
    migrate()
    migrate()
    with connection() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 36
        assert db.execute("SELECT name FROM materials WHERE id = ?", (material,)).fetchone()[0] == "旧物料"
        assert db.execute("SELECT COUNT(*) FROM supplier_materials").fetchone()[0] == 0
