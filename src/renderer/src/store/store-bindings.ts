import { storeToRefs } from 'pinia'
import type { StoreGeneric } from 'pinia'

// 旧页面依赖 ref 解构；Pinia 状态需转成 ref，操作方法则继续由原 store 提供。
export function storeBindings<T extends StoreGeneric>(store: T) {
  return { ...store, ...storeToRefs(store) }
}
