---
name: Nexora ERP 官网
description: 浅色 WebGL 应用窗与可读文档；仅适用于 docs/site
colors:
  paper: "#fafbfc"
  stage: "#f6f8fa"
  ink: "#182b35"
  muted: "#596873"
  teal: "#176f67"
  action: "#087f75"
  action-hover: "#06695f"
  selected: "#078579"
  linked: "#12bfa7"
  linked-row: "#e0f8f0"
  panel: "#fff"
  rule: "#d9e0e4"
  field-rule: "#ccdbe5"
  field-focus: "#2ca998"
  status-bg: "#c9f6eb"
  status-ink: "#076f61"
  draft-bg: "#fcf1d5"
  draft-ink: "#7d5712"
  error: "#a2292f"
typography:
  display: {fontFamily: 'Inter, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif', fontSize: "clamp(48px, 6vw, 80px)", fontWeight: 750, lineHeight: 1.13, letterSpacing: "-.035em"}
  headline: {fontSize: "clamp(30px, 3.2vw, 45px)", fontWeight: 700, lineHeight: 1.3, letterSpacing: "-.025em"}
  window-title: {fontSize: "27px", lineHeight: 1.2, letterSpacing: "-.025em"}
  body: {fontSize: "16px", lineHeight: 1.9}
  sandbox: {fontSize: "12px"}
  table: {fontSize: "11px", lineHeight: 1.5}
  amount: {fontSize: "36px", lineHeight: 1.25, letterSpacing: "-.03em"}
  code: {fontFamily: 'Consolas, "SFMono-Regular", monospace', fontSize: "13px", lineHeight: 1.8}
rounded:
  field: "5px"
  sidebar-action: "6px"
  sheet: "8px"
  primary: "9px"
  window: "14px"
  step: "22px"
  step-track: "26px"
spacing:
  control-gap: "8px"
  field-gap: "16px"
  sheet-inset: "18px"
  scene-horizontal: "32px"
components:
  button-primary: {backgroundColor: "{colors.action}", textColor: "{colors.panel}", rounded: "{rounded.primary}", padding: "13px 24px"}
  sandbox-primary: {backgroundColor: "{colors.action}", textColor: "{colors.panel}", rounded: "{rounded.field}", padding: "8px 11px"}
  sandbox-primary-hover: {backgroundColor: "{colors.action-hover}"}
  sandbox-secondary: {backgroundColor: "{colors.panel}", textColor: "#365d6a", rounded: "{rounded.field}", padding: "8px 11px"}
  field: {backgroundColor: "{colors.panel}", textColor: "#203440", rounded: "{rounded.field}", padding: "8px"}
  status-chip: {backgroundColor: "{colors.status-bg}", textColor: "{colors.status-ink}", rounded: "{rounded.field}", padding: "5px 10px"}
  status-chip-draft: {backgroundColor: "{colors.draft-bg}", textColor: "{colors.draft-ink}"}
  stage-button: {textColor: "#47616d", rounded: "{rounded.step}", padding: "8px 16px"}
  stage-button-selected: {backgroundColor: "{colors.selected}", textColor: "{colors.panel}"}
  demo-window: {rounded: "{rounded.window}", padding: "3px"}
  receipt-sheet: {backgroundColor: "{colors.panel}", rounded: "{rounded.sheet}", padding: "18px"}
---

# Design System: Nexora ERP 官网

<!-- 归档当前实现；样式范围仅 docs/site，不覆盖 ERP 桌面应用。 -->

## Overview

**Creative North Star: "清晰的业务舞台"**

浅色舞台、银灰独立应用窗、现代无衬线文字与青绿来源关系共同解释业务。本规范覆盖当前 WebGL 视觉层与 HTML 业务沙盒，取代此前卡片、深色概念图和衬线方案。保留 Nexora/联光 ERP 名称与品牌资源；网站示例不连接 ERP 服务，也不代表桌面应用已支持双语。

**Key Characteristics:**

- 浅色独立应用窗，GPU 银框、柔和阴影与渐隐反射。
- 入库大窗、库存右进、财务右进、三屏关联。
- HTML 管理业务、表单、焦点；GPU 仅负责视觉。
- 文档平实可读，静态回退保留业务操作。

## Colors

前置 token 提取自 site.css 与 sandbox.css，记录实际局部覆盖，不强行合并青绿色值。

### Primary

teal 用于官网链接与全局焦点，action 用于主行动，selected 用于步骤选择。linked 与 linked-row 表达来源锚点及库存关联；已入库与草稿分别使用浅绿、浅金底并附文字，错误同时显示红色与字段说明。GPU 金属与曲线色值由着色器生成，属于材质实现而非前置颜色 token。

### Neutral

paper 是文档纸面，stage 是首页舞台，panel 是业务面板；ink、muted 区分正文与说明，rule、field-rule 分别承担内容分隔和字段边界。

**The Business Accent Rule.** 品牌色强调操作与来源关系，不替代字段文字。

## Typography

