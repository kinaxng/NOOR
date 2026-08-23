# UI 一致性审计报告

**项目**: LADA WebUI Frontend
**审计日期**: 2026-03-25
**目标**: 按 Vision UI Dashboard 风格重构

---

## A. 不一致项清单（文件级别）

### 1. 重复组件（Duplicate Components）

| 旧组件 | 位置 | 替代组件 | 位置 | 问题 |
|--------|------|----------|------|------|
| `BaseButton.vue` | `src/components/` | `VuiButton.vue` | `src/components/vision/VuiButton/` | 两套按钮样式，命名混乱 |
| `BaseBadge.vue` | `src/components/` | `VuiBadge.vue` | `src/components/vision/VuiBadge/` | badge 语义重复 |
| `BaseProgress.vue` | `src/components/` | `VuiProgress.vue` | `src/components/vision/VuiProgress/` | 进度条重复 |
| `BaseIcon.vue` | `src/components/` | 内联 SVG icons | 各组件内 | 无依赖，轻量可保留 |

### 2. 状态颜色冲突（Status Color Conflicts）

| 状态 | `tokens.ts` 定义 | `style.css` 定义 | `VuiBadge.vue` 实际 | 问题 |
|------|-----------------|-----------------|---------------------|------|
| `warning` | `#F53939` (红) | `#FFB547` (橙) | `#F53939` (红) | 三处三种值 |
| `error` | `#F53C2B` | `#E31A1A` | `#F53C2B` | 两处不一致 |
| `info/primary` | `#0075FF` | `#0075FF` | `#0075FF` | ✓ 一致 |
| `success` | `#01B574` | `#01B574` | `#01B574` | ✓ 一致 |

**影响文件**: `tokens.ts`, `style.css`, `VuiBadge.vue`, `VuiProgress.vue`, `Jobs.vue`, `History.vue`, `Home.vue`

### 3. 卡片背景不一致（Card Background Inconsistency）

| 文件 | 背景样式 | 问题 |
|------|----------|------|
| `Dashboard.vue` | 使用 `MiniStatisticsCard`, `WelcomeMark`, `ActivityCard` 组件 | 统一 ✓ |
| `Jobs.vue` | `.job-card` 使用 `linear-gradient(...)` | 硬编码样式 |
| `History.vue` | `.table-card` 使用 `linear-gradient(...)` | 硬编码样式 |
| `Home.vue` | 直接内联 `style="background: linear-gradient..."` | 硬编码样式 |
| `SettingsIndex.vue` | `.settings-card` 使用 `linear-gradient(...)` | 硬编码样式 |
| `SystemSettings.vue` | `.settings-card` 使用 `linear-gradient(...)` | 硬编码样式 |
| `LadaSettings.vue` | `.settings-card` 使用 `linear-gradient(...)` | 硬编码样式 |
| `WhisperSettings.vue` | `.settings-card` 使用 `linear-gradient(...)` | 硬编码样式 |
| `StorageSettings.vue` | `.settings-card` 使用 `linear-gradient(...)` | 硬编码样式 |
| `VisionSidebar.vue` | 使用 `linear-gradient(...)` | 硬编码样式 |
| `ActivityCard.vue` | 使用 `linear-gradient(...)` | 硬编码样式 |
| `MiniStatisticsCard.vue` | 使用 `linear-gradient(...)` | 硬编码样式 |
| `WelcomeMark.vue` | 使用 `linear-gradient(...)` + 装饰 blob | 硬编码样式 |

### 4. 文本颜色 Token 缺失/错误

| Token | `tokens.ts` | `style.css` | 使用处 |
|-------|-------------|-------------|--------|
| `text-secondary` | 未定义 | `#6B7194` | 多个组件 |
| `text-body` | 未定义 | `#A0AEC0` | 多个组件 |
| `text-muted` | `#718096` | `#454A6A` | 不一致 |
| VuiTypography `dark` | — | — | 硬编码 `#344767` |

### 5. 硬编码视觉样式（Inline Style Violations）

以下文件在 `<template>` 或 `<style scoped>` 中直接使用硬编码颜色/值，违反设计 Token 约束：

