import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import { usePiniaAppStore } from './store/app-store'
import { workspaceRouter } from './router/browser-router'
import { installWorkspaceAccessGuard } from './router'
import './style.css'
import './light-theme.css'
import './dark-theme.css'
import './theme-transitions.css'

// 先建立本窗口的 Pinia 会话，再安装权限守卫；路由只负责页面访问，写操作仍由服务端授权。
const pinia = createPinia()
const app = createApp(App).use(pinia)
const appStore = usePiniaAppStore(pinia)
installWorkspaceAccessGuard(
  workspaceRouter,
  () => appStore.user?.permissions ?? null
)
app.use(workspaceRouter).mount('#app')
