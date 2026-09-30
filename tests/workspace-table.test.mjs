import assert from 'node:assert/strict'
import { readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'
import { test } from 'node:test'
import { fileURLToPath } from 'node:url'
import vue from '@vitejs/plugin-vue'
import { createSSRApp, h } from 'vue'
import { renderToString } from '@vue/server-renderer'
import { createServer } from 'vite'

const viewRoot = new URL('../src/renderer/src/views/workspace/', import.meta.url)

function vueFiles(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap(entry => {
    const path = join(directory, entry.name)
    return entry.isDirectory() ? vueFiles(path) : entry.name.endsWith('.vue') ? [path] : []
  })
}

test('公共表格加载真实 vxe 组件并渲染功能区、加载和空状态', async t => {
  // vxe 在浏览器挂载后才生成数据行；这里验证服务端渲染能装载真实组件与公共外壳。
  const server = await createServer({
    configFile: false,
    plugins: [vue()],
    ssr: { noExternal: ['vxe-table'] },
    optimizeDeps: { noDiscovery: true, include: [] },
    server: { middlewareMode: true },
    appType: 'custom'
  })
  t.after(() => server.close())
  const { default: WorkspaceTable } = await server.ssrLoadModule('/src/renderer/src/components/workspace/WorkspaceTable.vue')
  const columns = [{ key: 'name', title: '名称' }, { key: 'actions', title: '操作' }]
  const slots = {
    actions: () => h('button', '新增'),
    filters: () => h('label', '搜索'),
    'cell-actions': ({ row }) => h('button', `编辑${row.name}`),
    empty: () => '没有匹配的资料'
  }
  const render = (props, activeSlots = slots) => renderToString(createSSRApp({
    render: () => h(WorkspaceTable, { title: '资料列表', columns, ...props }, activeSlots)
  }))

  const populated = await render({ data: [{ name: '物料 A' }], minTableWidth: 360 })
  assert.match(populated, /aria-label="资料列表"/)
  assert.match(populated, /min-width:360px/)
  assert.match(populated, /workspace-vxe-table/)
  assert.ok(populated.indexOf('新增') < populated.indexOf('搜索'))

  const empty = await render({ data: [] })
  assert.match(empty, /没有匹配的资料/)

  const loading = await render({ data: [{ name: '物料 A' }], loading: true })
  assert.match(loading, /正在加载…/)

  const defaultEmpty = await render({ data: [], description: '职务说明' }, {})
  assert.match(defaultEmpty, /职务说明/)
  assert.match(defaultEmpty, /暂无数据/)
})

test('业务页面不再直接创建原生表格或 vxe 表格', () => {
  const component = readFileSync(new URL('../src/renderer/src/components/workspace/WorkspaceTable.vue', import.meta.url), 'utf8')
  assert.match(component, /<VxeTable\b/)
  assert.match(component, /<VxeColumn\b/)
  // Windows 的 URL pathname 会带有额外的盘符前缀，先转换为本机文件路径。
  for (const path of vueFiles(fileURLToPath(viewRoot))) {
    const source = readFileSync(path, 'utf8')
    assert.doesNotMatch(source, /<table\b|<VxeTable\b/, path)
  }
})

test('新增入口打开弹窗，失败时保留草稿', () => {
  const paths = [
    'catalog/MaterialsView.vue', 'warehouse/OtherInboundsView.vue',
    'purchase/PurchaseOrdersView.vue', 'sales/SalesOrdersView.vue',
    'production/ProductionWorkOrdersView.vue', 'system/UserManagementView.vue'
  ]
  for (const path of paths) {
    const source = readFileSync(new URL(path, viewRoot), 'utf8')
    assert.match(source, /<NModal\b/, path)
    assert.match(source, /@click="(?:edit\(\)|showForm = true|createOpen = true|customerOpen = true)"/, path)
    assert.match(source, /submitCreateDialog\(|if \(await saveMaterial/, path)
  }
})

test('公共 vxe 表格匹配工作台明暗主题与单元格高度', () => {
  const source = readFileSync(new URL('../src/renderer/src/components/workspace/WorkspaceTable.vue', import.meta.url), 'utf8')
  assert.match(source, /\.workspace-vxe-table :is\(th, td\) \{[^}]*vertical-align: middle;/)
  assert.match(source, /:root\[data-theme='dark'\] \.workspace-vxe-table/)
})
