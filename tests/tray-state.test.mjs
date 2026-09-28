import assert from 'node:assert/strict'
import { test } from 'node:test'
import { keepDesktopInTray, trayServiceLabel } from '../src/main/tray-state.ts'

test('Windows 和 macOS 关窗后保留桌面托盘', () => {
  assert.equal(keepDesktopInTray('win32'), true)
  assert.equal(keepDesktopInTray('darwin'), true)
  assert.equal(keepDesktopInTray('linux'), false)
})

test('托盘准确区分运行、停止、未配置、迁移和读取失败', () => {
  assert.equal(trayServiceLabel({ configured: true, running: true }), '本机服务：运行中')
  assert.equal(trayServiceLabel({ configured: true, running: false }), '本机服务：已停止')
  assert.equal(trayServiceLabel({ configured: false, running: false }), '本机服务：未配置')
  assert.equal(trayServiceLabel({ configured: true, running: false, migrationNeeded: true }), '本机服务：需要迁移')
  assert.equal(trayServiceLabel(null), '本机服务：状态读取失败')
})
