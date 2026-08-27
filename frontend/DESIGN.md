NOOR Design System
===================

Product Type: Local-first AI Video Processing Platform + Media Library Dashboard
Style: Dark Navy Blue (deep space) — Vision UI Dashboard inspired (Creative Tim, MIT)
Stack: Vue 3 + TypeScript + Tailwind CSS + Pinia + Vite
Locale: Bilingual (zh-CN / en-US)

---

Visual Theme
-----------
深色科技感控制台，深海军蓝背景 + 纯蓝色强调。整体氛围冷静、沉浸、无干扰。
所有视觉属性通过 CSS 变量引用，不允许在组件中硬编码 hex 值（color 除外且需注明理由）。

Color Palette
-------------
Base backgrounds (css: --color-bg-*)
  #030C1D   rgb(3,12,29)     void         页面最底层背景 (html body)
  rgb(3,12,29)               base         App 容器背景
  #1A1F3A   rgb(26,31,55)   surface      卡片 / 面板背景
  #1E2544   rgb(30,37,68)   elevated     悬浮层 / 次级卡片
  #252A40                   hover        Hover 态

Borders (css: --color-border-*)
  rgba(255,255,255,0.04)     subtle       卡片默认边框
  rgba(255,255,255,0.08)     default      输入框 / 分割线
  rgba(255,255,255,0.14)     strong       聚焦边框
  #0075FF                    focus        聚焦环

Text (css: --color-text-*)
  #FFFFFF                     primary      标题 / 主文本
  #A0AEC0                     secondary    正文 / 次要文本
  #718096                     muted        辅助文本 / 占位符 / 禁用

Brand
  #0075FF                     brand        主品牌蓝（唯一品牌色）
  #3993FE                     brand-hover
  #005FCC                     brand-active

Status — 唯一正确映射（禁止混淆）
  running    #0075FF  info        rgba(0,117,255,0.15)   bg
  completed  #01B574  success     rgba(1,181,116,0.15)
  queued     #FFB547  warning     rgba(255,181,71,0.15)
  failed     #E31A1A  error       rgba(227,26,26,0.15)
  (none)     #627594  secondary   rgba(98,117,148,0.15)

Accent（仅用于视觉点缀，非主操作）
  #21D4FD    cyan
  #FF2D95    magenta
  #FFB800    amber

Typography
----------
Font families (css: --font-*)
  --font-display  'Plus Jakarta Display', 'Inter', 'Noto Sans SC', sans-serif
                  用于：标题、标签、按钮、卡片文本、导航
  --font-body     'Inter', -apple-system, BlinkMacSystemFont, sans-serif
                  用于：正文、输入框
  --font-mono     'JetBrains Mono', 'Fira Code', monospace
                  用于：日志、代码、数值

Type scale (css: --font-size-*)
  0.625rem (10px)  xxs   极小辅助文字
  0.75rem  (12px)  xs    标签/徽章
  0.875rem (14px)  sm    正文辅助
  1rem     (16px)  base  正文
  1.125rem (18px)  lg    标题辅助
  1.25rem  (20px)  xl    标题
  1.5rem   (24px)  2xl   大标题
  1.875rem (30px)  3xl   页面标题

Font weights (css: --font-weight-*)
  300  light
  400  regular     body text
  500  medium      secondary emphasis
  600  semibold    labels, nav, card titles
  700  bold        buttons, logo

Component Stylings
------------------
Cards (.vision-card)
  background: rgb(26,31,55)
  border-radius: var(--radius-lg)   (15px)
  border: 1px solid rgba(255,255,255,0.06)
  padding: 1.5rem
  hover: border-color rgba(0,117,255,0.3), translateY(-1px), shadow blue tinted

Buttons (VuiButton / .vui-button)
  border-radius: var(--radius-button)  (12px)
  font-family: var(--font-display)
  font-weight: 700
  text-transform: uppercase
  letter-spacing: 0.5px
  transition: all var(--transition-fast)  (150ms ease-out)
  Variants:
    contained  background: var(--color-brand)  color: #FFFFFF
    outlined   background: transparent  border: 1px solid rgba(255,255,255,0.75)  color: #FFFFFF
    gradient   background: var(--color-brand)  color: #FFFFFF  box-shadow with blue tint
    text       background: transparent  color: #FFFFFF  no shadow, no uppercase
  Focus: box-shadow var(--shadow-glow)
  Hover: translateY(-1px) + deeper shadow (contained/gradient only)

