import assert from 'node:assert/strict'
import { test } from 'node:test'
import { ref, reactive } from 'vue'
import { createAccessActions } from '../src/renderer/src/store/modules/access-actions.ts'

test('资料写入使用普通 IPC 数据，失败保留草稿，开关等待服务端快照', async t => {
  const original = globalThis.window
  t.after(() => { globalThis.window = original })
  const calls = []
  let fail = false
  globalThis.window = { nexora: { async callApi(action, payload) {
    const copy = structuredClone(payload)
    calls.push([action, copy])
    if (fail) throw new Error('工号冲突')
    return { id: 1, ...copy }
  } } }
  const state = { user: ref({id:1}), newUser: ref({username:'worker', password:'secret-password', full_name:'张三', employee_no:'E01', phone:'13800138000', roles:['viewer']}), resetPasswords: ref({2:'new-password-123'}) }
  const actions = createAccessActions(state, async action => {
    try { await action() } catch { /* 模拟共享反馈层：错误展示后保留表单。 */ }
  })
  const draft = reactive({full_name:'李四', employee_no:'E02', phone:'13900139000', roles:['buyer']})
  await actions.updateUser(1, draft)
  assert.deepEqual(calls[0], ['updateUser', {userId:1, ...draft}])
  assert.equal(state.user.value.full_name, '李四')
  fail = true
  await actions.createUser()
  assert.equal(state.newUser.value.employee_no, 'E01')
  await actions.updateUser(1, {...draft, full_name:'失败修改'})
  assert.equal(state.user.value.full_name, '李四')
  const entry = {id:2, is_active:true}
  await actions.setUserStatus(entry)
  assert.equal(entry.is_active, true)
  await actions.resetUserPassword(2)
  assert.equal(state.resetPasswords.value[2], 'new-password-123')
  fail = false
  await actions.createUser()
  assert.equal(state.newUser.value.employee_no, '')
  await actions.resetUserPassword(2)
  assert.equal(state.resetPasswords.value[2], '')
})
