"""旧库夹具只回退待验证版本之后的结构，不让新版表混入旧库。"""

import pytest


@pytest.fixture
def remove_v39_schema():
    def remove(db):
        for table in ('production_settlement_charges', 'production_settlement_dependencies',
                      'production_settlement_sources', 'production_cost_allocations',
                      'production_settlement_reversals', 'production_cost_settlements'):
            db.execute(f'DROP TABLE IF EXISTS {table}')
        for code in ('production_cost.settle', 'production_cost.reopen'):
            db.execute('DELETE FROM role_permissions WHERE permission_code = ?', (code,))
            db.execute('DELETE FROM permissions WHERE code = ?', (code,))
    return remove