Inter、Segoe UI、PingFang SC、Microsoft YaHei、sans-serif 是既定现代无衬线体系。Inter 本地可变字体支持 100–900 字重及 font-display: swap；中文沿用回退字体。来源为 [Inter 官方仓库](https://github.com/rsms/inter)，采用 SIL Open Font License 1.1，许可随 fonts/LICENSE.txt 分发。

首页标题在 760px 以下使用 clamp(38px,10vw,62px)；说明桌面 18px、手机 14px。文档正文最大 75ch，720px 以下为 15px。窗口标题在 650px、400px 容器下分别为 22px、20px，手机覆盖为 21px。业务数字采用等宽数字；代码采用 Consolas、SFMono-Regular、monospace。

**The Readable Documentation Rule.** 产品展示的密度与标题尺度不扩散到长文正文。

## Layout

页眉最大 1360px，桌面舞台最大 1440px。场景 340vh，粘性区域 100svh、最小 620px；窗口区 calc(100svh - 200px)，限制在 420–650px。入库初始居中占 85%；双屏约 38% / 59%，三屏为 27% / 44% / 27%。

文档最大 1210px，230px 目录、最大 840px 正文、70px 列距。1100px 以下为 190px 目录、35px 列距；720px 以下单列。业务舞台在 760px 以下取消固定行程，窗口纵向排列，最大 600px、间距 54px；表格在窗内横向滚动。650px 容器下侧栏为 43px 图标栏；400px 以下进一步收拢字段。打印恢复顺序内容流并隐藏视觉画布。

## Elevation & Depth

桌面原生 WebGL 使用两块透明画布：下层绘制 GPU 透视银框、接触阴影与渐隐反射，上层以三角带绘制柔边来源曲线和光点。HTML 与 GPU 共享 1800px 透视与布局，画布 pointer-events:none 且 aria-hidden，不截获输入。父舞台最终 transform-style:flat，保留子窗 rotateY，解决倾斜按钮命中偏移。

聚焦时上层连线退到窗后（z-index 1、opacity .45），目标窗为 z-index 3，避免穿过表单。WebGL 可用时 HTML 窗仍有轻阴影：0 2px 2px #3d566429,0 20px 40px #29434f16。回退银边由 CSS 渐变构成，阴影为 0 2px 2px #3d566451,0 18px 30px #29434f20,0 32px 70px #28454b16。

**The Purposeful Depth Rule.** 空间感解释窗口关系，编辑时保证可点击与可读，文档保持平面阅读。

## Shapes

窗口圆角 14px、标题栏上角 11px、内容下角 10px；单据面板 8px，字段、业务按钮和状态 5px，侧栏选择 6px。首页行动 9px，步骤按钮 22px、轨道 26px。边框通常为 1px；GPU 圆角材质独立实现。

## Components

沙盒按钮与字段最小高 34px。实心主行动、白色次行动、只读浅底与禁用 opacity .5 区分操作状态。字段焦点为 2px、外扩 1px；全局键盘焦点为 3px 青绿、外扩 5px。错误关联 aria-invalid、说明文本和状态播报；主动来源导航结束后聚焦目标标题，输入获得焦点冻结镜头，退后或未出现的桌面窗 inert 且 aria-hidden。

本地沙盒支持新建/复制草稿、多物料入库、库存筛选、来源追溯、部分付款与付款历史。确认派生库存和应付，已确认单据只读，草稿不改余额。默认 DEMO-001 为数量 12、单价 ¥10.00、库存 +12、应付 ¥120.00；失败不替换旧状态。刷新/重置恢复默认，同标签页语言链接用一次性 sessionStorage 交接校验状态。

原生 scroll 与按需 requestAnimationFrame 驱动：20–38% 库存右进，52–70% 财务右进；34–43% / 66–76% 绘出两条线，85–95% 光点回看来源，95–100% 自然离开舞台。阶段文字边界 32%、63%、85%；分步选择锁定手动模式。聚焦约 450ms 放大至 85%，恢复滚动约 300ms 对齐位置；滚动只改镜头，不写业务。

曲线读取实际来源锚点，库存连接行边缘；不可见、草稿或不同来源不绘对应线。手机使用外缘 SVG 纵向连线，窗口以 18px / 400ms 轻微显现；减少动态效果取消位移、透视与显现，保留静态来源线和操作。手机与减少动态偏好不初始化 WebGL；无脚本显示静态示例。

WebGL 首次桌面动态绘制才初始化，DPR 最高 2 并受 GPU 缓冲尺寸限制；初始化、编译失败或上下文丢失时回退 HTML/CSS/SVG，不重置业务数据。恢复时重建 GPU 资源并请求当前帧；卸载释放资源。静止、离屏和后台不维持连续循环。文档表格与代码块采用浅色层次和独立滚动。

## Do's and Don'ts

### Do:

- **Do** 将规范限制在 docs/site，保留浅色独立窗与既定无衬线字体。
- **Do** 保留真实锚点、字段验证、键盘路径、手动模式与 GPU 失效回退。
- **Do** 区分本地演示、桌面能力和计划，随字体保留 OFL 许可。

### Don't:

- **Don't** 恢复旧卡片、深色概念图或衬线默认方案。
- **Don't** 用画布承载业务表单、截获输入或在恢复 GPU 时重置业务数据。
- **Don't** 在编辑时移动镜头、以连线遮挡字段或以滚动触发业务操作。
- **Don't** 将本规范覆盖到 ERP 应用，或把预览色阶视为生产 token。
