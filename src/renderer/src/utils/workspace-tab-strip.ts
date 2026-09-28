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

// 把计算结果真正写入滚动容器；页面和标签必须在同一次导航后保持可见。
export function scrollActiveTabIntoView(strip: HTMLElement): void {
  const current = strip.querySelector<HTMLElement>('.workspace-tab.active')
  if (!current) return
  const stripRect = strip.getBoundingClientRect()
  const tabRect = current.getBoundingClientRect()
  const tabLeft = tabRect.left - stripRect.left + strip.scrollLeft
  const tabRight = tabRect.right - stripRect.left + strip.scrollLeft
  const target = visibleTabScrollLeft(
    strip.scrollLeft,
    strip.clientWidth,
    tabLeft,
    tabRight
  )
  if (target !== strip.scrollLeft)
    strip.scrollTo({ left: target, behavior: 'auto' })
}
