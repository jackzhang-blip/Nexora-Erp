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
