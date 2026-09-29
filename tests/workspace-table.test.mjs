import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import vue from '@vitejs/plugin-vue'
import { createSSRApp, h } from 'vue'
import { renderToString } from '@vue/server-renderer'
import { createServer } from 'vite'

test('公共表格渲染页面内容、行和空状态，加载时不展示旧行', async (t) => {
  // 使用 Vue 实际编译并渲染单文件组件，核对插槽与表格状态的组合结果。
  const server = await createServer({
    configFile: false,
    plugins: [vue()],
    optimizeDeps: { noDiscovery: true, include: [] },
    server: { middlewareMode: true },
    appType: 'custom'
  })
  t.after(() => server.close())
  const { default: WorkspaceTable } = await server.ssrLoadModule('/src/renderer/src/components/workspace/WorkspaceTable.vue')
  const columns = [{ key: 'name', title: '名称' }, { key: 'actions', title: '操作' }]
  const slots = {
    heading: () => h('h2', '自定义标题'),
    actions: () => h('button', '新增'),
    filters: () => h('label', '搜索'),
    beforeTable: () => h('form', '编辑资料'),
    rows: () => h('tr', [h('td', '物料 A'), h('td', '编辑')]),
    empty: () => '没有匹配的资料'
  }
  const render = (props, activeSlots = slots) => renderToString(createSSRApp({
    render: () => h(WorkspaceTable, { title: '资料列表', columns, ...props }, activeSlots)
  }))

  const populated = await render({ rowCount: 1 })
  assert.match(populated, /aria-label="资料列表"/)
  assert.match(populated, /min-width:580px/)
  assert.match(populated, /<th[^>]*>名称<\/th>/)
  assert.match(populated, /物料 A/)
  assert.ok(populated.indexOf('自定义标题') < populated.indexOf('搜索'))
  assert.ok(populated.indexOf('搜索') < populated.indexOf('编辑资料'))
  assert.ok(populated.indexOf('编辑资料') < populated.indexOf('<table'))

  // 两列资料表可缩到更窄的窗口，避免沿用职务表的最小宽度。
  const compact = await render({ rowCount: 1, minTableWidth: 360 })
  assert.match(compact, /min-width:360px/)

  const empty = await render({ rowCount: 0 })
  assert.match(empty, /<td colspan="2"/)
  assert.match(empty, /没有匹配的资料/)
  assert.doesNotMatch(empty, /物料 A/)

  const loading = await render({ rowCount: 1, loading: true })
  assert.match(loading, /正在加载…/)
  assert.doesNotMatch(loading, /物料 A/)

  // 旧职务页面不提供新插槽时，默认标题、说明和空状态仍能正常显示。
  const defaultEmpty = await render({ rowCount: 0, description: '职务说明' }, {})
  assert.match(defaultEmpty, /<h2[^>]*>资料列表<\/h2>/)
  assert.match(defaultEmpty, /职务说明/)
  assert.match(defaultEmpty, /暂无数据/)
})

test('基础资料的四张列表都接入公共表格', () => {
  const views = [
    ['MaterialsView.vue', 1],
    ['SuppliersView.vue', 2],
    ['WarehousesView.vue', 1]
  ]
  for (const [name, expectedTables] of views) {
    const source = readFileSync(new URL(`../src/renderer/src/views/workspace/catalog/${name}`, import.meta.url), 'utf8')
    // 页面保留业务行与空状态，原生表格外壳不能再由各页重复实现。
    assert.equal((source.match(/<WorkspaceTable\b/g) ?? []).length, expectedTables, name)
    assert.equal((source.match(/<template #rows>/g) ?? []).length, expectedTables, name)
    assert.equal((source.match(/<template #empty>/g) ?? []).length, expectedTables, name)
    assert.doesNotMatch(source, /<table\b/, name)
  }
})
