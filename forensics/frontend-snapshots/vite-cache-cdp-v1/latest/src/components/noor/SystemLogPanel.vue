<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { useSystemLog } from '../../composables/useSystemLog'
import { useI18n } from '../../composables/useI18n'

const { logs, connected, show, stopPolling } = useSystemLog()
const { t } = useI18n()
const container = ref<HTMLElement | null>(null)

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
</script>

<template>
  <div v-if="show" class="syslog-panel">
    <!-- Header -->
    <div class="syslog-panel__header">
      <div class="flex items-center gap-2">
        <span class="syslog-panel__dot" :class="connected ? 'syslog-panel__dot--on' : 'syslog-panel__dot--off'"></span>
        <span class="syslog-panel__title">{{ t('systemLog.title') }}</span>
      </div>
      <button class="syslog-panel__close" @click="close">
        <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>

    <!-- Log Body -->
    <div ref="container" class="syslog-panel__body">
      <div v-if="logs.length === 0" class="syslog-panel__empty">
        // {{ t('systemLog.waiting') }}
      </div>
      <div
        v-for="(log, i) in logs"
        :key="i"
        class="syslog-panel__line"
        :class="{
          'syslog-panel__line--error': log.level === 'error' || log.level === 'critical',
          'syslog-panel__line--warning': log.level === 'warning',
          'syslog-panel__line--debug': log.level === 'debug',
        }"
      >
        <span class="syslog-panel__time">[{{ log.time }}]</span>
        <span class="syslog-panel__text">{{ log.line }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.syslog-panel {
  position: fixed;
  top: 64px; /* below navbar */
  right: 0;
  width: 360px;
  height: calc(100vh - 64px);
  background: linear-gradient(180deg, rgba(6, 11, 40, 0.98) 0%, rgba(10, 14, 35, 0.95) 100%);
  border-left: 1px solid rgba(255, 255, 255, 0.06);
  display: flex;
  flex-direction: column;
  z-index: 40;
  backdrop-filter: blur(12px);
}

.syslog-panel__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.875rem 1rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  flex-shrink: 0;
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
  padding: 0.75rem;
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
  display: flex;
  gap: 0.5rem;
  padding: 0.125rem 0;
  word-break: break-all;
}

.syslog-panel__time {
  color: rgba(255, 255, 255, 0.25);
  flex-shrink: 0;
  font-size: 0.625rem;
}

.syslog-panel__text {
  color: rgba(255, 255, 255, 0.6);
}

.syslog-panel__line--error .syslog-panel__text {
  color: #F53C2B;
}

.syslog-panel__line--warning .syslog-panel__text {
  color: #FFB547;
}

.syslog-panel__line--debug .syslog-panel__text {
  color: rgba(255, 255, 255, 0.25);
}
</style>
