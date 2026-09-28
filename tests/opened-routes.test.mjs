import assert from 'node:assert/strict'
import { test } from 'node:test'
import { closeRoute, openRoute, permittedOpenedRoutes } from '../src/renderer/src/workspace-routes.ts'

test('按首次打开顺序记录页面，重复打开不新增标签', () => {
  const opened = openRoute(openRoute(openRoute([], 'stock'), 'boms'), 'stock')
  assert.deepEqual(opened, ['stock', 'boms'])
})

test('关闭当前页面切换到前一个页面，关闭首项切换到后一个页面', () => {
  assert.deepEqual(closeRoute(['stock', 'boms', 'workOrders'], 'boms', 'boms'), {
    opened: ['stock', 'workOrders'], active: 'stock'
  })
  assert.deepEqual(closeRoute(['stock', 'boms'], 'stock', 'stock'), {
    opened: ['boms'], active: 'boms'
  })
})

test('关闭后台页面不影响当前页面，唯一页面保持打开', () => {
  assert.deepEqual(closeRoute(['stock', 'boms'], 'stock', 'boms'), {
    opened: ['boms'], active: 'boms'
  })
  assert.deepEqual(closeRoute(['stock'], 'stock', 'stock'), {
    opened: ['stock'], active: 'stock'
  })
})

test('权限撤销后清除无权访问的页面，保留公共设置页面', () => {
  assert.deepEqual(permittedOpenedRoutes(['stock', 'boms', 'users', 'settings'], ['production.view']), [
    'boms', 'settings'
  ])
})
