import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import { ref } from 'vue'
import { observeAppMessageFeedback } from '../src/renderer/src/utils/app-message-feedback.ts'

test('全局反馈只在新消息出现时发出，清空后相同操作仍会再次提示', () => {
  const notice = ref('')
  const error = ref('')
  const shown = []
  const stop = observeAppMessageFeedback({ notice, error }, (tone, content) => {
    shown.push({ tone, content })
  })

  notice.value = '库存已切换。'
  notice.value = ''
  notice.value = '库存已切换。'
  error.value = '刷新失败'
  error.value = ''
  assert.deepEqual(shown, [
    { tone: 'success', content: '库存已切换。' },
    { tone: 'success', content: '库存已切换。' },
    { tone: 'error', content: '刷新失败' }
  ])

  stop()
  notice.value = '数据已刷新。'
  assert.equal(shown.length, 3)
})

test('全应用提供右上角通知，工作台不再渲染整行成功与失败横幅', () => {
  const app = readFileSync(new URL('../src/renderer/src/App.vue', import.meta.url), 'utf8')
  const provider = readFileSync(new URL('../src/renderer/src/components/AppMessageProvider.vue', import.meta.url), 'utf8')
  const bridge = readFileSync(new URL('../src/renderer/src/components/AppMessageBridge.vue', import.meta.url), 'utf8')
  const shell = readFileSync(new URL('../src/renderer/src/views/WorkspaceShell.vue', import.meta.url), 'utf8')

  // 提供器必须包住引导页和工作台，桥接器才能在任何页面收到业务反馈。
  assert.match(app, /<AppMessageProvider>[\s\S]*<OnboardingView[\s\S]*<WorkspaceShell v-else \/>[\s\S]*<\/AppMessageProvider>/)
  assert.match(provider, /<NMessageProvider placement="top-right"/)
  assert.doesNotMatch(provider, /:max=/)
  assert.match(provider, /<AppMessageBridge \/>/)
  assert.match(bridge, /observeAppMessageFeedback\(\{ notice, error \}/)
  assert.doesNotMatch(shell, /class="message (?:success|error)"/)
})
