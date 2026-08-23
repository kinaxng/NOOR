<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useHardlinksStore } from '../stores/hardlinks'
import NoorBadge from '../noor-kit/NoorBadge.vue'
import NoorButton from '../noor-kit/NoorButton.vue'
import NoorState from '../noor-kit/NoorState.vue'

const store = useHardlinksStore()

const stats = computed(() => [
  { label: '作品组', value: store.groups.length },
  { label: '异常组', value: store.issueGroups.length, filter: 'issue' },
  { label: '仅主文件', value: store.sourceOnlyGroups.length, filter: 'source-only' },
  { label: '仅硬链接', value: store.hardlinkOnlyGroups.length, filter: 'hardlink-only' },
])

function sizeText(value?: number | null) {
  if (!value) return '-'
  if (value > 1024 ** 3) return `${(value / 1024 ** 3).toFixed(2)} GB`
  return `${(value / 1024 ** 2).toFixed(1)} MB`
}

onMounted(() => store.fetchGroups())
</script>

<template>
  <section class="page stack">
    <div class="page-heading">
      <div>
        <h1>硬链接</h1>
        <p>主文件与硬链接关系总览。</p>
      </div>
      <div class="actions">
        <input v-model="store.query" class="input" placeholder="搜索作品或路径" />
        <NoorButton tone="primary" @click="store.fetchGroups()">重新扫描</NoorButton>
      </div>
    </div>

    <div class="metric-grid">
      <button
        v-for="item in stats"
        :key="item.label"
        type="button"
        class="metric-card metric-card--button"
        @click="store.filter = (item.filter as any) || 'all'"
      >
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
      </button>
    </div>

    <div class="actions">
      <NoorButton :tone="store.filter === 'all' ? 'primary' : 'secondary'" @click="store.filter = 'all'">全部</NoorButton>
      <NoorButton :tone="store.filter === 'issue' ? 'primary' : 'secondary'" @click="store.filter = 'issue'">异常组</NoorButton>
      <NoorButton :tone="store.filter === 'source-only' ? 'primary' : 'secondary'" @click="store.filter = 'source-only'">仅主文件</NoorButton>
      <NoorButton :tone="store.filter === 'hardlink-only' ? 'primary' : 'secondary'" @click="store.filter = 'hardlink-only'">仅硬链接</NoorButton>
    </div>

    <NoorState v-if="store.loading" type="loading" title="加载硬链接" />
    <NoorState v-else-if="store.error" type="error" :title="store.error" />
    <NoorState v-else-if="!store.filteredGroups.length" type="empty" title="暂无匹配作品" />

    <div v-else class="hardlink-list">
      <article v-for="group in store.filteredGroups.slice(0, 80)" :key="group.code" class="hardlink-card">
        <div class="hardlink-card__head">
          <h2>{{ group.code }}</h2>
          <NoorBadge :tone="group.status === 'issue' ? 'warning' : 'success'">{{ group.status === 'issue' ? '异常' : '正常' }}</NoorBadge>
        </div>
        <div v-for="entry in group.entries" :key="`${group.code}:${entry.source_path || entry.hardlink_paths.join('|')}`" class="hardlink-entry">
          <div class="path-line">
            <span>主文件</span>
            <strong>{{ entry.source_path || '未找到对应主文件' }}</strong>
            <em>{{ sizeText(entry.source_size) }}</em>
          </div>
          <div v-for="path in entry.hardlink_paths" :key="path" class="path-line">
            <span>硬链接</span>
            <strong>{{ path }}</strong>
          </div>
        </div>
      </article>
    </div>
  </section>
</template>
