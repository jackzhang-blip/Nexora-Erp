import assert from 'node:assert/strict'
import { test } from 'node:test'
import { readFileSync } from 'node:fs'
import { ref } from 'vue'
import { menuIconOptions, resolveMenuIcon } from '../src/shared/menu-icons.ts'
import { workspaceRouteGroups, canVisitRoute, routeByKey } from '../src/renderer/src/router/workspace-routes.ts'
import { createMenuActions } from '../src/renderer/src/store/modules/menu-actions.ts'

test('菜单和图标白名单覆盖所有实际导航，未知图标回退且管理入口受权限保护', () => {
  const backend = readFileSync(new URL('../backend/app/access/menus.py', import.meta.url), 'utf8')
  const parse = name => [...backend.match(new RegExp(`${name} = (\\{[\\s\\S]*?\\})`))[1].matchAll(/'([^']+)'/g)].map(m => m[1]).sort()
  const keys = workspaceRouteGroups.flatMap(group => [
    ...(group.key === 'home' ? [] : [`group:${group.key}`]), ...group.routes.map(route => `route:${route.key}`)
  ])
  assert.deepEqual(parse('MENU_KEYS'), keys.sort())
  assert.deepEqual(parse('ICON_KEYS'), menuIconOptions.map(icon => icon.key).sort())
  for (const group of workspaceRouteGroups) {
    for (const icon of [group.icon, ...group.routes.map(route => route.icon)]) assert.ok(menuIconOptions.some(option => option.key === icon))
  }
  assert.equal(resolveMenuIcon([{key:'group:warehouse',icon:'truck'}], 'group:warehouse', 'warehouse'), 'truck')
  assert.equal(resolveMenuIcon([{key:'group:warehouse',icon:'malicious'}], 'group:warehouse', 'warehouse'), 'warehouse')
  assert.equal(resolveMenuIcon([{key:'group:warehouse',icon:null}], 'group:warehouse', 'warehouse'), 'warehouse')
  assert.equal(canVisitRoute(routeByKey('menuManagement'), []), false)
  assert.equal(canVisitRoute(routeByKey('menuManagement'), ['users.manage']), true)
})

test('保存后更新共享快照，冲突与断线保留原值，IPC 只传普通字段', async t => {
  const old = globalThis.window
  t.after(() => { globalThis.window = old })
  const state = { user:ref({id:1}),server:ref({instanceId:'one'}), menuIcons:ref([{key:'group:warehouse',icon:'warehouse',version:1}]), busy:ref(false),connectionLost:ref(false),error:ref(''),notice:ref('') }
  let fail = false
  const calls = []
  globalThis.window = {nexora:{async callApi(action,payload) {
    calls.push([action,structuredClone(payload)])
    if (fail) throw new Error('图标已被修改')
    return {...payload,version:payload.version+1}
  }}}
  const actions = createMenuActions(state)
  assert.equal(await actions.saveMenuIcon('group:warehouse','truck',1),true)
  assert.deepEqual(state.menuIcons.value,[{key:'group:warehouse',icon:'truck',version:2}])
  assert.deepEqual(calls[0],['saveMenuIcon',{key:'group:warehouse',icon:'truck',version:1}])
  fail=true
  assert.equal(await actions.saveMenuIcon('group:warehouse',null,1),false)
  assert.equal(state.menuIcons.value[0].icon,'truck')
  assert.match(state.error.value,/已被修改/)
  state.connectionLost.value=true
  assert.equal(await actions.saveMenuIcon('group:warehouse','box',2),false)
  assert.equal(calls.length,2)
  state.connectionLost.value=false;fail=false
  assert.equal(await actions.saveMenuIcon('group:warehouse',null,2),true)
  assert.equal(state.menuIcons.value[0].icon,null)
})

test('切换服务期间到达的旧配置不写入新会话', async t => {
  const old=globalThis.window;t.after(()=>{globalThis.window=old})
  let complete
  globalThis.window={nexora:{callApi:()=>new Promise(resolve=>{complete=resolve})}}
  const state={user:ref({id:1}),server:ref({instanceId:'one'}),menuIcons:ref([])}
  const actions=createMenuActions(state)
  const loading=actions.loadMenuIcons()
  state.server.value={instanceId:'two'}
  complete([{key:'route:home',icon:'truck',version:1}])
  await loading
  assert.deepEqual(state.menuIcons.value,[])
})

test('桌面桥接使用固定菜单接口并携带会话，冲突信息交给页面展示', async t => {
  const {callBackend} = await import('../src/main/backend.ts')
  const calls = []
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    calls.push({path:url.pathname,...options})
    if (url.pathname.endsWith('/auth/login')) return Response.json({token:'test-menu-token',user:{id:1}})
    if (options.method === 'PUT') return Response.json({detail:'该图标已被其他管理员修改'}, {status:409})
    return Response.json([])
  })
  await callBackend('login',{username:'admin',password:'test-password'})
  assert.deepEqual(await callBackend('menuIcons',undefined),[])
  await assert.rejects(callBackend('saveMenuIcon',{key:'route:home',icon:'chart',version:0}),/已被其他管理员修改/)
  assert.equal(calls[1].path,'/api/v1/menu-icons')
  assert.equal(calls[1].headers.Authorization,'Bearer test-menu-token')
  assert.equal(calls[2].path,'/api/v1/menu-icons')
  assert.deepEqual(JSON.parse(calls[2].body),{key:'route:home',icon:'chart',version:0})
})
