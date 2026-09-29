<script setup lang="ts">
import { ref } from 'vue'
import type { PermissionModule } from '../../utils/permission-tree'
import {
  documentPermissionCodes,
  modulePermissionCodes,
  selectedPermissionCount,
  togglePermissionCodes
} from '../../utils/permission-tree'

const props = defineProps<{
  modules: PermissionModule[]
  modelValue: string[]
  disabled?: boolean
  readonly?: boolean
}>()
const emit = defineEmits<{ 'update:modelValue': [codes: string[]] }>()
// 展开状态只影响页面浏览；勾选状态由角色草稿持有，切换页面也不会丢失。
const expandedModules = ref<Record<string, boolean>>({})
const expandedDocuments = ref<Record<string, boolean>>({})

function toggleCodes(codes: string[], event: Event): void {
  if (props.disabled || props.readonly) return
  const checked = (event.target as HTMLInputElement).checked
  emit('update:modelValue', togglePermissionCodes(props.modelValue, codes, checked))
}

function documentKey(moduleCode: string, documentCode: string): string {
  return `${moduleCode}/${documentCode}`
}
</script>

<template>
  <div class="permission-tree">
    <div v-for="module in modules" :key="module.code" class="permission-tree-module">
      <div class="permission-tree-heading">
        <input
          type="checkbox"
          :aria-label="`选择${module.label}全部操作`"
          :checked="selectedPermissionCount(modelValue, modulePermissionCodes(module)) === modulePermissionCodes(module).length"
          :indeterminate="selectedPermissionCount(modelValue, modulePermissionCodes(module)) > 0 && selectedPermissionCount(modelValue, modulePermissionCodes(module)) < modulePermissionCodes(module).length"
          :disabled="disabled || readonly"
          @change="toggleCodes(modulePermissionCodes(module), $event)"
        />
        <button
          class="permission-tree-expand"
          type="button"
          :aria-expanded="Boolean(expandedModules[module.code])"
          @click="expandedModules[module.code] = !expandedModules[module.code]"
        >
          <span aria-hidden="true">{{ expandedModules[module.code] ? '▾' : '▸' }}</span>
          <strong>{{ module.label }}</strong>
          <small>{{ selectedPermissionCount(modelValue, modulePermissionCodes(module)) }}/{{ modulePermissionCodes(module).length }}</small>
        </button>
      </div>
      <div v-if="expandedModules[module.code]" class="permission-tree-children" role="group" :aria-label="module.label">
        <div
          v-for="document in module.documents"
          :key="document.code"
          class="permission-tree-document"
        >
          <div class="permission-tree-heading">
            <input
              type="checkbox"
              :aria-label="`选择${document.label}全部操作`"
              :checked="selectedPermissionCount(modelValue, documentPermissionCodes(document)) === document.permissions.length"
              :indeterminate="selectedPermissionCount(modelValue, documentPermissionCodes(document)) > 0 && selectedPermissionCount(modelValue, documentPermissionCodes(document)) < document.permissions.length"
              :disabled="disabled || readonly"
              @change="toggleCodes(documentPermissionCodes(document), $event)"
            />
            <button
              class="permission-tree-expand"
              type="button"
              :aria-expanded="Boolean(expandedDocuments[documentKey(module.code, document.code)])"
              @click="expandedDocuments[documentKey(module.code, document.code)] = !expandedDocuments[documentKey(module.code, document.code)]"
            >
              <span aria-hidden="true">{{ expandedDocuments[documentKey(module.code, document.code)] ? '▾' : '▸' }}</span>
              <span>{{ document.label }}</span>
              <small>{{ selectedPermissionCount(modelValue, documentPermissionCodes(document)) }}/{{ document.permissions.length }}</small>
            </button>
          </div>
          <div
            v-if="expandedDocuments[documentKey(module.code, document.code)]"
            class="permission-tree-leaves"
            role="group"
            :aria-label="document.label"
          >
            <label v-for="permission in document.permissions" :key="permission.code" class="check">
              <input
                type="checkbox"
                :checked="modelValue.includes(permission.code)"
                :disabled="disabled || readonly"
                @change="toggleCodes([permission.code], $event)"
              />
              {{ permission.label }}
            </label>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
