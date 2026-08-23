<script setup lang="ts">
import { onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { usePluginsStore } from '../stores/plugins'
import NoorBadge from '../noor-kit/NoorBadge.vue'
import NoorButton from '../noor-kit/NoorButton.vue'
import NoorState from '../noor-kit/NoorState.vue'

const store = usePluginsStore()

onMounted(() => store.fetchPlugins())
</script>

<template>
  <section class="page stack">
    <div class="page-heading">
      <div>
        <h1>插件</h1>
        <p>插件管理、启用状态和侧边栏入口。</p>
      </div>
      <NoorButton tone="primary" @click="store.reload()">重载插件</NoorButton>
    </div>

    <div class="metric-grid">
      <div class="metric-card"><span>插件总数</span><strong>{{ store.plugins.length }}</strong></div>
      <div class="metric-card"><span>已启用</span><strong>{{ store.enabledPlugins.length }}</strong></div>
      <div class="metric-card"><span>未启用</span><strong>{{ store.disabledPlugins.length }}</strong></div>
      <div class="metric-card"><span>页面插件</span><strong>{{ store.sidebarPlugins.length }}</strong></div>
    </div>

    <NoorState v-if="store.loading" type="loading" title="加载插件" />
    <NoorState v-else-if="store.error" type="error" :title="store.error" />
    <NoorState v-else-if="!store.plugins.length" type="empty" title="暂无插件" />

    <div v-else class="plugin-grid">
      <article v-for="plugin in store.plugins" :key="plugin.id" class="plugin-card" :class="{ 'is-disabled': !plugin.enabled }">
        <div class="plugin-card__head">
          <div>
            <h2>{{ plugin.name }}</h2>
            <p>{{ plugin.id }} · {{ plugin.version || '-' }}</p>
          </div>
          <NoorBadge :tone="plugin.enabled ? 'success' : 'muted'">{{ plugin.enabled ? '已启用' : '未启用' }}</NoorBadge>
        </div>
        <p class="plugin-desc">{{ plugin.description || '-' }}</p>
        <div class="chip-row">
          <NoorBadge v-for="tag in plugin.tags || []" :key="tag">{{ tag }}</NoorBadge>
        </div>
        <div class="actions">
          <RouterLink v-if="(plugin.contributions?.sidebar as any)?.route" class="link-button" :to="`/plugins/${plugin.id}`">打开</RouterLink>
          <NoorButton :tone="plugin.enabled ? 'ghost' : 'primary'" @click="store.setEnabled(plugin.id, !plugin.enabled)">
            {{ plugin.enabled ? '停用' : '启用' }}
          </NoorButton>
        </div>
      </article>
    </div>
  </section>
</template>
