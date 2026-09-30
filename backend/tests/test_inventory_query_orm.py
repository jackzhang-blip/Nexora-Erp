"""库存 ORM 查询保留跨仓精度、日期边界和无操作人的历史流水。"""

import pytest
from fastapi.testclient import TestClient

from app.core.models import StockMovement
from app.core.orm import orm_session
from app.main import app


@pytest.fixture
def inventory(monkeypatch, tmp_path):
    monkeypatch.setenv('NEXORA_DB_PATH', str(tmp_path / 'inventory-query.db'))
    with TestClient(app, client=('127.0.0.1', 12000)) as client:
        base = '/api/v1'
        assert client.post(base + '/setup/admin', json={
            'username': 'admin', 'password': 'secure-pass-123'}).status_code == 201
        token = client.post(base + '/auth/login', json={
            'username': 'admin', 'password': 'secure-pass-123'}).json()['token']
        client.headers['Authorization'] = f'Bearer {token}'
        material = client.post(base + '/materials', json={
            'sku': 'FLOW', 'name': '流水物料', 'unit': '件'}).json()['id']
        empty = client.post(base + '/materials', json={
            'sku': 'EMPTY', 'name': '无库存物料', 'unit': '件'}).json()['id']
        warehouse = client.post(base + '/warehouses', json={'code': 'SECOND', 'name': '外仓'}).json()['id']
        with orm_session(write=True) as db:
            for line_id, source_type, quantity, timestamp in (
                (1, 'receipt', '0.300', '2026-01-30 23:59:59'),
                (2, 'shipment', '-0.100', '2026-01-31 00:00:00'),
                (3, 'other_inbound', '0.200', '2026-02-01 00:00:00')):
                db.add(StockMovement(warehouse_id=1, material_id=material, quantity=quantity,
                    source_type=source_type, source_id=line_id, source_line_id=line_id,
                    created_by=None, created_at=timestamp))
            db.add(StockMovement(warehouse_id=warehouse, material_id=material, quantity='0.600',
                source_type='other_inbound', source_id=4, source_line_id=4, created_by=1,
                created_at='2026-01-31 23:59:59'))
        yield client, material, empty, warehouse


def test_multi_warehouse_quantities_and_empty_material(inventory):
    client, material, empty, warehouse = inventory
    quantities = lambda rows: {row['id']: row['quantity'] for row in rows}
    assert quantities(client.get('/api/v1/stock').json()) == {material: '1.000', empty: '0'}
    assert quantities(client.get('/api/v1/stock', params={'warehouse_id': 1}).json())[material] == '0.400'
    assert quantities(client.get('/api/v1/stock', params={'warehouse_id': warehouse}).json())[material] == '0.600'
    assert client.get('/api/v1/stock', params={'warehouse_id': 999999}).status_code == 422
    movements = client.get('/api/v1/movements').json()
    assert len(movements) == 4 and movements[0]['source_id'] == 4
    assert movements[-1]['receipt_id'] == 1 and movements[-1]['shipment_id'] is None
    assert movements[2]['shipment_id'] == 2 and movements[2]['receipt_id'] is None
    assert movements[-1]['created_by'] is None and movements[-1]['material_name'] == '流水物料'


def test_ledger_date_limits_and_source_scope(inventory):
    client, material, _, warehouse = inventory
    path = '/api/v1/inventory-ledger/query'
    filters = {'warehouse_id': 1, 'material_id': material, 'from_date': '2026-01-31', 'to_date': '2026-01-31'}
    ledger = client.post(path, json=filters).json()
    assert ledger['groups'][0]['opening_quantity'] == '0.300'
    assert ledger['groups'][0]['closing_quantity'] == '0.200'
    assert len(ledger['rows']) == 1 and ledger['rows'][0]['balance_quantity'] == '0.200'
    assert ledger['rows'][0]['created_by_name'] is None
    other = client.post(path, json={**filters, 'warehouse_id': warehouse}).json()
    assert len(other['rows']) == 1 and other['groups'][0]['closing_quantity'] == '0.600'
    source = client.post(path, json={**filters, 'source_type': 'shipment'}).json()
    assert source['groups'][0]['opening_quantity'] == '0'
    assert source['groups'][0]['closing_quantity'] == '-0.100'
    assert client.post(path, json={**filters, 'material_id': 999999}).status_code == 422
    assert client.post(path, json={**filters, 'warehouse_id': 999999}).status_code == 422
    assert client.post(path, json={**filters, 'source_type': "receipt' OR 1=1"}).status_code == 422


def test_inventory_queries_require_login(inventory):
    client, *_ = inventory
    client.headers.pop('Authorization')
    assert client.get('/api/v1/stock').status_code == 401
    assert client.get('/api/v1/movements').status_code == 401
    assert client.post('/api/v1/inventory-ledger/query', json={}).status_code == 401
