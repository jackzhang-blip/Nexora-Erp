<script setup lang="ts">
import { computed, ref } from 'vue'
import { useAppStore } from '../store/app-store'
import IconUser3Line from '~icons/ri/user-3-line'
import IconArrowDownSLine from '~icons/ri/arrow-down-s-line'
import IconLogoutBoxRLine from '~icons/ri/logout-box-r-line'
import { accountRoleText } from '../utils/account-role'

const { user, roles, logout } = useAppStore()
const card = ref<HTMLElement | null>(null)
const menuOpen = ref(false)

const roleText = computed(() => accountRoleText(user.value?.roles ?? [], roles.value))

function closeWhenFocusLeaves(event: FocusEvent): void {
  if (!(event.relatedTarget instanceof Node) || !card.value?.contains(event.relatedTarget))
    menuOpen.value = false
}

function closeWhenPointerLeaves(): void {
  // 只为可见的键盘焦点保留菜单；鼠标点击后的普通焦点不阻止悬停菜单收起。
  if (!card.value?.contains(document.activeElement) || !document.activeElement?.matches(':focus-visible'))
    menuOpen.value = false
}

function closeOnEscape(): void {
  menuOpen.value = false
  // 释放焦点，避免后续 focusin 把刚关闭的菜单再次打开。
  if (document.activeElement instanceof HTMLElement) document.activeElement.blur()
}
</script>

<template>
  <div
    v-if="user"
    ref="card"
    class="sidebar-account"
    @mouseenter="menuOpen = true"
    @mouseleave="closeWhenPointerLeaves"
    @focusin="menuOpen = true"
    @focusout="closeWhenFocusLeaves"
    @keydown.esc.stop="closeOnEscape"
  >
    <button
      class="sidebar-account-card"
      type="button"
      :aria-expanded="menuOpen"
      aria-controls="sidebar-account-menu"
      @click="menuOpen = true"
    >
      <span class="sidebar-account-avatar" aria-hidden="true"><IconUser3Line /></span>
      <span class="sidebar-account-identity">
        <strong :title="user.username">{{ user.username }}</strong>
        <small :title="roleText">{{ roleText }}</small>
      </span>
      <IconArrowDownSLine class="sidebar-account-chevron" aria-hidden="true" />
    </button>
    <div v-show="menuOpen" id="sidebar-account-menu" class="sidebar-account-menu">
      <button type="button" @click="logout">
        <IconLogoutBoxRLine aria-hidden="true" />退出登录
      </button>
    </div>
  </div>
</template>
