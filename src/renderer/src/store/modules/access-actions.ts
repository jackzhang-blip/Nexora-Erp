import type { AppState } from '../state'
import type { User } from '../../../../shared/erp-api'

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
        username: newUser.value.username,
        password: newUser.value.password,
        roles: [...newUser.value.roles]
      })
      newUser.value = { username: '', password: '', roles: ['viewer'] }
    }, '用户已创建。')
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
    saveRoles,
    createRole,
    saveRole,
    setUserStatus,
    resetUserPassword
  }
}
