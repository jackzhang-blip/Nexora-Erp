import type { AppState } from '../state'
import type { User, UserProfile } from '../../../../shared/erp-api'

// 账号与角色操作集中在业务模块；写入后仍由统一入口刷新服务端快照。
export function createAccessActions(
  state: AppState,
  perform: (action: () => Promise<unknown>, success: string) => Promise<void>
) {
  const {
    user,
    username,
    password,
    roles,
    permissions,
    permissionLabelDrafts,
    roleDrafts,
    rolePermissionDrafts,
    roleLabelDrafts,
    resetPasswords,
    newUser,
    newRole
  } = state
  async function createUser(): Promise<void> {
    if (!window.nexora) return
    await perform(async () => {
      await window.nexora!.callApi('createUser', {
        full_name: newUser.value.full_name,
        employee_no: newUser.value.employee_no,
        phone: newUser.value.phone,
        username: newUser.value.username,
        password: newUser.value.password,
        roles: [...newUser.value.roles]
      })
      newUser.value = { username: '', password: '', roles: ['viewer'], full_name: '', employee_no: '', phone: '' }
    }, '用户已创建。')
  }

  // 复制表单字段为普通对象，避免将 Vue 代理传入 Electron IPC。
  async function updateUser(userId: number, profile: UserProfile & { roles: string[] }): Promise<void> {
    if (!window.nexora) return
    await perform(async () => {
      const updated = await window.nexora!.callApi('updateUser', {
        userId, full_name: profile.full_name, employee_no: profile.employee_no,
        phone: profile.phone, roles: [...profile.roles]
      })
      if (user.value?.id === userId) user.value = updated
    }, '用户资料和角色已更新。')
  }

  async function saveRoles(userId: number): Promise<void> {
    if (!window.nexora) return
    await perform(async () => {
      await window.nexora!.callApi('setUserRoles', {
        userId,
        roles: [...(roleDrafts.value[userId] ?? [])]
      })
      if (user.value?.id === userId)
        user.value = await window.nexora!.callApi('me', undefined)
    }, '角色已更新。')
  }

  async function createRole(): Promise<void> {
    if (!window.nexora) return
    await perform(async () => {
      // 角色代码只是内部稳定标识，自动生成以免要求管理员理解英文编码。
      const code = `role_${crypto.randomUUID().replaceAll('-', '')}`
      await window.nexora!.callApi('createRole', {
        code,
        label: newRole.value.label,
        permissions: [...newRole.value.permissions]
      })
      newRole.value = { label: '', permissions: [] }
    }, '自定义角色已创建。')
  }

  async function saveRole(code: string): Promise<void> {
    if (!window.nexora) return
    await perform(
      () =>
        window.nexora!.callApi('updateRole', {
          code,
          label: roleLabelDrafts.value[code],
          permissions: [...(rolePermissionDrafts.value[code] ?? [])]
        }),
      '角色权限已更新。'
    )
  }

  async function savePermissionLabel(code: string): Promise<void> {
    if (!window.nexora) return
    await perform(
      () => window.nexora!.callApi('updatePermissionLabel', {
        code,
        label: permissionLabelDrafts.value[code]
      }),
      '权限名称已更新。'
    )
  }

  async function setUserStatus(entry: User): Promise<void> {
    if (!window.nexora) return
    await perform(
      () =>
        window.nexora!.callApi('setUserStatus', {
          userId: entry.id,
          is_active: !entry.is_active
        }),
      entry.is_active ? '账号已停用，原有登录已失效。' : '账号已启用。'
    )
  }

  async function resetUserPassword(userId: number): Promise<void> {
    if (!window.nexora) return
    await perform(async () => {
      await window.nexora!.callApi('resetUserPassword', {
        userId,
        password: resetPasswords.value[userId]
      })
      resetPasswords.value[userId] = ''
    }, '密码已重置，用户需要重新登录。')
  }
  return {
    createUser,
    updateUser,
    saveRoles,
    createRole,
    saveRole,
    savePermissionLabel,
    setUserStatus,
    resetUserPassword
  }
}