- `Home.vue`: 92行 `style="color: rgba(255,255,255,0.3);"`, 152行 `text-[#0075FF]`, 156行 `text-[#FFB547]`, 186行 `style="background: linear-gradient..."`
- `Jobs.vue`: 348-354行硬编码 `rgba(0, 117, 255, 0.15)` 和 `#0075FF`
- `Dashboard.vue`: 212-234行 `.quick-action-card` 内联样式
- `MediaDetailPanel.vue`: 多处 `bg-bg-surface`, `text-accent-cyan` 等混用
- `SubtitlePanel.vue`: 多处 `bg-bg-elevated`, `border-border-subtle` 等混用
- `SystemSettings.vue`: 158行 `border-[#0075FF]` 等

### 6. 组件命名不一致

| 当前名称 | Vision UI 标准 | 问题 |
|----------|---------------|------|
| `VisionSidebar` | `DashboardSidenav` | 命名偏通用 |
| `MiniStatisticsCard` | `MiniStatisticsCard` | ✓ 符合 |
| `ActivityCard` | `ProjectsCard` (类似) | 命名需对齐 |
| `WelcomeMark` | `WelcomeMark` | ✓ 符合 |
| `SystemMetricsCard` | 无对应 | 可保留 |

### 7. 表单输入未组件化

所有 settings 页面使用原生 `<input>` 和 `<select>`，没有使用统一的 `VuiInput`/`VuiSelect` 组件。

### 8. 路由配置问题

`router/index.ts` 中：
- Dashboard 路由 path `/` 指向 `Dashboard.vue`
- Home 路由 path `/library` 指向 `Home.vue`
- 但组件名称 `dashboard` 和 `home` 与路径不匹配

### 9. App.vue 中的重复导航

`App.vue` 定义了 `navItems` 和导航逻辑，同时 `VisionSidebar.vue` 也定义了 `navItems`。两处维护同一份数据。

### 10. 任务状态语义不完整

`statusMap` 定义:
```ts
queued: { color: 'warning', label: '排队' }
running: { color: 'info', label: '运行中' }
completed: { color: 'success', label: '完成' }
failed: { color: 'error', label: '失败' }
```

但 `canceled` 状态缺失，且 `Jobs.vue` 中 `queued` 使用 `warning` 颜色，但 `warning` 在 VuiBadge 中是红色 `#F53939`，不是橙色。

---

## B. 文件清单

### 需要删除的旧组件
- `src/components/BaseButton.vue`
- `src/components/BaseBadge.vue`
- `src/components/BaseProgress.vue`

### 需要重构的页面
- `src/views/Dashboard.vue` - QuickAction 内联样式
- `src/views/Home.vue` - 多处硬编码
- `src/views/Jobs.vue` - 硬编码颜色
- `src/views/History.vue` - table-card 样式
- `src/views/settings/SettingsIndex.vue` - settings-card 样式
- `src/views/settings/SystemSettings.vue` - settings-card 样式
- `src/views/settings/LadaSettings.vue` - settings-card 样式
- `src/views/settings/WhisperSettings.vue` - settings-card 样式
- `src/views/settings/StorageSettings.vue` - settings-card 样式

### 需要重构的组件
- `src/components/MediaDetailPanel.vue` - 面板样式
- `src/components/SubtitlePanel.vue` - 面板样式
- `src/components/JobCard.vue` - 卡片样式
- `src/components/MediaCardBento.vue` - 保留（业务组件）
- `src/components/LogViewer.vue` - 样式保留
- `src/components/FilterBar.vue` - 样式保留
- `src/components/LibrarySidebar.vue` - 需检查
- `src/components/MediaGrid.vue` - 需检查
- `src/components/MediaCard.vue` - 需检查（可能被废弃）

### 需要重构的布局
- `src/layouts/VisionSidebar.vue` - 样式对齐
- `src/App.vue` - 合并导航逻辑，清理内联样式

### 需要清理的全局样式
- `src/style.css` - 统一 Token 定义
- `src/theme/tokens.ts` - 修正颜色冲突

---

## C. 风险评估

| 风险 | 级别 | 说明 | 缓解 |
|------|------|------|------|
| 组件替换破坏业务 | 中 | BaseButton/BaseBadge/BaseProgress 删除后有引用未更新的地方 | 先搜索引用再删除 |
| statusMap 颜色变更影响任务页面 | 高 | warning 颜色变更影响 Job status 显示 | 统一 status → color 映射 |
| 硬编码渐变背景删除 | 中 | 多个组件依赖 `linear-gradient(127.09deg...)` | 创建统一的 card token |
| VuiTypography dark 色值不匹配暗色主题 | 低 | 仅用于亮色主题，当前是暗色主题，可忽略 |