Badges (VuiBadge)
  border-radius: var(--radius-button)  (12px)  or pill (9999px) for circular
  font-family: var(--font-display)
  font-size: var(--font-size-xs)  (12px)
  font-weight: 600
  padding: 0.25rem 0.625rem

Inputs (.settings-input)
  background: rgba(255,255,255,0.04)
  border: 1px solid rgba(255,255,255,0.08)
  border-radius: var(--radius-md)  (8px)
  padding: 0.625rem 0.875rem
  font-family: var(--font-display)
  font-size: var(--font-size-sm)  (14px)
  color: #FFFFFF
  Focus: border-color var(--color-border-focus) + box-shadow 0 0 0 3px rgba(0,117,255,0.1)

Filter buttons (.filter-btn)
  border-radius: var(--radius-button)  (12px)
  font-size: 0.75rem  font-weight: 600  uppercase  letter-spacing: 0.05em
  font-family: var(--font-display)
  inactive:  background rgba(255,255,255,0.03)  border rgba(255,255,255,0.06)  color rgba(255,255,255,0.5)
  active:    background var(--color-brand)  color white  box-shadow 0 4px 12px rgba(0,117,255,0.3)

Pagination (.pagination-btn)
  border-radius: var(--radius-lg)  (15px)
  font-family: var(--font-display)  font-size: 0.875rem  font-weight: 500
  background rgba(255,255,255,0.03)  border rgba(255,255,255,0.08)  color rgba(255,255,255,0.7)
  disabled:  opacity 0.3  cursor not-allowed

Sidebar navigation
  item:  padding 0.625rem 0.875rem  border-radius var(--radius-md)
         inactive: color rgba(255,255,255,0.5)
         hover:    background rgba(255,255,255,0.04)  color rgba(255,255,255,0.8)
         active:   background rgba(0,117,255,0.15)  color #FFFFFF
                   left bar 3px #0075FF + translateY(-50%)
  collapse: 274px → 120px  transition var(--transition-slow)

Layout Principles
----------------
8pt grid system (Tailwind 默认 4px 基准)
主布局：Sidebar (274px fixed) + Header (64px sticky) + Content (p-4 md:p-6)
媒体库网格：auto-fill minmax(160px, 1fr)  →  响应式 2-6 列
Dashboard 网格：lg:grid-cols-4 和 lg:grid-cols-3

Breakpoints
  sm  640px   md  768px   lg  1024px   xl  1280px   2xl  1536px
Mobile: sidebar 作为 drawer 滑出，content 无 margin-left

Depth & Elevation
----------------
Shadow scale (css: --shadow-*)
  sm          0 2px 6px rgba(0,0,0,0.18)
  md          0 8px 24px rgba(0,0,0,0.28)   ← 卡片默认
  lg          0 16px 40px rgba(0,0,0,0.35)
  glow        0 0 0 3px rgba(0,117,255,0.28)  ← focus 态
  glow-blue   0 4px 15px rgba(0,117,255,0.35) ← 按钮 hover

Z-index scale (css: --z-*)
  sidebar   40
  navbar    50
  dropdown  50
  modal     100
  toast     200

Transitions (css: --transition-*)
  fast    150ms ease-out      ← 微交互（hover、focus）
  normal  200ms ease-in-out  ← 状态切换
  slow    300ms cubic-bezier(0.16, 1, 0.3, 1)  ← 页面过渡、面板滑入

Do's and Don'ts
---------------
✓ 所有颜色通过 CSS 变量引用（--color-*）
✓ 使用 .vision-card 定义卡片样式
✓ 使用 VuiButton / VuiBadge / VuiProgress 组件
✓ 状态颜色严格遵循 status 映射表
✓ hover/active/disabled 状态必须实现
✓ 动画只使用 transform + opacity（GPU 加速）
✓ 圆角统一使用 var(--radius-*) token

