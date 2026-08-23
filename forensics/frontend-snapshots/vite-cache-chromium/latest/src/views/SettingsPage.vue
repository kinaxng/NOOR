<script setup lang="ts">
import { onMounted } from 'vue'
import { useSettingsStore } from '../stores/settings'
import NoorBadge from '../noor-kit/NoorBadge.vue'
import NoorButton from '../noor-kit/NoorButton.vue'
import NoorInput from '../noor-kit/NoorInput.vue'
import NoorState from '../noor-kit/NoorState.vue'
import NoorToggle from '../noor-kit/NoorToggle.vue'

const store = useSettingsStore()

onMounted(() => store.fetchSettings())
</script>

<template>
  <section class="page stack">
    <div class="page-heading">
      <div>
        <h1>设置</h1>
        <p>重写版逐步接回主配置：媒体源、路径、Whisper、LADA 与网络。</p>
      </div>
      <div class="actions">
        <NoorButton @click="store.resetDraft()">恢复</NoorButton>
        <NoorButton tone="primary" @click="store.fetchSettings()">刷新</NoorButton>
      </div>
    </div>

    <NoorState v-if="store.loading" type="loading" title="加载设置" />
    <NoorState v-else-if="store.error" type="error" :title="store.error" />
    <NoorState v-if="store.message" type="empty" :title="store.message" />

    <div v-if="!store.loading && store.draft" class="settings-grid">
      <section class="settings-section">
        <div class="panel-title">
          <h2>Emby</h2>
          <NoorBadge tone="info">媒体源</NoorBadge>
        </div>
        <div class="settings-form">
          <label><span>服务器</span><NoorInput v-model="store.draft.emby!.server" placeholder="http://127.0.0.1:8096" /></label>
          <label><span>API Key</span><NoorInput v-model="store.draft.emby!.api_key" type="password" placeholder="Emby API Key" /></label>
          <label><span>用户 ID</span><NoorInput v-model="store.draft.emby!.user_id" placeholder="Emby User ID" /></label>
          <label><span>启用媒体库</span><NoorInput :model-value="store.draft.emby!.enabled_library_ids?.join(',')" placeholder="例如：3,5" @update:model-value="store.draft.emby!.enabled_library_ids = $event.split(',').map(i => i.trim()).filter(Boolean)" /></label>
        </div>
        <div class="settings-actions">
          <NoorButton :disabled="store.saving === 'test-emby'" @click="store.testEmby()">{{ store.saving === 'test-emby' ? '测试中' : '测试连接' }}</NoorButton>
          <NoorButton tone="primary" :disabled="store.saving === 'emby'" @click="store.saveEmby()">{{ store.saving === 'emby' ? '保存中' : '保存 Emby' }}</NoorButton>
        </div>
      </section>

      <section class="settings-section">
        <div class="panel-title"><h2>存储路径</h2></div>
        <div class="settings-form">
          <label><span>源目录</span><NoorInput v-model="store.draft.storage!.source_dir" /></label>
          <label><span>输出目录</span><NoorInput v-model="store.draft.storage!.output_dir" /></label>
          <label><span>Whisper 模型目录</span><NoorInput v-model="store.draft.storage!.whisper_model_dir" /></label>
          <label><span>LADA 模型目录</span><NoorInput v-model="store.draft.storage!.lada_model_weights_dir" /></label>
        </div>
        <div class="settings-actions">
          <NoorButton tone="primary" :disabled="store.saving === 'storage'" @click="store.saveStorage()">{{ store.saving === 'storage' ? '保存中' : '保存路径' }}</NoorButton>
        </div>
      </section>

      <section class="settings-section">
        <div class="panel-title">
          <h2>Whisper</h2>
          <NoorBadge tone="info">{{ store.draft.whisper!.strategy || 'default' }}</NoorBadge>
        </div>
        <div class="settings-form">
          <label><span>策略</span><NoorInput v-model="store.draft.whisper!.strategy" /></label>
          <label><span>主模型</span><NoorInput v-model="store.draft.whisper!.model" /></label>
          <label><span>Pipeline</span><NoorInput v-model="store.draft.whisper!.pipeline_mode" /></label>
          <label><span>语言</span><NoorInput v-model="store.draft.whisper!.language" /></label>
          <label><span>Pass 1</span><NoorInput v-model="store.draft.whisper!.pass1_pipeline" /></label>
          <label><span>Pass 2</span><NoorInput v-model="store.draft.whisper!.pass2_pipeline" placeholder="留空关闭" /></label>
          <label><span>音频预处理</span><NoorInput v-model="store.draft.whisper!.audio_preprocess_mode" placeholder="none" /></label>
          <label><span>预处理模型</span><NoorInput v-model="store.draft.whisper!.audio_preprocess_model" /></label>
          <label><span>翻译目标</span><NoorInput v-model="store.draft.whisper!.translate_to" placeholder="留空关闭，例如 zh" /></label>
          <label><span>翻译模型</span><NoorInput v-model="store.draft.whisper!.translate_model" /></label>
          <label><span>翻译端点</span><NoorInput v-model="store.draft.whisper!.translate_base_url" /></label>
          <label><span>翻译 Key</span><NoorInput v-model="store.draft.whisper!.translate_api_key" type="password" /></label>
        </div>
        <div class="settings-actions">
          <NoorButton tone="primary" :disabled="store.saving === 'whisper'" @click="store.saveWhisper()">{{ store.saving === 'whisper' ? '保存中' : '保存 Whisper' }}</NoorButton>
        </div>
      </section>

      <section class="settings-section">
        <div class="panel-title">
          <h2>LADA</h2>
          <NoorBadge :tone="store.draft.lada!.is_docker ? 'warning' : 'success'">{{ store.draft.lada!.is_docker ? 'Docker' : 'Native' }}</NoorBadge>
        </div>
        <div class="settings-form">
          <label><span>CLI</span><NoorInput v-model="store.draft.lada!.cli_path" /></label>
          <label><span>版本</span><NoorInput :model-value="store.draft.lada!.version || ''" placeholder="自动检测" @update:model-value="store.draft.lada!.version = $event" /></label>
          <label><span>设备</span><NoorInput v-model="store.draft.lada_defaults!.device" /></label>
          <label><span>检测模型</span><NoorInput v-model="store.draft.lada_defaults!.detection_model" /></label>
          <label><span>修复模型</span><NoorInput v-model="store.draft.lada_defaults!.restoration_model" /></label>
          <label><span>编码预设</span><NoorInput v-model="store.draft.lada_defaults!.encoding_preset" /></label>
          <label><span>最大片段秒数</span><NoorInput :model-value="store.draft.lada_defaults!.max_clip_length" type="number" @update:model-value="store.draft.lada_defaults!.max_clip_length = Number($event || 0)" /></label>
          <label><span>FP16</span><NoorToggle v-model="store.draft.lada_defaults!.fp16" label="启用" /></label>
          <label><span>人脸马赛克检测</span><NoorToggle v-model="store.draft.lada_defaults!.detect_face_mosaics" label="启用" /></label>
        </div>
        <div class="settings-actions">
          <NoorButton :disabled="store.saving === 'lada'" @click="store.saveLada()">{{ store.saving === 'lada' ? '保存中' : '保存 LADA CLI' }}</NoorButton>
          <NoorButton tone="primary" :disabled="store.saving === 'lada-defaults'" @click="store.saveLadaDefaults()">{{ store.saving === 'lada-defaults' ? '保存中' : '保存默认参数' }}</NoorButton>
        </div>
      </section>

      <section class="settings-section settings-section--wide">
        <div class="panel-title"><h2>网络加速</h2></div>
        <div class="settings-form settings-form--wide">
          <label><span>模式</span><NoorInput v-model="store.draft.network!.acceleration_mode" placeholder="none / proxy / mirror" /></label>
          <label><span>HTTP Proxy</span><NoorInput v-model="store.draft.network!.http_proxy" /></label>
          <label><span>HF Mirror</span><NoorInput v-model="store.draft.network!.hf_mirror" /></label>
          <label><span>GitHub Mirror</span><NoorInput v-model="store.draft.network!.github_mirror" /></label>
          <label><span>Pip Mirror</span><NoorInput v-model="store.draft.network!.pip_mirror" /></label>
          <label><span>HF Token</span><NoorInput v-model="store.draft.network!.hf_token" type="password" /></label>
        </div>
        <div class="settings-actions">
          <NoorButton tone="primary" :disabled="store.saving === 'network'" @click="store.saveNetwork()">{{ store.saving === 'network' ? '保存中' : '保存网络' }}</NoorButton>
        </div>
      </section>
    </div>
  </section>
</template>
