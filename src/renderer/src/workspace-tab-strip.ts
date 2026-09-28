// 只在当前标签离开可视范围时移动页面栏，避免每次切换都重置用户的滚动位置。
export function visibleTabScrollLeft(
  scrollLeft: number,
  viewportWidth: number,
  tabLeft: number,
  tabRight: number
): number {
  if (tabLeft < scrollLeft) return Math.max(0, tabLeft)
  if (tabRight > scrollLeft + viewportWidth) return tabRight - viewportWidth
  return scrollLeft
}
