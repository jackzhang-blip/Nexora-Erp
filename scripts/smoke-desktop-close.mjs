const endpoint = process.argv[2]
if (!endpoint) throw new Error('缺少桌面调试地址')

const listPages = async () => (await (await fetch(`${endpoint}/json/list`)).json())
const page = (await listPages()).find((target) => target.type === 'page' && target.title === 'Nexora ERP')
if (!page) throw new Error('关闭检查前找不到桌面窗口')

const socket = new WebSocket(page.webSocketDebuggerUrl)
await new Promise((resolve, reject) => {
  socket.onopen = resolve
  socket.onerror = reject
})
try {
  // 只关闭真实渲染窗口；外层脚本随后检查桌面进程是否仍持有托盘。
  socket.send(JSON.stringify({ id: 1, method: 'Runtime.evaluate', params: { expression: 'window.close()' } }))
  let closed = false
  for (let attempt = 0; attempt < 40; attempt += 1) {
    const pages = await listPages()
    if (!pages.some((target) => target.id === page.id)) { closed = true; break }
    await new Promise((done) => setTimeout(done, 250))
  }
  if (!closed) throw new Error('关闭窗口后，桌面页面仍然存在')
  process.stdout.write('桌面窗口已关闭，继续核对托盘进程。\n')
} finally {
  if (socket.readyState === WebSocket.OPEN) socket.close()
}
