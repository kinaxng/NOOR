<script setup lang="ts">
import { onMounted } from 'vue'
import { useSettingsStore } from '../stores/settings'
import NoorBadge from '../noor-kit/NoorBadge.vue'
import NoorButton from '../noor-kit/NoorButton.vue'
import NoorState from '../noor-kit/NoorState.vue'

const store = useSettingsStore()

onMounted(() => store.fetchSettings())
</script>

<template>
  <section class="page stack">
    <div class="page-heading">
      <div>
        <h1>设置</h1>
        <p>当前重写版先提供配置总览，保存能力会按模块迁移。</p>
      </div>
      <NoorButton tone="primary" @click="store.fetchSettings()">刷新</NoorButton>
    </div>

    <NoorState v-if="store.loading" type="loading" title="加载设置" />
    <NoorState v-else-if="store.error" type="error" :title="store.error" />

    <div v-else-if="store.settings" class="settings-grid">
      <section class="settings-section">
        <div class="panel-title"><h2>Emby</h2></div>
        <dl>
          <dt>服务器</dt><dd>{{ store.settings.emby?.server || '-' }}</dd>
          <dt>用户</dt><dd>{{ store.settings.emby?.user_id || '-' }}</dd>
          <dt>媒体库</dt><dd>{{ store.settings.emby?.enabled_library_ids?.length || 0 }} 个</dd>
        </dl>
      </section>

      <section class="settings-section">
        <div class="panel-title"><h2>存储</h2></div>
        <dl>
          <dt>源目录</dt><dd>{{ store.settings.storage?.source_dir || '-' }}</dd>
          <dt>输出目录</dt><dd>{{ store.settings.storage?.output_dir || '-' }}</dd>
          <dt>模型目录</dt><dd>{{ store.settings.storage?.whisper_model_dir || '-' }}</dd>
        </dl>
      </section>

      <section class="settings-section">
        <div class="panel-title">
          <h2>Whisper</h2>
          <NoorBadge tone="info">{{ store.settings.whisper?.strategy || 'default' }}</NoorBadge>
        </div>
        <dl>
          <dt>模型</dt><dd>{{ store.settings.whisper?.model || '-' }}</dd>
          <dt>Pass 1</dt><dd>{{ store.settings.whisper?.pass1_pipeline || '-' }}</dd>
          <dt>Pass 2</dt><dd>{{ store.settings.whisper?.pass2_pipeline || '关闭' }}</dd>
          <dt>翻译</dt><dd>{{ store.settings.whisper?.translate_to || '关闭' }}</dd>
        </dl>
      </section>

      <section class="settings-section">
        <div class="panel-title"><h2>网络</h2></div>
        <dl>
          <dt>加速</dt><dd>{{ store.settings.network?.acceleration_mode || '-' }}</dd>
          <dt>HF Mirror</dt><dd>{{ store.settings.network?.hf_mirror || '-' }}</dd>
          <dt>GitHub Mirror</dt><dd>{{ store.settings.network?.github_mirror || '-' }}</dd>
        </dl>
      </section>
    </div>
  </section>
</template>
