<script setup lang="ts">
import { computed, ref, watch, nextTick } from 'vue'
import { useSystemLog } from '../../composables/useSystemLog'
import { useI18n } from '../../composables/useI18n'

const { logs, connected, show, stopPolling } = useSystemLog()
const { t } = useI18n()
const container = ref<HTMLElement | null>(null)
const activeLevel = ref<'all' | 'warning' | 'error'>('all')
const levelOptions = [
  { value: 'all', label: '全部' },
  { value: 'warning', label: '警告' },
  { value: 'error', label: '错误' },
] as const

const visibleLogs = computed(() => {
  if (activeLevel.value === 'all') return logs.value
  if (activeLevel.value === 'error') {
    return logs.value.filter(log => log.level === 'error' || log.level === 'critical')
  }
  return logs.value.filter(log => log.level === 'warning')
})

const counts = computed(() => {
  let warning = 0
  let error = 0
  for (const log of logs.value) {
    if (log.level === 'warning') warning += 1
    if (log.level === 'error' || log.level === 'critical') error += 1
  }
  return { total: logs.value.length, warning, error }
})

watch(() => logs.value.length, async () => {
  await nextTick()
  if (container.value) {
    container.value.scrollTop = container.value.scrollHeight
  }
})

function close() {
  stopPolling()
  show.value = false
}

function levelCount(level: 'all' | 'warning' | 'error') {
  if (level === 'warning') return counts.value.warning
  if (level === 'error') return counts.value.error
  return counts.value.total
}

function sourceLabel(source?: string) {
  const value = String(source || 'system')
  if (value === 'frontend') return '前端'
  if (value.startsWith('plugins.') || value.startsWith('plugin.')) return value.replace(/^plugins?\\./, '插件:')
  if (value.startsWith('uvicorn')) return '服务'
  if (value.startsWith('app.')) return value.replace(/^app\\./, '')
  return value
}
</script>

<template>
  <div v-if="show" class="syslog-panel">
    <!-- Header -->
    <div class="syslog-panel__header">
      <div class="flex items-center gap-2">
        <span class="syslog-panel__dot" :class="connected ? 'syslog-panel__dot--on' : 'syslog-panel__dot--off'"></span>
        <span class="syslog-panel__title">{{ t('systemLog.title') }}</span>
        <span class="syslog-panel__mode">临时</span>
      </div>
      <button class="syslog-panel__close" @click="close">
        <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>

    <div class="syslog-panel__filters">
      <button
        v-for="item in levelOptions"
        :key="item.value"
        type="button"
        class="syslog-panel__filter"
        :class="{ 'syslog-panel__filter--active': activeLevel === item.value }"
        @click="activeLevel = item.value"
      >
        <span>{{ item.label }}</span>
        <span class="syslog-panel__filter-count">{{ levelCount(item.value) }}</span>
      </button>
    </div>

    <!-- Log Body -->
    <div ref="container" class="syslog-panel__body">
      <div v-if="logs.length === 0" class="syslog-panel__empty">
        // {{ t('systemLog.waiting') }} · 仅显示打开面板后的日志
      </div>
      <div v-else-if="visibleLogs.length === 0" class="syslog-panel__empty">
        // 当前筛选暂无日志
      </div>
      <div
        v-for="(log, i) in visibleLogs"
        :key="i"
        class="syslog-panel__line"
        :class="{
          'syslog-panel__line--error': log.level === 'error' || log.level === 'critical',
          'syslog-panel__line--warning': log.level === 'warning',
          'syslog-panel__line--debug': log.level === 'debug',
        }"
      >
        <div class="syslog-panel__meta">
          <span class="syslog-panel__time">[{{ log.time }}]</span>
          <span class="syslog-panel__level">{{ log.level }}</span>
          <span class="syslog-panel__source">{{ sourceLabel(log.source) }}</span>
        </div>
        <div class="syslog-panel__text">{{ log.line }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.syslog-panel {
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  width: 380px;
  height: 100vh;
  background:
    radial-gradient(circle at 20% 0%, rgba(0, 117, 255, .14), transparent 34%),
    linear-gradient(180deg, rgba(12, 18, 38, 0.98) 0%, rgba(6, 11, 28, 0.97) 100%);
  border-left: 1px solid rgba(255, 255, 255, 0.06);
  display: flex;
  flex-direction: column;
  z-index: var(--z-sidebar);
  backdrop-filter: blur(18px) saturate(1.2);
  box-shadow: -22px 0 55px rgba(0, 0, 0, .28);
}

.syslog-panel__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.875rem 1rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  flex-shrink: 0;
  height: 64px;
}

