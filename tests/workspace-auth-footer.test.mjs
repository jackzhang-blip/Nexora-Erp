import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'

test('登录和工作台共用底栏，业务提示留在页面内', () => {
  const shell = readFileSync(new URL('../src/renderer/src/views/WorkspaceShell.vue', import.meta.url), 'utf8')
  const onboarding = readFileSync(new URL('../src/renderer/src/views/OnboardingView.vue', import.meta.url), 'utf8')
  const footer = readFileSync(new URL('../src/renderer/src/components/AppStatusFooter.vue', import.meta.url), 'utf8')

  // 所有阶段只实例化同一个底栏，避免工作台遗漏连接状态。
  assert.match(shell, /<AppStatusFooter \/>/)
  assert.match(onboarding, /<AppStatusFooter \/>/)
  assert.doesNotMatch(shell, /<footer v-if="isAuthScreen"/)
  assert.match(shell, /v-if="notice" class="message success" role="status"/)
  assert.match(shell, /v-if="error" class="message error" role="alert"/)
  assert.doesNotMatch(shell, /v-if="connectionLost" class="message/)
  assert.match(footer, /server\?\.name \|\| '未选择服务端'/)
  assert.match(footer, /server\?\.version/)
  assert.match(footer, /:role="status\.tone === 'error' \? 'alert' : 'status'"/)
})

test('页面内容滚动时，公共底栏仍固定在视口底部', () => {
  const css = readFileSync(new URL('../src/renderer/src/style.css', import.meta.url), 'utf8')
  const rule = (selector) => css.match(new RegExp(`${selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')} \\{([^}]+)\\}`, 'm'))?.[1] ?? ''

  // 滚动区域和底栏必须属于同一个定高列容器，长库存页才不会盖住底栏。
  assert.match(rule('.app-shell'), /height: 100vh;[^}]*overflow: hidden;/)
  assert.match(rule('.content'), /height: 100vh;[^}]*flex-direction: column;[^}]*overflow: hidden;/)
  assert.match(rule('.content-body'), /min-height: 0;[^}]*flex: 1;[^}]*overflow-y: auto;/)
  assert.match(rule('.onboard-footer'), /flex: none;/)
  assert.match(rule('.app-status-footer'), /grid-template-columns: minmax\(0, 1fr\) minmax\(0, 1fr\);/)
  assert.match(css, /@media \(max-width: 760px\)[\s\S]*?\.content \{ height: auto; min-height: 0; flex: 1; \}/)
})

test('侧栏底部显示当前用户、角色和退出，服务端身份交给公共底栏', () => {
  const sidebar = readFileSync(new URL('../src/renderer/src/components/WorkspaceSidebar.vue', import.meta.url), 'utf8')
  const shell = readFileSync(new URL('../src/renderer/src/views/WorkspaceShell.vue', import.meta.url), 'utf8')
  const css = readFileSync(new URL('../src/renderer/src/style.css', import.meta.url), 'utf8')

  // 登录前不显示旧用户；小窗口收起侧栏后，右上角保留同一退出入口。
  assert.match(sidebar, /v-if="screen === 'app' && user" class="sidebar-bottom sidebar-account"/)
  assert.match(sidebar, /class="sidebar-account-name">\{\{ user\.username \}\}/)
  assert.match(sidebar, /class="sidebar-account-roles">\{\{ user\.roles\.join\(' · '\) \}\}/)
  assert.match(sidebar, /class="sidebar-logout"[^>]*@click="logout"/)
  assert.doesNotMatch(sidebar, /<small v-if="version"/)
  assert.match(shell, /v-if="user" class="account"[\s\S]*?@click="logout"/)
  assert.match(css, /\.account \{ display: none;/)
  assert.match(css, /@media \(max-width: 760px\)[\s\S]*?\.account \{ display: flex; \}/)
})
