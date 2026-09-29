import assert from 'node:assert/strict'
import test from 'node:test'
import { filterRoleRows } from '../src/renderer/src/utils/role-table.ts'

const roles = [
  { code: 'admin', label: '管理员', is_builtin: true, permissions: ['users.manage'] },
  { code: 'buyer', label: '采购员', is_builtin: true, permissions: [] },
  { code: 'role_stock', label: '库存主管', is_builtin: false, permissions: ['inventory.view'] },
  { code: 'role_sales', label: '销售主管', is_builtin: false, permissions: [] }
]

test('职务搜索与类型筛选同时作用且不修改原始角色授权', () => {
  assert.deepEqual(filterRoleRows(roles, ' 主管 ', 'custom').map((role) => role.code),
    ['role_stock', 'role_sales'])
  assert.deepEqual(filterRoleRows(roles, '采购', 'builtin').map((role) => role.code), ['buyer'])
  assert.deepEqual(filterRoleRows(roles, '采购', 'custom'), [])
  assert.deepEqual(roles[2].permissions, ['inventory.view'])
})
