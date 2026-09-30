export interface TableScrollbarMetrics {
  max: number
  thumbWidth: number
}

// 滚动手柄按可视区域比例缩放，窄表格仍保留足够大的拖动目标。
export function tableScrollbarMetrics(clientWidth: number, scrollWidth: number): TableScrollbarMetrics {
  const visible = Math.max(0, clientWidth)
  const total = Math.max(visible, scrollWidth)
  return {
    max: Math.max(0, total - visible),
    thumbWidth: total ? Math.min(visible, Math.max(44, Math.round(visible * visible / total))) : 0
  }
}
