// 渲染进程只能调用这里列出的桌面能力，后续新增接口也应先定义清楚类型。
export interface DesktopApi {
  getVersion: () => Promise<string>
}