✗ 禁止硬编码 Tailwind 默认色（bg-red-600 / text-gray-400 等）—— 必须换算为设计系统 token
✗ 禁止混用两套色板（MASTER.md 的 OLED 风格未实现，禁止使用）
✗ 禁止在组件 scoped style 中直接写 hex 值（除了 #FFFFFF #000000）
✗ 禁止用 100vh 代替自动高度（移动端使用 100dvh）
✗ 禁止用 emoji 代替 SVG icon
✗ 禁止在活动状态用颜色单独传达信息（需配合 icon 或文字）
✗ 禁止 animate width/height —— 用 transform: scale()

Responsive Behavior
-------------------
< 640px     媒体库 2 列，sidebar 隐藏（drawer）
640-1024px  媒体库 4 列
> 1024px    媒体库 6 列，sidebar 固定

Agent Prompt Guide
------------------
给 AI 编程助手的特殊指令：

1. 颜色优先级：当设计系统和代码中的值不一致时，以 style.css 中实际定义的 CSS 变量为准。
   现状冲突：index.html 导入了 IBM Plex Sans + Rajdhani，但 --font-display 实际是 Plus Jakarta Display。
   修复方式：使用 Google Fonts CDN 导入 Plus Jakarta Display 和 Inter（不要导入 Rajdhani）。

2. 状态颜色映射（牢记）：
   running → info (blue)    #0075FF
   completed → success     #01B574
   queued → warning        #FFB547
   failed → error          #E31A1A
   常见错误：把 success 写成 #00E58B，把 error 写成 #FF474B —— 这些值不在 design system 中。

3. 媒体卡片标签色板（MediaCardBento 用）：
   有字幕/中文  →  status-error (red)  bg: rgba(227,26,26,0.15)
   破解         →  status-success  bg: rgba(1,181,116,0.15)
   流出         →  status-warning  bg: rgba(255,181,71,0.15)
   无码         →  accent-magenta   bg: rgba(255,45,149,0.15)
   无标签       →  text-muted       bg: rgba(255,255,255,0.08)

4. 组件库选择：
   使用 src/components/vision/ 下的 VuiButton、VuiBadge、VuiProgress、VuiBox、VuiTypography
   不要混用 BaseButton、BaseBadge（待废弃）
   .vision-card 是统一卡片类，配合 Tailwind 的 bg-surface 使用

5. VuiButton variant="contained" 的默认色是白色按钮（深色字），variant="gradient" 是蓝色按钮。
   NOOR 主要使用 gradient variant 表示主操作。

6. 新增组件时：将设计 token 值（颜色、半径、阴影）定义在 style.css 的 :root 中，
   在组件中通过 var() 引用，而不是复制具体值。

Global Loading, Empty and Feedback States
-----------------------------------------
这些约束适用于主程序页面、面板、弹窗、插件贡献页面。目标是避免“多个框叠在一起”、避免每个页面自造一套 loading / warning / toast。

1. 页面首次加载
   - 页面级 loading 使用居中轻量状态条：spinner + 一句短文案。
   - 不要用整块大卡片占位，除非页面本身就是表格/卡片骨架且能稳定避免布局跳动。
   - 插件宿主加载插件模块时，由 `PluginPageHost` 负责显示 loading；插件本身不要在 mount 前再画一个外层 loading 框。

2. 局部加载
   - 表格、网格、列表内容加载时，优先在内容区使用单个 inline state，不要同时显示空状态、错误状态和 loading 状态。
   - loading / empty / error 三者互斥：同一区域同一时刻只能出现一种状态。
   - 局部 loading 不要抢占页面主视觉，样式应比主要按钮和 tab 更弱。

3. 空状态
   - 空状态只说明“当前没有什么”和“用户可以做什么”。
   - 空状态不使用警告色，不使用大面积边框，不堆叠多段解释。
   - 例如：`暂无内容`、`暂无片单内容，点击 + 添加片单`。

4. 错误 / 警告
   - 可恢复错误优先 toast；页面内容区错误只保留一条简短 inline error。
   - 阻断型错误才使用面板级 error state。
   - 危险操作必须用 modal / preview，不用浏览器 `alert()` / `confirm()` 作为最终交互。

5. Toast
   - toast 用于动作结果反馈：保存成功、提交失败、推送完成。
   - toast 文案必须短，不承载长日志、长路径、长异常栈。
   - 重复快速触发的动作应避免刷屏，后续需要统一去重/合并策略。

