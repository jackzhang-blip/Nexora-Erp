import type { AppState } from '../state'
import type { MenuIconKey } from '../../../../shared/menu-icons'
import { displayError } from '../../utils/formatters.ts'

// 菜单配置单独加载与保存，业务列表失败不影响图标编辑；失败时保留原快照。
export function createMenuActions(state: AppState) {
  async function loadMenuIcons(): Promise<void> {
    if (!window.nexora || !state.user.value) return
    const user = state.user.value
    const server = state.server.value
    const entries = await window.nexora.callApi('menuIcons', undefined)
    if (state.user.value === user && state.server.value === server) state.menuIcons.value = entries
  }

  async function saveMenuIcon(key: string, icon: MenuIconKey | null, version: number): Promise<boolean> {
    if (!window.nexora || !state.user.value || state.busy.value) return false
    if (state.connectionLost.value) {
      state.error.value = '服务端连接已中断，恢复连接后才能保存更改。'
      return false
    }
    const user = state.user.value
    const server = state.server.value
    state.busy.value = true
    state.error.value = ''
    state.notice.value = ''
    try {
      const updated = await window.nexora.callApi('saveMenuIcon', { key, icon, version })
      // 切换服务或退出后，不把之前请求的配置写入新会话。
      if (state.user.value !== user || state.server.value !== server) return false
      state.menuIcons.value = [...state.menuIcons.value.filter((entry) => entry.key !== key), updated]
      state.notice.value = icon === null ? '已恢复默认图标。' : '菜单图标已保存。'
      return true
    } catch (cause) {
      state.error.value = displayError(cause)
      return false
    } finally {
      state.busy.value = false
    }
  }
  return { loadMenuIcons, saveMenuIcon }
}
