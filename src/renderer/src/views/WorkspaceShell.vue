<script setup lang="ts">
import { computed } from 'vue'
import { useAppStore } from '../store/app-store'
// 工作台专属导航与跨页面公共组件分目录，避免应用外壳继续依赖平铺组件路径。
import WorkspaceSidebar from '../components/workspace/WorkspaceSidebar.vue'
import ThemeToggle from '../components/app/ThemeToggle.vue'
import WorkspaceTabs from '../components/workspace/WorkspaceTabs.vue'
import AppStatusFooter from '../components/app/AppStatusFooter.vue'
import AuthView from './AuthView.vue'
import { nexoraLogo } from '../assets/brand'
import { accountRoleText } from '../utils/account-role'

const {
  screen,
  activeTab,
  expandedGroupKey,
  busy,
  user,
  username,
  password,
  roles,
  visibleGroups,
  visibleTabs,
  openedTabs,
  activeRouteAllowed,
  toggleRouteGroup,
  navigateToRoute,
  closeOpenedRoute,
  switchServer,
  authenticate,
  logout
} = useAppStore()

// 登录、初始化和工作台共用内容区域与底栏。
const isAuthScreen = computed(() => screen.value === 'setup' || screen.value === 'login')
// 窄窗口与侧栏账号卡片共用角色名称规则，避免同一用户显示两种称呼。
const accountRole = computed(() => accountRoleText(user.value?.roles ?? [], roles.value))
</script>

<template>
  <div class="app-shell" :class="{ 'has-sidebar': screen === 'app' }">
    <!-- 只在进入工作台后挂载侧栏，进出时与内容列共用同一段过渡。 -->
    <Transition name="sidebar-slide">
      <WorkspaceSidebar v-if="screen === 'app'" />
    </Transition>

    <main class="content">
      <div class="content-body" :class="{ 'auth-screen': isAuthScreen }">
        <WorkspaceTabs v-if="screen === 'app'" />

        <header class="topbar">
          <!-- 登录标题沿用侧栏的品牌图形，保持未登录和工作台的视觉识别一致。 -->
          <span v-if="isAuthScreen" class="auth-header-mark" aria-hidden="true">
            <img :src="nexoraLogo" alt="" />
          </span>
          <div>
            <p class="eyebrow">NEXORA WORKSPACE</p>
            <h1>
              {{
                screen === 'app'
                  ? visibleTabs.find((item) => item.key === activeTab)?.label
                  : '开始使用联光 ERP'
              }}
            </h1>
          </div>
          <div v-if="user" class="account">
            <!-- 侧栏在窄窗口收起时，顶部保留账号和退出操作。 -->
            <span class="account-identity"
              >{{ user.username
              }}<small>{{ accountRole }}</small></span
            ><ThemeToggle /><button class="text-button" type="button" @click="logout">
              退出登录
            </button>
          </div>
        </header>

        <AuthView v-if="isAuthScreen" />
        <template v-else-if="screen === 'app' && activeRouteAllowed">
          <!-- 工作台页面由 Vue Router 装载；权限守卫和服务端鉴权共同约束访问。 -->
          <RouterView />
        </template>
      </div>
      <AppStatusFooter />
    </main>
  </div>
</template>
