<script setup lang="ts">
import { onUnmounted } from 'vue'
import { useAppStore } from '../../store/app-store'
import { useAppMessage } from '../../composables/use-app-message'
import { observeAppMessageFeedback } from '../../utils/app-message-feedback'

const { notice, error } = useAppStore()
const message = useAppMessage()

// 桥接现有业务状态，所有页面的成功与失败反馈都复用同一个右上角通知层。
const stop = observeAppMessageFeedback({ notice, error }, (tone, content) => {
  message[tone](content)
})
onUnmounted(stop)
</script>

<template></template>
