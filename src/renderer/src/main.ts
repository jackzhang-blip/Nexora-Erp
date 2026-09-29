import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import './style.css'
import './light-theme.css'
import './dark-theme.css'
import './theme-transitions.css'

// 每个渲染窗口安装独立 Pinia 实例；系统能力仍只通过预加载桥接调用。
createApp(App).use(createPinia()).mount('#app')
