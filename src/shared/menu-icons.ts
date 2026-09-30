// 图标仅从随应用打包的资源中选择，不接受任意 HTML、SVG 或外部地址。
export const menuIconOptions = [
  { key: 'dashboard', label: '工作台' },
  { key: 'stack', label: '库存' },
  { key: 'archive', label: '档案' },
  { key: 'file', label: '单据' },
  { key: 'history', label: '历史' },
  { key: 'team', label: '团队' },
  { key: 'settings', label: '设置' },
  { key: 'warehouse', label: '仓库' },
  { key: 'catalog', label: '资料' },
  { key: 'purchase', label: '采购' },
  { key: 'sales', label: '销售' },
  { key: 'finance', label: '财务' },
  { key: 'production', label: '生产' },
  { key: 'menu', label: '菜单' },
  { key: 'truck', label: '配送' },
  { key: 'chart', label: '报表' },
  { key: 'shield', label: '权限' },
  { key: 'user', label: '用户' },
  { key: 'box', label: '物料' },
  { key: 'search', label: '查询' },
] as const
export type MenuIconKey = (typeof menuIconOptions)[number]['key']
export interface MenuIconSetting { key: string; icon: MenuIconKey | null; version: number }
export function isMenuIconKey(value: unknown): value is MenuIconKey {
  return menuIconOptions.some((option) => option.key === value)
}
// 未配置、已恢复默认或旧数据引用不存在的图标时，始终保留可见的默认图标。
export function resolveMenuIcon(settings: readonly MenuIconSetting[], key: string, fallback: MenuIconKey): MenuIconKey {
  const icon = settings.find((entry) => entry.key === key)?.icon
  return isMenuIconKey(icon) ? icon : fallback
}
