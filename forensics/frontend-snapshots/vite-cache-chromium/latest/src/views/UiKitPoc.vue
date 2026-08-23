<script setup lang="ts">
import { ref } from 'vue'
import { NoorBadge, NoorButton, NoorDialog, NoorTabs, NoorTopActionBar } from '@/components/noor-kit'

const activeTab = ref('overview')
const dialogOpen = ref(false)
</script>

<template>
  <div class="ui-card space-y-5">
    <div>
      <p class="text-xs font-semibold uppercase tracking-wider text-white/40">NOOR UI Kit PoC</p>
      <h2 class="mt-1 text-xl font-bold text-white">Nuxt UI bridge</h2>
      <p class="mt-1 max-w-2xl text-sm text-white/50">
        低风险验证页：主程序 Vue 组件通过 NOOR Kit 包装 Nuxt UI；插件继续通过 sdk.ui 使用同一语义。
      </p>
    </div>

    <NoorTopActionBar>
      <template #tabs>
        <NoorTabs
          v-model="activeTab"
          :tabs="[
            { key: 'overview', label: '概览' },
            { key: 'actions', label: '操作' },
            { key: 'dialog', label: '弹窗' },
          ]"
        />
      </template>
      <NoorBadge tone="info">状态型</NoorBadge>
      <NoorBadge tone="success">已验证</NoorBadge>
      <NoorButton tone="secondary">功能按钮</NoorButton>
      <NoorButton tone="primary" @click="dialogOpen = true">打开弹窗</NoorButton>
    </NoorTopActionBar>

    <div class="grid gap-3 md:grid-cols-3">
      <div class="rounded-lg border border-white/8 bg-white/[0.035] p-4">
        <div class="text-sm font-bold text-white">Button</div>
        <div class="mt-3 flex flex-wrap gap-2">
          <NoorButton tone="primary">Primary</NoorButton>
          <NoorButton tone="secondary">Secondary</NoorButton>
          <NoorButton tone="danger">Danger</NoorButton>
        </div>
      </div>
      <div class="rounded-lg border border-white/8 bg-white/[0.035] p-4">
        <div class="text-sm font-bold text-white">Badge</div>
        <div class="mt-3 flex flex-wrap gap-2">
          <NoorBadge>Muted</NoorBadge>
          <NoorBadge tone="warning">Warning</NoorBadge>
          <NoorBadge tone="danger">Danger</NoorBadge>
        </div>
      </div>
      <div class="rounded-lg border border-white/8 bg-white/[0.035] p-4">
        <div class="text-sm font-bold text-white">Tabs</div>
        <p class="mt-3 text-sm text-white/55">当前：{{ activeTab }}</p>
      </div>
    </div>

    <NoorDialog v-model:open="dialogOpen" title="Nuxt UI Dialog" description="通过 NOOR Kit 包装后的弹窗。">
      <p class="text-sm leading-6 text-white/65">
        这个弹窗来自 Nuxt UI UModal，但视觉 token 已映射到 NOOR 深色体系。
      </p>
      <template #footer>
        <div class="flex justify-end gap-2">
          <NoorButton tone="secondary" @click="dialogOpen = false">关闭</NoorButton>
          <NoorButton tone="primary" @click="dialogOpen = false">确认</NoorButton>
        </div>
      </template>
    </NoorDialog>
  </div>
</template>
