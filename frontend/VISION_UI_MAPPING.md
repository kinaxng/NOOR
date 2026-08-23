# Vision UI → LADA WebUI 映射表

**参考**: Vision UI Dashboard React (https://github.com/creativetimofficial/vision-ui-dashboard-react)
**目标**: LADA WebUI 单用户管理员控制台

---

## 1. 页面路由映射

| Vision UI 页面 | LADA WebUI 页面 | 说明 |
|----------------|-----------------|------|
| Dashboard | `/` (Dashboard.vue) | 概览页 |
| Tables | `/library` (Home.vue) | 媒体库 |
| Billing | — | 无对应（不是电商） |
| Profile | — | 无对应（单用户） |
| RTL | — | 无对应 |
| Authentication | — | 无对应（无登录） |
| — | `/jobs` (Jobs.vue) | 任务监控 |
| — | `/history` (History.vue) | 历史记录 |
| — | `/settings` (SettingsIndex.vue) | 设置页 |

---

## 2. 组件映射

### 2.1 布局组件

| Vision UI | LADA WebUI | 映射说明 |
|-----------|------------|---------|
| `DashboardLayout` | `VisionSidebar` + `App.vue` | 主布局容器 |
| `PageLayout` | 未使用 | 单页应用不需要 |
| `DashboardNavbar` | `App.vue` header | 顶部导航栏 |
| `DefaultNavbar` | 未使用 | — |
| `Sidenav` | `VisionSidebar.vue` | 侧边导航 |

### 2.2 按钮组件

| Vision UI | LADA WebUI | 说明 |
|-----------|------------|------|
| `VuiButton` | `src/components/vision/VuiButton/VuiButton.vue` | 已实现 ✓ |
| — | `BaseButton.vue` | **废弃**，使用 VuiButton |
| `BaseButtonRoot` | 合并到 VuiButton | — |

### 2.3 徽章组件

| Vision UI | LADA WebUI | 说明 |
|-----------|------------|------|
| `VuiBadge` | `src/components/vision/VuiBadge/VuiBadge.vue` | 已实现 ✓ |
| — | `BaseBadge.vue` | **废弃**，使用 VuiBadge |

### 2.4 进度条组件

| Vision UI | LADA WebUI | 说明 |
|-----------|------------|------|
| `VuiProgress` | `src/components/vision/VuiProgress/VuiProgress.vue` | 已实现 ✓ |
| — | `BaseProgress.vue` | **废弃**，使用 VuiProgress |

### 2.5 卡片组件

| Vision UI | LADA WebUI | 说明 |
|-----------|------------|------|
| `VuiBox` | `src/components/vision/VuiBox/VuiBox.vue` | 已实现 ✓ |
| `MiniStatisticsCard` | `src/components/vision/MiniStatisticsCard.vue` | 已实现 ✓ |
| `ProjectsCard` | `src/components/vision/ActivityCard.vue` | 重命名映射 |
| `WelcomeMark` | `src/components/vision/WelcomeMark.vue` | 已实现 ✓ |
| `SystemMetricsCard` | `src/components/vision/SystemMetricsCard.vue` | 已实现 ✓ |
| `MasterCard` | 未使用 | — |
| `InfoCards` | 未使用 | — |

### 2.6 排版组件

| Vision UI | LADA WebUI | 说明 |
|-----------|------------|------|
| `VuiTypography` | `src/components/vision/VuiTypography/VuiTypography.vue` | 已实现 ✓ |

### 2.7 输入组件

| Vision UI | LADA WebUI | 说明 |
|-----------|------------|------|
| `VuiInput` | 未实现 | settings 表单使用原生 input + .settings-input 类 |
| `VuiSwitch` | 未实现 | — |
| `VuiSelect` | 未实现 | settings 表单使用原生 select + .settings-input 类 |

### 2.8 其他组件

| Vision UI | LADA WebUI | 说明 |
|-----------|------------|------|
| `VuiAvatar` | 未使用 | — |
| `VuiAlert` | 未使用 | Toast 替代 |
| `VuiPagination` | 未使用 | — |
| `Calendar` | 未使用 | — |
| `GradientBorder` | 未使用 | — |
| `Breadcrumbs` | 未使用 | — |

---

## 3. 主题配置映射

### 3.1 颜色

| Vision UI Token | LADA WebUI Token | 值 |
|-----------------|------------------|-----|
| `colors.primary` | `--color-brand` | #0075FF |
| `colors.secondary` | `--color-secondary` | #627594 |
| `colors.info` | `--color-info` | #0075FF |
| `colors.success` | `--color-success` | #01B574 |
| `colors.warning` | `--color-warning` | #FFB547 |
| `colors.error` | `--color-error` | #E31A1A |
| `darkMode.colors.background` | `--color-bg-void` | #030C1D |
| `darkMode.colors.card` | `--color-bg-surface` | #1A1F3A |
| `darkMode.colors.white` | `--color-text-primary` | #FFFFFF |

### 3.2 圆角

| Vision UI | LADA WebUI | 值 |
|-----------|------------|-----|
| `borderRadius.xs` | `--radius-xs` | 2px |
| `borderRadius.sm` | `--radius-sm` | 4px |
| `borderRadius.md` | `--radius-md` | 8px |
| `borderRadius.button` | `--radius-button` | 12px |
| `borderRadius.lg` | `--radius-lg` | 15px |
| `borderRadius.xl` | `--radius-xl` | 20px |
| `borderRadius.section` | `--radius-pill` | 9999px |

### 3.3 阴影

| Vision UI | LADA WebUI | 值 |
|-----------|------------|-----|
| `boxShadows.xs` | `--shadow-xs` | 0 2px 9px -5px rgba(0,0,0,0.15) |
| `boxShadows.sm` | `--shadow-sm` | 0 5px 10px 0 rgba(0,0,0,0.12) |
| `boxShadows.md` | `--shadow-md` | 0 4px 6px -1px rgba(0,0,0,0.12) |
| `boxShadows.lg` | `--shadow-lg` | 0 8px 26px -4px rgba(0,0,0,0.15) |
| `boxShadows.xl` | `--shadow-xl` | 0 23px 45px -11px rgba(0,0,0,0.25) |
| `boxShadows.primary` | `--shadow-glow-blue` | 0 4px 15px rgba(0,117,255,0.35) |

---

## 4. 任务状态映射（关键）

| API Status | Vision UI Color | Badge 颜色 | 说明 |
|------------|-----------------|------------|------|
| `queued` | warning | `warning` | 橙色 #FFB547 |
| `running` | info | `info` | 蓝色 #0075FF |
| `completed` | success | `success` | 绿色 #01B574 |
| `failed` | error | `error` | 红色 #E31A1A |
| `canceled` | — | `secondary` | 灰色 #627594 |

**Warning 颜色澄清**: Vision UI 原版 warning 是橙色 (#FFB547)，不是红色。红色用于 error 状态。

---

## 5. 页面结构映射

### 5.1 Dashboard 页面

Vision UI Dashboard:
```
┌──────────────────────────────────────┐
│ Header (Welcome + Notifications)       │
├──────────────────────────────────────┤
│ Mini Statistics (4 cards grid)        │
├──────────────────────────────────────┤
│ Project Table (2/3) │ Activity (1/3) │
├──────────────────────────────────────┤
│ Footer / Configurator                 │
└──────────────────────────────────────┘
```

LADA WebUI Dashboard:
```
┌──────────────────────────────────────┐
│ Header (Welcome + Stats)              │
├──────────────────────────────────────┤
│ WelcomeMark (2/4) │ MiniStats (2/4)  │
├──────────────────────────────────────┤
│ SystemMetrics (2/3) │ Activity (1/3) │
├──────────────────────────────────────┤
│ Quick Actions (4 cards)               │
└──────────────────────────────────────┘
```

### 5.2 Tables 页面 → 媒体库

Vision UI Tables:
- 数据表格，筛选，搜索，分页

LADA WebUI 媒体库:
- 筛选标签，网格视图（MediaCardBento），分页
- 详情面板（MediaDetailPanel）

### 5.3 Settings 页面

Vision UI 无对应页面。LADA WebUI Settings:
- Tab 导航：System / Storage / LADA / Whisper
- 表单布局统一为 `.settings-card` 容器

---

## 6. 样式类映射

| Vision UI 类 | LADA WebUI 等价 | 说明 |
|-------------|----------------|------|
| `bg-gradient` | `.vision-card` | 卡片背景 |
| `text-gradient` | `VuiTypography textGradient` | 渐变文字 |
| `shadow-lg` | `shadow-lg` | Tailwind |
| `px-6 py-4` | `p-6` | Tailwind |
| `rounded-xl` | `rounded-xl` | Tailwind |

---

## 7. 实现差距

### 已完成 ✓
- VuiButton（contained/outlined/gradient/text variants）
- VuiBadge（gradient/contained/standard variants + 所有颜色）
- VuiProgress（gradient/contained variants + 所有颜色）
- VuiBox
- VuiTypography
- MiniStatisticsCard
- ActivityCard
- WelcomeMark
- SystemMetricsCard
- VisionSidebar
- CSS 变量体系
- Tailwind token 映射

### 未完成/待重构
- [ ] 删除 BaseButton/BaseBadge/BaseProgress
- [ ] 统一 settings 表单使用 Vision UI input 样式
- [ ] 清理所有硬编码 `linear-gradient(127.09deg...)` 背景
- [ ] 统一所有卡片使用 `.vision-card` 类
- [ ] 统一所有内联颜色使用 CSS 变量
- [ ] 确认 warning 颜色（橙色 #FFB547）在所有组件中一致
- [ ] statusMap 补充 `canceled` 状态
- [ ] VuiInput/VuiSelect 表单组件（可选，当前使用原生 + 类）
