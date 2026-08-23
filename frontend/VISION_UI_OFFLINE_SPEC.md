# VISION_UI_OFFLINE_SPEC.md
> 用于在无法访问本地参考仓库时，强制统一为 Vision UI Dashboard 风格的离线规范。
> 目标：管理员单用户控制台（概览、媒体库、任务、历史、设置）。
> 颜色：纯色体系，无渐变（蓝色系 #0075FF）

## 1. Design Principles
- 深色科技感：以深色多层背景承载数据界面。
- 玻璃拟态：卡片有轻微透明感、描边、柔和阴影。
- 高信息密度但层级清晰：标题、指标、数据区、操作区边界明确。
- 单一视觉语言：所有页面只允许一套 token 和组件变体。
- 业务优先：只改表现层，不改 API 契约和核心流程。

## 2. Core Tokens
```ts
// src/theme/tokens.ts
export const tokens = {
  color: {
    // brand / semantic — 纯色，无渐变
    primary: "#0075FF",
    primaryHover: "#3993FE",
    primaryActive: "#005FCC",

    info: "#0075FF",
    success: "#01B574",
    warning: "#F53939",
    error: "#F53C2B",

    // dark surfaces
    bg: {
      app: "rgb(3, 12, 29)",       // page background (Vision UI body-bg)
      canvas: "#0B1437",           // large containers
      elevated: "#1A1F3A",        // cards / panels
      overlay: "rgba(17, 25, 54, 0.65)", // glass layer
    },

    // text
    text: {
      primary: "#FFFFFF",
      secondary: "#A3AED0",
      muted: "#718096",
      inverse: "#1B254B",
    },

    // borders
    border: {
      default: "rgba(255,255,255,0.06)",
      strong: "rgba(255,255,255,0.12)",
      focus: "#0075FF",
    },

    // status backgrounds (语义色 + 低透明度背景)
    statusBg: {
      info: "rgba(0,117,255,0.12)",
      success: "rgba(1,181,116,0.12)",
      warning: "rgba(245,57,57,0.12)",
      error: "rgba(245,60,43,0.12)",
    },
  },

  typography: {
    fontFamily: "'Plus Jakarta Display', 'Inter', 'Noto Sans SC', sans-serif",
    monoFamily: "'JetBrains Mono', 'Fira Code', monospace",
    size: {
      xs: "0.625rem",    // 10px
      sm: "0.75rem",     // 12px
      md: "0.875rem",    // 14px
      lg: "1rem",        // 16px
      xl: "1.25rem",     // 20px
      "2xl": "1.5rem",   // 24px
      "3xl": "1.875rem", // 30px
    },
    weight: {
      regular: 400,
      medium: 500,
      semibold: 600,
      bold: 700,
    },
    lineHeight: {
      tight: 1.2,
      base: 1.5,
      loose: 1.7,
    },
  },

  radius: {
    xs: "0.5rem",     // 8px
    sm: "0.75rem",    // 12px
    md: "1rem",       // 16px
    lg: "1.25rem",    // 20px
    xl: "1.5rem",     // 24px
    pill: "9999px",   // 胶囊形
  },

  spacing: {
    1: "4px",
    2: "8px",
    3: "12px",
    4: "16px",
    5: "20px",
    6: "24px",
    8: "32px",
    10: "40px",
    12: "48px",
  },

  shadow: {
    sm: "0 2px 6px rgba(0,0,0,0.18)",
    md: "0 8px 24px rgba(0,0,0,0.28)",
    lg: "0 16px 40px rgba(0,0,0,0.35)",
    glow: "0 0 0 3px rgba(0,117,255,0.28)",
    glowBlue: "0 4px 15px rgba(0,117,255,0.35)",
  },

  blur: {
    glass: "14px",
    navbar: "20px",
  },

  zIndex: {
    dropdown: 1000,
    sticky: 1100,
    overlay: 1200,
    modal: 1300,
    toast: 1400,
  },

  motion: {
    fast: "150ms ease-out",
    normal: "200ms ease-in-out",
    slow: "300ms ease",
  },
} as const;
```

## 3. Layout Spec
App Shell：
- 左侧固定 Sidebar（宽 260px），Logo + 导航 + 用户信息
- 顶部 Navbar（高 64px），固定，模糊玻璃效果
- 主内容区 max-width 1440px，左右内边距 24px（移动端 16px）

