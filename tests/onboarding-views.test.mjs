import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import { test } from 'node:test'

test('启动阶段均映射到独立页面，证书与就绪页保留前置条件', () => {
  const shell = readFileSync(new URL('../src/renderer/src/views/OnboardingView.vue', import.meta.url), 'utf8')
  const imports = new Map([...shell.matchAll(/^import (\w+) from '\.\/onboarding\/(\w+View\.vue)'$/gm)]
    .map(([, component, filename]) => [component, filename]))
  const entries = [...shell.matchAll(/^  (\w+): (\w+View),?$/gm)]
  const expectedStages = ['loading', 'welcome', 'manual', 'scan', 'results', 'create', 'trust', 'ready', 'offline']

  // 新增引导阶段时必须同时建立真实页面，避免切换后只剩标题。
  assert.deepEqual(entries.map(([, stage]) => stage), expectedStages)
  assert.equal(imports.size, expectedStages.length)
  for (const [, stage, component] of entries) {
    const filename = imports.get(component)
    assert.ok(filename, `${stage} 缺少页面导入`)
    assert.ok(existsSync(new URL(`../src/renderer/src/views/onboarding/${filename}`, import.meta.url)))
  }
  assert.match(shell, /screen\.value === 'trust' && !candidate\.value/)
  assert.match(shell, /screen\.value === 'ready' && !server\.value/)
})

test('启动页的长内容在中间滚动，底部说明保留在窗口内', () => {
  const css = readFileSync(new URL('../src/renderer/src/style.css', import.meta.url), 'utf8')
  const rule = (selector) => css.match(new RegExp(`^\\${selector} \\{([^}]+)\\}`, 'm'))?.[1] ?? ''

  // 三个区域的高度约束必须配套；缺少中间区域的 min-height 会再次把底栏推出视口。
  assert.match(rule('.onboarding'), /\bheight: 100vh;/)
  assert.match(rule('.onboarding'), /\boverflow: hidden;/)
  assert.match(rule('.onboard-top'), /\bflex: none;/)
  assert.match(rule('.onboard-main'), /\bmin-height: 0;/)
  assert.match(rule('.onboard-main'), /\boverflow-y: auto;/)
  assert.match(rule('.onboard-footer'), /\bflex: none;/)
})

test('连接成功和失败提示都位于底栏右端，失败优先且保留告警语义', () => {
  const shell = readFileSync(new URL('../src/renderer/src/views/OnboardingView.vue', import.meta.url), 'utf8')
  const css = readFileSync(new URL('../src/renderer/src/style.css', import.meta.url), 'utf8')
  const [main, footer] = shell.split('<footer class="onboard-footer">')

  // 连接超时不能再推挤表单；错误和成功共用右端位置，错误消息优先。
  assert.doesNotMatch(main, /v-if="(?:error|notice)"/)
  assert.match(footer, /v-if="error \|\| notice"/)
  assert.match(footer, /:class="\{ 'is-error': !!error \}"/)
  assert.match(footer, /:role="error \? 'alert' : 'status'"/)
  assert.match(footer, /\{\{ error \|\| notice \}\}/)
  assert.match(footer, /<span v-else class="onboard-footer-copy">局域网内连接/)
  assert.match(css, /\.onboard-footer-status \{[^}]*grid-column: 2 \/ 4;[^}]*justify-content: flex-end;/)
  assert.match(css, /\.onboard-footer-status\.is-error \{[^}]*color: #a9473d;/)
  assert.match(css, /@media \(max-width: 760px\)[\s\S]*?\.onboard-footer-status \{ flex: 1; \}/)
})

test('服务端就绪页左右卡片等宽，窄窗口仍改为单列', () => {
  const view = readFileSync(new URL('../src/renderer/src/views/onboarding/ConnectionReadyView.vue', import.meta.url), 'utf8')
  const css = readFileSync(new URL('../src/renderer/src/style.css', import.meta.url), 'utf8')

  // 单独约束就绪页，避免影响手动连接和本机服务创建页的列宽。
  assert.match(view, /class="onboard-columns ready-columns"/)
  assert.match(css, /\.ready-columns \{ grid-template-columns: repeat\(2, minmax\(0, 1fr\)\); align-items: stretch; \}/)
  assert.match(css, /@media \(max-width: 760px\)[\s\S]*?\.choice-grid, \.onboard-columns \{ grid-template-columns: 1fr; \}/)
})
