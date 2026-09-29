import assert from 'node:assert/strict'
import { test } from 'node:test'
import { accountRoleText } from '../src/renderer/src/utils/account-role.ts'

test('账号卡片优先展示服务端返回的角色名称', () => {
  assert.equal(accountRoleText(['admin', 'warehouse'], [
    { code: 'admin', label: '管理员' },
    { code: 'warehouse', label: '仓库员' }
  ]), '管理员 · 仓库员')
})

test('没有角色详情或没有角色时不伪造职位', () => {
  assert.equal(accountRoleText(['buyer'], []), '采购员')
  assert.equal(accountRoleText(['custom'], []), 'custom')
  assert.equal(accountRoleText([], []), '未分配角色')
})
