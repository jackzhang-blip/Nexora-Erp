export type DashboardPeriod = '7d' | '30d'

export interface DashboardMetric {
  label: string
  value: string
  unit: string
  change: string
  note: string
  tone: 'teal' | 'blue' | 'amber' | 'rose'
}

export interface DashboardSnapshot {
  periodLabel: string
  metrics: readonly DashboardMetric[]
  trend: {
    labels: readonly string[]
    sales: readonly number[]
    purchase: readonly number[]
  }
  composition: readonly { label: string; percent: number; color: string }[]
  pipeline: readonly { label: string; count: number; tone: string }[]
  reminders: readonly { title: string; detail: string; tone: string }[]
}

// 演示快照与页面分离；真实接口接入时只需把同结构的数据交给视图。
export const demoDashboardSnapshots: Record<DashboardPeriod, DashboardSnapshot> = {
  '7d': {
    periodLabel: '近 7 天',
    metrics: [
      { label: '销售额', value: '428,600', unit: '元', change: '+12.8%', note: '较前 7 天', tone: 'teal' },
      { label: '采购金额', value: '186,240', unit: '元', change: '+5.2%', note: '较前 7 天', tone: 'blue' },
      { label: '待处理订单', value: '24', unit: '单', change: '待跟进', note: '采购与销售', tone: 'amber' },
      { label: '库存预警', value: '8', unit: '项', change: '需关注', note: '低于安全库存', tone: 'rose' }
    ],
    trend: {
      labels: ['周一', '周二', '周三', '周四', '周五', '周六', '周日'],
      sales: [31, 44, 37, 53, 48, 68, 61],
      purchase: [20, 29, 25, 34, 30, 39, 33]
    },
    composition: [
      { label: '销售出库', percent: 42, color: '#35b8aa' },
      { label: '采购入库', percent: 29, color: '#5f9de8' },
      { label: '生产完工', percent: 18, color: '#eab867' },
      { label: '仓库调拨', percent: 11, color: '#a3a8e8' }
    ],
    pipeline: [
      { label: '销售订单', count: 36, tone: 'teal' },
      { label: '采购订单', count: 28, tone: 'blue' },
      { label: '生产工单', count: 17, tone: 'amber' }
    ],
    reminders: [
      { title: '采购订单待入库', detail: '6 单 · 请核对到货进度', tone: 'blue' },
      { title: '销售订单待出库', detail: '11 单 · 建议优先处理', tone: 'teal' },
      { title: '物料库存偏低', detail: '8 项 · 请检查补货计划', tone: 'rose' }
    ]
  },
  '30d': {
    periodLabel: '近 30 天',
    metrics: [
      { label: '销售额', value: '1,826,400', unit: '元', change: '+9.6%', note: '较前 30 天', tone: 'teal' },
      { label: '采购金额', value: '742,900', unit: '元', change: '+3.8%', note: '较前 30 天', tone: 'blue' },
      { label: '待处理订单', value: '24', unit: '单', change: '待跟进', note: '采购与销售', tone: 'amber' },
      { label: '库存预警', value: '8', unit: '项', change: '需关注', note: '低于安全库存', tone: 'rose' }
    ],
    trend: {
      labels: ['第 1 周', '第 2 周', '第 3 周', '第 4 周', '本周'],
      sales: [44, 51, 46, 64, 72],
      purchase: [29, 33, 28, 39, 41]
    },
    composition: [
      { label: '销售出库', percent: 46, color: '#35b8aa' },
      { label: '采购入库', percent: 26, color: '#5f9de8' },
      { label: '生产完工', percent: 17, color: '#eab867' },
      { label: '仓库调拨', percent: 11, color: '#a3a8e8' }
    ],
    pipeline: [
      { label: '销售订单', count: 142, tone: 'teal' },
      { label: '采购订单', count: 104, tone: 'blue' },
      { label: '生产工单', count: 73, tone: 'amber' }
    ],
    reminders: [
      { title: '采购订单待入库', detail: '6 单 · 请核对到货进度', tone: 'blue' },
      { title: '销售订单待出库', detail: '11 单 · 建议优先处理', tone: 'teal' },
      { title: '物料库存偏低', detail: '8 项 · 请检查补货计划', tone: 'rose' }
    ]
  }
}

export function trendCoordinates(values: readonly number[], maxValue: number): { x: number; y: number }[] {
  // 空序列及单点序列也保持有限坐标，避免以后真实接口返回稀疏数据时画出 NaN。
  const ceiling = Math.max(1, maxValue)
  return values.map((value, index) => ({
    x: values.length === 1 ? 320 : 28 + index * 584 / (values.length - 1),
    y: 190 - Math.min(ceiling, Math.max(0, value)) / ceiling * 150
  }))
}

export function trendLine(points: readonly { x: number; y: number }[]): string {
  return points.map((point) => `${point.x},${point.y}`).join(' ')
}

export function trendArea(points: readonly { x: number; y: number }[]): string {
  if (points.length === 0) return ''
  return `M ${points[0].x} 190 L ${points.map((point) => `${point.x} ${point.y}`).join(' L ')} L ${points[points.length - 1].x} 190 Z`
}
