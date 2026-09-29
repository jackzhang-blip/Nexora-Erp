import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'

test('登录页连接状态持续位于底栏右侧，工作台与账号错误保留原有提示', () => {
  const shell = readFileSync(new URL('../src/renderer/src/views/WorkspaceShell.vue', import.meta.url), 'utf8')

  // 断线优先于旧成功消息，正常状态也要明确显示而不只写服务端名称。
  assert.match(shell, /screen\.value === 'setup' \|\| screen\.value === 'login'/)
  assert.match(shell, /if \(connectionLost\.value\) return '服务端连接已中断/)
  assert.match(shell, /if \(notice\.value\) return notice\.value/)
  assert.match(shell, /return '已连接'/)
  assert.match(shell, /v-if="notice && !isAuthScreen" class="message success" role="status"/)
  assert.match(shell, /v-if="error" class="message error" role="alert"/)
  assert.match(shell, /v-if="connectionLost && !isAuthScreen" class="message error" role="alert"/)
  const footer = shell.split('<footer v-if="isAuthScreen" class="onboard-footer auth-footer">')[1]
  assert.match(footer, /:class="\{ 'is-error': connectionLost \}"/)
  assert.match(footer, /:role="connectionLost \? 'alert' : 'status'"/)
  assert.match(footer, /class="onboard-footer-status-text">\{\{ authConnectionMessage \}\}/)
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
  assert.match(rule('.onboard-footer-status'), /grid-column: 2 \/ 4;[^}]*justify-content: flex-end;/)
  assert.match(css, /@media \(max-width: 760px\)[\s\S]*?\.auth-footer \{ justify-content: flex-end; padding: 10px 17px; \}/)
  assert.match(css, /@media \(max-width: 760px\)[\s\S]*?\.auth-footer \.onboard-footer-copy:first-child \{ display: none; \}/)
})

test('登录页左下角保留服务端名称和版本，但连接状态只在右下角', () => {
  const sidebar = readFileSync(new URL('../src/renderer/src/components/WorkspaceSidebar.vue', import.meta.url), 'utf8')
  const css = readFileSync(new URL('../src/renderer/src/style.css', import.meta.url), 'utf8')

  // 服务端身份是静态信息，应保留；左侧不能再用绿点表示动态连接状态。
  assert.match(sidebar, /<div class="sidebar-bottom" :class="\{ 'auth-server-details': screen !== 'app' \}">/)
  assert.match(sidebar, /<span v-if="screen === 'app'" class="status-dot"><\/span>/)
  assert.match(sidebar, /\{\{ server\?\.name \|\| 'Nexora ERP' \}\}/)
  assert.match(sidebar, /<small v-if="version">v\{\{ version \}\}<\/small>/)
  assert.match(css, /\.sidebar-bottom\.auth-server-details small \{ margin-left: 0; \}/)
})
