import assert from 'node:assert/strict'
import { test } from 'node:test'
import { ref } from 'vue'
import { submitCreateDialog } from '../src/renderer/src/utils/create-dialog.ts'

test('新增成功后关闭弹窗，连续使用相同成功文案仍可关闭', async () => {
  const state = { busy: ref(false), error: ref(''), notice: ref('物料已创建。') }
  const open = ref(true)
  await submitCreateDialog(async () => { state.notice.value = '物料已创建。' }, state, open)
  assert.equal(open.value, false)
})

test('保存失败或业务操作提前退出时保留弹窗和草稿', async () => {
  const state = { busy: ref(false), error: ref(''), notice: ref('旧的成功消息') }
  const open = ref(true)
  await submitCreateDialog(async () => { state.error.value = '服务端拒绝保存' }, state, open)
  assert.equal(open.value, true)
  assert.equal(state.notice.value, '')

  state.error.value = ''
  await submitCreateDialog(async () => {}, state, open)
  assert.equal(open.value, true)
})

test('提交仍在进行时忽略重复提交', async () => {
  const state = { busy: ref(true), error: ref(''), notice: ref('') }
  const open = ref(true)
  let calls = 0
  await submitCreateDialog(async () => { calls++ }, state, open)
  assert.equal(calls, 0)
  assert.equal(open.value, true)
})
