import assert from 'node:assert/strict'
import test from 'node:test'
import {
  buildPermissionTree,
  documentPermissionCodes,
  modulePermissionCodes,
  selectedPermissionCount,
  togglePermissionCodes
} from '../src/renderer/src/utils/permission-tree.ts'

test('同名审批按钮按单据分成独立的操作叶子', () => {
  const permissions = [
    { code: 'receipt.approve', label: '批准', group_path: [
      { code: 'warehouse', label: '仓库管理' }, { code: 'receipt', label: '入库单' }] },
    { code: 'shipment.approve', label: '批准', group_path: [
      { code: 'warehouse', label: '仓库管理' }, { code: 'shipment', label: '出库单' }] },
    { code: 'receipt.review', label: '审核', group_path: [
      { code: 'warehouse', label: '仓库管理' }, { code: 'receipt', label: '入库单' }] }
  ]
  const [warehouse] = buildPermissionTree(permissions)
  assert.equal(warehouse.label, '仓库管理')
  assert.equal(warehouse.documents.length, 2)
  const receipt = warehouse.documents.find((document) => document.code === 'receipt')
  const shipment = warehouse.documents.find((document) => document.code === 'shipment')
  assert.deepEqual(new Set(documentPermissionCodes(receipt)), new Set(['receipt.approve', 'receipt.review']))
  assert.deepEqual(documentPermissionCodes(shipment), ['shipment.approve'])

  const selected = togglePermissionCodes([], documentPermissionCodes(receipt), true)
  assert.deepEqual(new Set(selected), new Set(['receipt.approve', 'receipt.review']))
  assert.equal(selected.includes('shipment.approve'), false)
  assert.equal(selectedPermissionCount(selected, modulePermissionCodes(warehouse)), 2)
  assert.deepEqual(togglePermissionCodes(selected, ['receipt.approve'], false), ['receipt.review'])
})

test('旧服务端缺少层级字段时仍显示权限叶子', () => {
  const [fallback] = buildPermissionTree([{ code: 'legacy.view', label: '查看旧单据' }])
  assert.equal(fallback.label, '其他权限')
  assert.deepEqual(documentPermissionCodes(fallback.documents[0]), ['legacy.view'])
})
