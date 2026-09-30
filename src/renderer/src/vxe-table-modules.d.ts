// vxe 的分组件入口未附带声明；复用官方总入口的组件类型，保持按需加载时的模板检查。
declare module 'vxe-table/es/table' {
  export { VxeTable as default } from 'vxe-table'
}

declare module 'vxe-table/es/column' {
  export { VxeColumn as default } from 'vxe-table'
}

declare module 'vxe-table/es/locale/lang/zh-CN' {
  const locale: Record<string, unknown>
  export default locale
}
