const endpoint = process.argv[2]
if (!endpoint) throw new Error('缺少桌面调试地址')

// 等待打包后的窗口出现，再读取页面实际渲染出的三个启动入口。
let page
for (let attempt = 0; attempt < 80; attempt += 1) {
  try {
    const targets = await (await fetch(`${endpoint}/json/list`)).json()
    page = targets.find((target) => target.type === 'page' && target.title === 'Nexora ERP')
    if (page) break
  } catch { /* Electron 还在启动。 */ }
  await new Promise((done) => setTimeout(done, 250))
}
if (!page) throw new Error('打包后的桌面窗口未启动')

const socket = new WebSocket(page.webSocketDebuggerUrl)
await new Promise((resolve, reject) => {
  socket.onopen = resolve
  socket.onerror = reject
})

async function readChoices() {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('页面检查超时')), 5000)
    const listener = (event) => {
      const response = JSON.parse(event.data)
      if (response.id !== 1) return
      clearTimeout(timer)
      socket.removeEventListener('message', listener)
      if (response.result?.exceptionDetails) reject(new Error('页面脚本异常'))
      else resolve(response.result?.result?.value)
    }
    socket.addEventListener('message', listener)
    socket.send(JSON.stringify({ id: 1, method: 'Runtime.evaluate', params: {
      expression: `({ choices: [...document.querySelectorAll('.choice-card strong')].map((item) => item.textContent), errors: [...document.querySelectorAll('[role=alert]')].map((item) => item.textContent) })`,
      returnByValue: true
    } }))
  })
}

try {
  let state
  for (let attempt = 0; attempt < 40; attempt += 1) {
    state = await readChoices()
    if (state?.choices?.length === 3) break
    await new Promise((done) => setTimeout(done, 250))
  }
  const expected = ['连接服务端', '扫描局域网', '新建服务端']
  if (JSON.stringify(state?.choices) !== JSON.stringify(expected) || state.errors.length) {
    throw new Error(`首次进入页未正确加载：${JSON.stringify(state)}`)
  }
  process.stdout.write('桌面首次进入页已加载三个启动入口。\n')
} finally {
  socket.close()
}
