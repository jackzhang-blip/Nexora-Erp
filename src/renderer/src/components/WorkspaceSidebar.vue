<script setup lang="ts">
import { useAppStore } from '../store/app-store'
import { nexoraLogo } from '../assets/brand'
import IconArrowDownSLine from '~icons/ri/arrow-down-s-line'

// 侧栏只负责导航展示，权限过滤和当前路由来自共享 store。
const {
  screen,
  activeTab,
  expandedGroupKey,
  version,
  server,
  user,
  visibleGroups,
  toggleRouteGroup,
  navigateToRoute
} = useAppStore()
</script>

<template>
  <aside class="sidebar">
    <div class="brand">
      <span class="brand-mark"><img :src="nexoraLogo" alt="" /></span>
      <div>
        <strong>NEXORA</strong
        ><small
          >联光 ERP · {{ server?.isLocal ? '本机服务' : '团队工作台' }}</small
        >
      </div>
    </div>
    <div v-if="screen === 'app'" class="side-group">
      <div v-for="group in visibleGroups" :key="group.key" class="nav-group">
        <button
          class="side-category"
          :class="{
            current: group.routes.some((item) => item.key === activeTab)
          }"
          type="button"
          :aria-expanded="expandedGroupKey === group.key"
          :aria-controls="`route-group-${group.key}`"
          @click="toggleRouteGroup(group.key)"
        >
          {{ group.label
          }}<IconArrowDownSLine
            class="category-chevron"
            :class="{ expanded: expandedGroupKey === group.key }"
            aria-hidden="true"
          />
        </button>
        <div
          :id="`route-group-${group.key}`"
          class="nav-panel"
          :class="{ expanded: expandedGroupKey === group.key }"
          :aria-hidden="expandedGroupKey !== group.key"
          :inert="expandedGroupKey !== group.key ? true : undefined"
        >
          <div class="nav-list">
            <button
              v-for="item in group.routes"
              :key="item.key"
              class="nav-item"
              :class="{ active: activeTab === item.key }"
              type="button"
              :aria-current="activeTab === item.key ? 'page' : undefined"
              @click="navigateToRoute(item.key)"
            >
              <component
                :is="item.icon"
                class="nav-icon"
                aria-hidden="true"
              />{{ item.label }}
            </button>
          </div>
        </div>
      </div>
    </div>
    <!-- 左下角保留服务端身份；登录阶段不显示表示连接状态的绿点。 -->
    <div class="sidebar-bottom" :class="{ 'auth-server-details': screen !== 'app' }">
      <!-- 账号信息只属于当前登录会话，退出后立即从侧栏消失。 -->
      <div v-if="screen === 'app' && user" class="sidebar-account">
        <span class="sidebar-account-label">当前账号</span>
        <strong class="sidebar-account-name">{{ user.username }}</strong>
        <span class="sidebar-account-roles">{{ user.roles.join(' · ') }}</span>
      </div>
      <span v-if="screen === 'app'" class="status-dot"></span>{{ server?.name || 'Nexora ERP' }}
      <small v-if="version">v{{ version }}</small>
    </div>
  </aside>
</template>
