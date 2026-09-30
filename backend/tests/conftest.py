"""旧库夹具只回退待验证版本之后的结构，不让新版表混入旧库。"""

import pytest


@pytest.fixture
def remove_v39_schema():
    def remove(db):
        for table in ('ledger_account_changes', 'accounting_period_changes',
                      'ledger_accounts', 'accounting_periods'):
            db.execute(f'DROP TABLE IF EXISTS {table}')
        for code in ('ledger_account.view', 'ledger_account.manage',
                     'accounting_period.view', 'accounting_period.manage'):
            db.execute('DELETE FROM role_permissions WHERE permission_code = ?', (code,))
            db.execute('DELETE FROM permissions WHERE code = ?', (code,))
        if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='permission_groups'").fetchone():
            db.execute("DELETE FROM permission_groups WHERE code IN ('finance.ledger_accounts','finance.accounting_periods')")
        for table in ('production_settlement_charges', 'production_settlement_dependencies',
                      'production_settlement_sources', 'production_cost_allocations',
                      'production_settlement_reversals', 'production_cost_settlements'):
            db.execute(f'DROP TABLE IF EXISTS {table}')
        for code in ('production_cost.settle', 'production_cost.reopen'):
            db.execute('DELETE FROM role_permissions WHERE permission_code = ?', (code,))
            db.execute('DELETE FROM permissions WHERE code = ?', (code,))
    return remove
