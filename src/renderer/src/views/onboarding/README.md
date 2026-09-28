# 启动引导页面

`OnboardingView.vue` 负责页眉、提示和当前阶段切换。下列组件各自负责一个可见页面，连接数据和操作由 `store/` 管理。

| 页面组件 | 页面用途 |
| --- | --- |
| `LoadingView.vue` | 检查上次连接时显示等待状态 |
| `WelcomeView.vue` | 选择手动连接、局域网扫描或创建本机服务端 |
| `ManualConnectionView.vue` | 填写服务端地址并选择最近连接 |
| `DiscoveryScanView.vue` | 显示局域网扫描进度 |
| `DiscoveryResultsView.vue` | 选择扫描到的服务端 |
| `LocalHostSetupView.vue` | 配置或启动本机服务端 |
| `ServerTrustView.vue` | 核对服务端证书指纹 |
| `ConnectionReadyView.vue` | 展示已连接服务端并进入登录 |
| `ConnectionOfflineView.vue` | 提供重试连接、重启本机服务和切换服务端入口 |

阶段标题和说明统一维护在 `i18n/zh-CN.ts`。目前只有中文文案。