6. Skeleton
   - Skeleton 只用于卡片网格或表格等尺寸稳定区域。
   - Skeleton 不展示边框堆叠，不与 spinner 同时出现。
   - 如果数据通常 1 秒内返回，优先使用单个 inline spinner，不使用 skeleton。

7. 插件页面反馈
   - 插件页面的外层加载、模块加载失败由 `PluginPageHost` 负责。
   - 插件内部只负责业务数据加载状态，例如 RSS 正在加载、片单为空。
   - 插件必须通过 `sdk.toast` 发成功/失败提示，不要直接使用 `alert()`。
   - 插件内部状态组件必须复用 NOOR token：`--color-bg-surface`、`--color-border-default`、`--color-text-secondary`、`--color-brand`。


Top action row / 顶部操作行
-------------------------
用于页面级 tabs 同一行右侧的状态与操作，例如：`额度受限`、`已连接`、`刷新`、`新建任务`。

统一结构：左侧为一级 tabs，右侧为 actions；移动端 actions 必须排在 tabs 上方，避免主操作被横向 tabs 挤到第二视觉层级。

尺寸：
- 状态 badge、普通按钮、主按钮统一高度 30px。
- 间距 8px，整行 gap 12px，可换行。

类型与颜色：
- `muted/default`：中性白灰，用于普通状态、次操作按钮。
- `info`：品牌蓝，用于进行中、可点击的当前能力。
- `success`：绿色，用于已连接、已启用、成功。
- `warning`：琥珀，用于额度受限、未配置、需要注意但不阻断。
- `error`：红色，用于已过期、连接失败、阻断错误。
- `primary button`：品牌蓝，只用于当前最重要动作，例如“刷新”“新建任务”。

插件应优先使用 SDK / 全局类：`.noor-plugin-topbar`、`.noor-plugin-topbar__actions`、`.noor-plugin-badge--{tone}`、`.noor-plugin-btn--primary`，不要在每个插件里重新发明高度和色板。

NOOR Kit / Nuxt UI Migration Contract
-------------------------------------
NOOR 前端从 2026-05-01 起进入 Nuxt UI + NOOR Kit 迁移期。Nuxt UI 提供底层可访问组件，NOOR Kit 提供产品语义封装；业务页面不应直接堆叠页面私有按钮、badge、tabs 样式。

统一入口：
- Vue 主程序：`frontend/src/components/noor-kit/*`
- 插件页面：`sdk.ui.*` DOM Lite 组件
- 全局 token：`frontend/src/style.css` 中的 `--color-*` 与 `--ui-*` bridge

第一批语义组件：
- `NoorButton` / `sdk.ui.button()`：`primary`、`secondary/default`、`danger/error`、`ghost`、`link`
- `NoorBadge` / `sdk.ui.badge()`：`muted`、`info`、`success`、`warning`、`danger/error`
- `NoorTabs` / `sdk.ui.tabs()`：页面一级 tab，必须有滑动指示或等价 active 反馈
- `NoorDialog` / `sdk.ui.modal()` / `sdk.ui.confirm()`：替代浏览器原生弹窗
- `NoorTopActionBar` / `sdk.ui.topBar()` / `.noor-plugin-topbar`：顶部操作区唯一结构
- `NoorInput`、`NoorSelect`、`NoorSearchBox` / `sdk.ui.input/select/search()`：输入与搜索统一入口
- `NoorPagination` / `sdk.ui.pagination()`：分页统一入口，支持键盘 Home/End/PageUp/PageDown
- `NoorState` / `sdk.ui.emptyState/loadingState/errorState()`：加载、空、错误态互斥
- `NoorSubmitButton` / `sdk.ui.submitButton()`：按钮内进度，完成后保留状态直到刷新

旧组件边界：
- `VuiButton`、`VuiBadge`、`Tabs`、`VuiPagination`、`BaseModal`、`VuiSubmitButton` 暂保留兼容旧页面。
- 新页面和新插件功能不得继续扩展这些旧组件。
- 旧页面迁移时优先替换顶部操作区、分页、弹窗，再替换局部卡片内按钮。

禁止：
- 在单个页面或插件里重新定义按钮高度、badge 颜色、tab 动画。
- 插件直接复制主程序 CSS 片段后改名。
- 同一行中混用白色线框按钮、蓝色按钮、插件私有渐变按钮。
