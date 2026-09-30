import Icon0 from '~icons/ri/dashboard-line'
import Icon1 from '~icons/ri/stack-line'
import Icon2 from '~icons/ri/archive-line'
import Icon3 from '~icons/ri/file-list-3-line'
import Icon4 from '~icons/ri/history-line'
import Icon5 from '~icons/ri/team-line'
import Icon6 from '~icons/ri/settings-3-line'
import Icon7 from '~icons/ri/building-3-line'
import Icon8 from '~icons/ri/folders-line'
import Icon9 from '~icons/ri/shopping-cart-2-line'
import Icon10 from '~icons/ri/store-2-line'
import Icon11 from '~icons/ri/wallet-3-line'
import Icon12 from '~icons/ri/tools-line'
import Icon13 from '~icons/ri/menu-2-line'
import Icon14 from '~icons/ri/truck-line'
import Icon15 from '~icons/ri/bar-chart-box-line'
import Icon16 from '~icons/ri/shield-keyhole-line'
import Icon17 from '~icons/ri/user-line'
import Icon18 from '~icons/ri/box-3-line'
import Icon19 from '~icons/ri/search-line'
import type { Component } from 'vue'
import type { MenuIconKey } from '../../../shared/menu-icons'

// 显式导入保证离线可用，并且只打包可选择的图标。
export const menuIconComponents: Record<MenuIconKey, Component> = {
  dashboard: Icon0,
  stack: Icon1,
  archive: Icon2,
  file: Icon3,
  history: Icon4,
  team: Icon5,
  settings: Icon6,
  warehouse: Icon7,
  catalog: Icon8,
  purchase: Icon9,
  sales: Icon10,
  finance: Icon11,
  production: Icon12,
  menu: Icon13,
  truck: Icon14,
  chart: Icon15,
  shield: Icon16,
  user: Icon17,
  box: Icon18,
  search: Icon19,
}
