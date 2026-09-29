import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  THEME_STORAGE_KEY,
  readThemePreference,
  saveThemePreference
} from '../src/renderer/src/utils/theme-preference.ts'

test('主题设置只接受已保存的深色值，其余情况回到浅色', () => {
  // 清空、损坏或无法访问的设置都不能让界面落入未知主题。
  assert.equal(readThemePreference({ getItem: () => 'dark' }), 'dark')
  assert.equal(readThemePreference({ getItem: () => 'invalid' }), 'light')
  assert.equal(readThemePreference({ getItem: () => null }), 'light')
  assert.equal(readThemePreference({ getItem: () => { throw new Error('blocked') } }), 'light')
  assert.equal(readThemePreference(undefined), 'light')
})

test('主题切换写入固定键，存储失败时仍可继续切换界面', () => {
  const values = new Map()
  const storage = {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value)
  }

  saveThemePreference(storage, 'dark')
  assert.equal(values.get(THEME_STORAGE_KEY), 'dark')
  assert.equal(readThemePreference(storage), 'dark')
  saveThemePreference(storage, 'light')
  assert.equal(readThemePreference(storage), 'light')
  assert.doesNotThrow(() => saveThemePreference({ setItem: () => { throw new Error('blocked') } }, 'dark'))
})
