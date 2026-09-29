import { useMessage } from 'naive-ui'

// 页面只调用统一入口，通知位置和默认停留时间由根提供器集中管理。
export function useAppMessage() {
  const message = useMessage()
  return {
    info: (content: string) => message.info(content),
    success: (content: string) => message.success(content),
    warning: (content: string) => message.warning(content),
    error: (content: string) => message.error(content, { duration: 7000 })
  }
}
