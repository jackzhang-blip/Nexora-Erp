export class DesktopProbeTimeoutError extends Error {
  constructor() {
    super('页面检查超时')
    this.name = 'DesktopProbeTimeoutError'
  }
}

export function readDesktopChoices(socket, id, timeoutMs) {
  return new Promise((resolve, reject) => {
    let timer
    let settled = false
    const finish = (error, value) => {
      if (settled) return
      settled = true
      // 每次请求都清理监听器；超时响应不能污染下一次页面检查。
      clearTimeout(timer)
      socket.removeEventListener('message', onMessage)
      socket.removeEventListener('close', onClose)
      socket.removeEventListener('error', onError)
      if (error) reject(error)
      else resolve(value)
    }
    const onMessage = (event) => {
      let response
      try { response = JSON.parse(event.data) }
      catch { finish(new Error('页面调试响应无效')); return }
      if (response.id !== id) return
      if (response.error) finish(new Error(`页面调试失败：${response.error.message ?? '未知错误'}`))
      else if (response.result?.exceptionDetails) finish(new Error('页面脚本异常'))
      else finish(null, response.result?.result?.value)
    }
    const onClose = () => finish(new Error('桌面调试连接已关闭'))
    const onError = () => finish(new Error('桌面调试连接异常'))
    timer = setTimeout(() => finish(new DesktopProbeTimeoutError()), timeoutMs)
    socket.addEventListener('message', onMessage)
    socket.addEventListener('close', onClose)
    socket.addEventListener('error', onError)
    try {
      socket.send(JSON.stringify({ id, method: 'Runtime.evaluate', params: {
        expression: `({ choices: [...document.querySelectorAll('.choice-card strong')].map((item) => item.textContent), errors: [...document.querySelectorAll('[role=alert]')].map((item) => item.textContent) })`,
        returnByValue: true
      } }))
    } catch (error) { finish(error) }
  })
}

export async function waitForDesktopChoices(socket, options = {}) {
  const { deadlineMs = 30_000, requestTimeoutMs = 5_000, pollIntervalMs = 250 } = options
  const deadline = Date.now() + deadlineMs
  let state
  let timeouts = 0
  let id = 0
  while (Date.now() < deadline) {
    try {
      // 页面导航可能暂时不回复 CDP；仅对超时重试，脚本异常仍立即失败。
      state = await readDesktopChoices(socket, ++id, Math.min(requestTimeoutMs, deadline - Date.now()))
      if (state?.choices?.length === 3) return state
    } catch (error) {
      if (!(error instanceof DesktopProbeTimeoutError)) throw error
      timeouts += 1
    }
    const remaining = deadline - Date.now()
    if (remaining > 0) await new Promise((done) => setTimeout(done, Math.min(pollIntervalMs, remaining)))
  }
  throw new Error(`首次进入页未正确加载：${JSON.stringify({ state, timeouts })}`)
}
