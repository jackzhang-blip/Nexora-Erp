// 各业务单据按同一顺序展示，具体内容与操作仍由页面插槽决定。
export const recordColumns = [
  { key: 'document', title: '单据', width: '28%' },
  { key: 'status', title: '状态', width: '120' },
  { key: 'details', title: '业务明细' },
  { key: 'actions', title: '操作', width: '280' }
] as const

// 仅搜索页面明确提供的可见字段，避免把内部数据或密码等字段纳入搜索。
export function matchesRecordQuery(query: string, values: readonly unknown[]): boolean {
  const keyword = query.trim().toLocaleLowerCase()
  return !keyword || values.filter(value => value != null).join(' ').toLocaleLowerCase().includes(keyword)
}
