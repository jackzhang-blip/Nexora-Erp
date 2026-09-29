import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'

test('登录页成功状态进入底栏，工作台和错误提示保留原有位置', () => {
  const shell = readFileSync(new URL('../src/renderer/src/views/WorkspaceShell.vue', import.meta.url), 'utf8')

  // 同一条消息只在当前页面对应的位置出现，避免登录页重新产生整行成功提示。
  assert.match(shell, /screen\.value === 'setup' \|\| screen\.value === 'login'/)
  assert.match(shell, /v-if="notice && !isAuthScreen" class="message success" role="status"/)
  assert.match(shell, /<footer v-if="isAuthScreen" class="onboard-footer auth-footer">[\s\S]*?v-if="notice" class="onboard-footer-status" role="status"/)
  assert.match(shell, /v-if="error" class="message error" role="alert"/)
  assert.match(shell, /v-if="connectionLost" class="message error" role="alert"/)
})

test('登录内容独立滚动，底栏在宽窄窗口内都保留可见', () => {
  const css = readFileSync(new URL('../src/renderer/src/style.css', import.meta.url), 'utf8')
  const rule = (selector) => css.match(new RegExp(`${selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')} \\{([^}]+)\\}`, 'm'))?.[1] ?? ''

  // 内容区需要允许收缩并自行滚动，否则小窗口仍会把底栏推到视口外。
  assert.match(rule('.content.auth-content'), /height: 100vh;[^}]*overflow: hidden;[^}]*padding: 0;/)
  assert.match(rule('.auth-content .content-body'), /min-height: 0;[^}]*flex: 1;[^}]*overflow-y: auto;/)
  assert.match(rule('.onboard-footer'), /flex: none;/)
  assert.match(css, /@media \(max-width: 760px\)[\s\S]*?\.app-shell\.auth-shell \{ height: 100vh; display: flex; flex-direction: column; overflow: hidden; \}/)
  assert.match(css, /@media \(max-width: 760px\)[\s\S]*?\.content\.auth-content \{ height: auto; min-height: 0; flex: 1; \}/)
  assert.match(css, /@media \(max-width: 760px\)[\s\S]*?\.auth-footer \.onboard-footer-copy:first-child \{ display: none; \}/)
})
