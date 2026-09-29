import type { Role } from '../../../shared/erp-api'

// 普通账号无权读取角色列表；内置角色的固定名称与服务端初始化资料保持一致。
const builtinRoleLabels: Record<string, string> = {
  admin: '管理员',
  buyer: '采购员',
  warehouse: '仓库员',
  viewer: '查看员',
  seller: '销售员',
  finance: '财务员',
  planner: '生产计划员'
}

// 自定义角色资料不可读取时保留真实代码，不猜测用户的职位。
export function accountRoleText(
  codes: readonly string[],
  availableRoles: readonly Pick<Role, 'code' | 'label'>[]
): string {
  if (!codes.length) return '未分配角色'
  return codes
    .map((code) => availableRoles.find((role) => role.code === code)?.label ?? builtinRoleLabels[code] ?? code)
    .join(' · ')
}
