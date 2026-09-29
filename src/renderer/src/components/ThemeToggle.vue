<script setup lang="ts">
import { NButton } from 'naive-ui'
import IconMoonLine from '~icons/ri/moon-line'
import IconSunLine from '~icons/ri/sun-line'
import { storeToRefs } from 'pinia'
import { useThemeStore } from '../store/theme-store'

// 窄窗口的顶部账号区复用同一个图标按钮，避免侧栏收起后无法切换主题。
const theme = useThemeStore()
const { isDarkTheme } = storeToRefs(theme)
const { setDarkTheme } = theme
</script>

<template>
  <NButton
    class="theme-toggle"
    quaternary
    circle
    size="small"
    :aria-label="isDarkTheme ? '切换为浅色模式' : '切换为深色模式'"
    :title="isDarkTheme ? '切换为浅色模式' : '切换为深色模式'"
    @click="setDarkTheme(!isDarkTheme)"
  >
    <template #icon>
      <Transition name="theme-icon" mode="out-in">
        <IconSunLine v-if="isDarkTheme" key="sun" aria-hidden="true" />
        <IconMoonLine v-else key="moon" aria-hidden="true" />
      </Transition>
    </template>
  </NButton>
</template>
