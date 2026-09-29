import type { Role } from '../../../shared/erp-api'

export type RoleKindFilter = 'all' | 'builtin' | 'custom'

export function filterRoleRows(roles: readonly Role[], query: string, kind: RoleKindFilter): Role[] {
  // 搜索只影响当前列表展示，角色权限和服务端数据不随筛选改变。
  const keyword = query.trim().toLocaleLowerCase()
  return roles.filter((role) => {
    if (kind === 'builtin' && !role.is_builtin) return false
    if (kind === 'custom' && role.is_builtin) return false
    return !keyword || role.label.toLocaleLowerCase().includes(keyword)
  })
}
