import assert from 'node:assert/strict'
import { test } from 'node:test'
import { computed, isRef, ref } from 'vue'
import { createPinia, defineStore, setActivePinia } from 'pinia'
import { storeBindings } from '../src/renderer/src/store/store-bindings.ts'

const useExampleStore = defineStore('pinia-bindings-example', () => {
  const count = ref(0)
  const doubled = computed(() => count.value * 2)
  function increment() { count.value += 1 }
  return { count, doubled, increment }
})

test('Pinia 状态解构后仍是响应式 ref，操作方法共用同一实例', () => {
  setActivePinia(createPinia())
  const first = storeBindings(useExampleStore())
  const second = storeBindings(useExampleStore())

  // 页面保留既有的 .value 访问方式，状态变化同时反映在另一个页面和计算值中。
  assert.equal(isRef(first.count), true)
  assert.equal(isRef(first.doubled), true)
  first.increment()
  assert.equal(first.count.value, 1)
  assert.equal(first.doubled.value, 2)
  assert.equal(second.count.value, 1)
})

test('不同 Pinia 实例之间的状态相互隔离', () => {
  setActivePinia(createPinia())
  const first = storeBindings(useExampleStore())
  first.increment()

  setActivePinia(createPinia())
  const second = storeBindings(useExampleStore())
  assert.equal(second.count.value, 0)
})