.syslog-panel__filters {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: .45rem;
  padding: .65rem .85rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.055);
}

.syslog-panel__filter {
  min-width: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: .35rem;
  height: 1.8rem;
  border: 1px solid rgba(255, 255, 255, .065);
  border-radius: .6rem;
  background: rgba(255, 255, 255, .035);
  color: rgba(255, 255, 255, .42);
  font-size: .68rem;
  transition: background var(--transition-fast), color var(--transition-fast), border-color var(--transition-fast);
}

.syslog-panel__filter:hover,
.syslog-panel__filter--active {
  background: rgba(255, 255, 255, .075);
  border-color: rgba(255, 255, 255, .11);
  color: rgba(255, 255, 255, .78);
}

.syslog-panel__filter-count {
  color: rgba(255, 255, 255, .32);
  font-size: .62rem;
}

.syslog-panel__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.syslog-panel__dot--on {
  background: #01B574;
  box-shadow: 0 0 4px #01B574;
}

.syslog-panel__dot--off {
  background: rgba(255, 255, 255, 0.2);
}

.syslog-panel__title {
  font-family: var(--font-display);
  font-size: 0.75rem;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.7);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.syslog-panel__mode {
  padding: .12rem .4rem;
  border: 1px solid rgba(255, 255, 255, .08);
  border-radius: 999px;
  background: rgba(255, 255, 255, .045);
  color: rgba(255, 255, 255, .36);
  font-size: .62rem;
  line-height: 1;
}

.syslog-panel__close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 1.75rem;
  height: 1.75rem;
  border-radius: var(--radius-sm);
  background: transparent;
  border: none;
  color: rgba(255, 255, 255, 0.35);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.syslog-panel__close:hover {
  background: rgba(255, 255, 255, 0.08);
  color: rgba(255, 255, 255, 0.8);
}

.syslog-panel__body {
  flex: 1;
  overflow-y: auto;
  padding: 0.9rem 0.85rem 1rem;
  font-family: var(--font-mono, 'JetBrains Mono', 'SF Mono', Monaco, monospace);
  font-size: 0.6875rem;
  line-height: 1.6;
  scrollbar-width: thin;
  scrollbar-color: rgba(255,255,255,0.1) transparent;
}

.syslog-panel__body::-webkit-scrollbar {
  width: 4px;
}

.syslog-panel__body::-webkit-scrollbar-track {
  background: transparent;
}

.syslog-panel__body::-webkit-scrollbar-thumb {
  background: rgba(255,255,255,0.1);
  border-radius: 2px;
}

.syslog-panel__empty {
  color: rgba(255, 255, 255, 0.2);
  padding: 1rem 0;
  font-style: italic;
}

.syslog-panel__line {
  display: grid;
  gap: .18rem;
  padding: .38rem .42rem;
  border-radius: .5rem;
  word-break: break-word;
}

.syslog-panel__line:hover {
  background: rgba(255, 255, 255, .035);
}

.syslog-panel__meta {
  display: flex;
  align-items: center;
  gap: .42rem;
  min-width: 0;
}

.syslog-panel__time {
  color: rgba(255, 255, 255, 0.25);
  flex-shrink: 0;
  font-size: 0.625rem;
}

.syslog-panel__level {
  flex: 0 0 auto;
  color: rgba(255, 255, 255, .28);
  text-transform: uppercase;
  font-size: .58rem;
}

.syslog-panel__source {
  min-width: 0;
  overflow: hidden;
  color: rgba(147, 197, 253, .48);
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: .62rem;
}

.syslog-panel__text {
  color: rgba(255, 255, 255, 0.6);
  padding-left: .1rem;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.syslog-panel__line--error .syslog-panel__text {
  color: #F53C2B;
}

.syslog-panel__line--error .syslog-panel__level {
  color: #F53C2B;
}

.syslog-panel__line--warning .syslog-panel__text {
  color: #FFB547;
}

.syslog-panel__line--warning .syslog-panel__level {
  color: #FFB547;
}

.syslog-panel__line--debug .syslog-panel__text {
  color: rgba(255, 255, 255, 0.25);
}

@media (max-width: 1023px) {
  .syslog-panel {
    top: 64px;
    width: min(100vw, 420px);
    height: calc(100vh - 64px);
    z-index: var(--z-modal);
  }

  .syslog-panel__header {
    height: auto;
  }

  .syslog-panel__line {
    padding: .34rem .36rem;
  }
}
</style>
