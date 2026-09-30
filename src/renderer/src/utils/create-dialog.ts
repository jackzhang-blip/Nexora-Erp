import type { Ref } from 'vue'

interface DialogOperationState {
  busy: Ref<boolean>
  error: Ref<string>
  notice: Ref<string>
}

// 只有业务操作明确写入成功消息才关闭弹窗；失败或提前退出时保留草稿供用户修正。
export async function submitCreateDialog(
  action: () => Promise<void>,
  state: DialogOperationState,
  open: Ref<boolean>
): Promise<void> {
  if (state.busy.value) return
  state.notice.value = ''
  await action()
  if (!state.error.value && state.notice.value) open.value = false
}
