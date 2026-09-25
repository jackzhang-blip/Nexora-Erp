import { createApp } from 'vue'
import App from './App.vue'
import './style.css'

// Vue 只负责界面；需要系统能力时通过预加载脚本提供的接口调用。
createApp(App).mount('#app')