页面结构统一：
1. Page Header（可选标题 + 简述 + 主操作）
2. KPI / 快速状态区
3. 主数据区（表格或任务流）
4. 次级信息区（日志、提示、最近活动）

栅格：
- Desktop: 12 列，gap 24px
- Tablet: 8 列，gap 16px
- Mobile: 4 列，gap 12px

## 4. Component Rules (必须统一)

### Button (VuiButton)
| variant | 样式 | 颜色 |
|---------|------|------|
| contained | 实色背景 | 白底深色字 或 color 指定色 |
| gradient | 纯色背景（无渐变） | #0075FF 白字 |
| outlined | 透明背景 + 边框 | 白字 |
| text | 无背景边框 | 白字，hover 半透明 |

高度统一：small=32px, medium=40px, large=48px
圆角统一：`var(--radius-button)` = 0.75rem

### Card
- 背景：`var(--gradient-card)` 或 `--color-bg-elevated`
- 边框：`1px solid rgba(255,255,255,0.06)`
- 圆角：`var(--radius-xl)` = 1.5rem
- 可选 `backdrop-filter: blur(14px)`

### Input / Select / Textarea
- 背景：`rgba(255,255,255,0.02)`
- 边框：`1px solid rgba(255,255,255,0.06)`
- focus：`border-color: #0075FF` + `box-shadow: 0 0 0 3px rgba(0,117,255,0.28)`
- 高度 40px（textarea 自适应）

### Badge (VuiBadge)
| variant | 样式 |
|---------|------|
| gradient | 纯色背景 + 圆角 pill + 白字 |
| contained | 低透明度背景 + 圆角 pill + 白字 |
| standard | 透明背景 + 边框 + 语义色字 |

所有 badge 强制 `border-radius: 9999px`

### Table
- 表头弱对比（`rgba(255,255,255,0.4)`）
- 行 hover：`background: rgba(255,255,255,0.03)`
- 状态列使用统一状态色 Badge

### Modal / Drawer
- 背景：`bg.elevated`
- 圆角：`md`
- 标题区与内容区分隔清晰

### Toast / Alert
- 信息结构统一：标题 + 说明 + 可选动作

## 5. Status Mapping (任务域专用)
```
queued  -> warning  (#F53939)
running -> info    (#0075FF)
success -> success (#01B574)
failed  -> error   (#F53C2B)
canceled-> muted   (#718096)
```

## 6. Page IA (固定 5 个)
```
/           → 概览（Dashboard）
/library    → 媒体库
/jobs       → 任务管理
/history    → 历史记录
/settings   → 系统设置
```

## 7. Hard Constraints
- 禁止页面内写死颜色、圆角、阴影、字体、间距 → 必须引用 token
- 禁止渐变色用于按钮/badge 等交互元素（纯色优先）
- 禁止同类组件多个视觉版本并存
- 禁止新增第 6 个一级导航页面
- 仅改 UI 层；业务 API、数据模型、提交流程保持兼容
- 所有改动必须可追溯到 token 或组件变体

## 8. 执行 Checklist

- [ ] 审计现有项目并输出不一致项
- [ ] 建立 src/theme/tokens.ts（已完成：色值更新为纯蓝体系）
- [ ] 建立统一组件变体（button/card/input/badge）
- [ ] 批量替换硬编码样式
- [ ] 对齐五个页面的信息架构与视觉层级
- [ ] 状态色和状态文案统一
- [ ] 清理重复旧样式和废弃组件
- [ ] 输出 UI_CONSISTENCY_REPORT.md

## 9. 已确认的设计决策

| 决策 | 值 | 原因 |
|------|-----|------|
| 主色 | #0075FF 纯色 | Vision UI 蓝色按钮，无渐变 |
| 成功色 | #01B574 纯色 | 语义绿 |
| 警告色 | #F53939 纯色 | 语义红 |
| 错误色 | #F53C2B 纯色 | 语义红 |
| Badge 圆角 | pill (9999px) | 胶囊形状 |
| Badge 字色 | 白色（语义色背景） | 深色背景确保可读性 |
| 背景图 | body-background.png | Vision UI 原版蓝紫光晕纹理 |
| 页面背景色 | rgb(3,12,29) | 匹配 html/html bg |
| 卡片背景 | rgb(26, 31, 55) 纯深色 | Vision UI 原版实色卡片 |
| 页面背景 | body-background.png + rgb(3,12,29) | 蓝紫光晕纹理（Vision UI 原版）|
