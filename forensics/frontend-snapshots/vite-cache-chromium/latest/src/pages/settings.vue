<script setup lang="ts">
import { onMounted } from 'vue'
import { useSettingsStore } from '../stores/settings'
import { useI18n } from '../composables/useI18n'
import { pipelineLabel } from '../app/format'

const { t } = useI18n()
const store = useSettingsStore()

onMounted(() => store.fetchSettings())
</script>

<template>
  <UDashboardPanel id="settings" grow>
    <template #header>
      <UDashboardNavbar :title="t('settings.title')">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <div class="flex items-center gap-2">
            <UButton color="neutral" variant="ghost" @click="store.resetDraft()">{{ t('settings.reset') }}</UButton>
            <UButton color="neutral" variant="ghost" icon="i-heroicons-arrow-path-20-solid" @click="store.fetchSettings()">{{ t('common.refresh') }}</UButton>
          </div>
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div v-if="store.loading" class="flex flex-col items-center justify-center py-12 text-(--ui-text-muted)">
        <UIcon name="i-heroicons-arrow-path-20-solid" class="w-8 h-8 animate-spin mb-4" />
        <p>{{ t('common.loading') }}</p>
      </div>

      <div v-else-if="store.error" class="flex flex-col items-center justify-center py-12">
        <UIcon name="i-heroicons-exclamation-triangle-20-solid" class="w-12 h-12 text-(--ui-error) mb-4" />
        <p class="text-(--ui-error) font-medium">{{ store.error }}</p>
      </div>

      <div v-else-if="!store.loading && store.draft" class="grid grid-cols-1 lg:grid-cols-2 gap-6 pb-12">
        <UCard>
          <template #header>
            <div class="flex items-center justify-between">
              <h3 class="text-base font-semibold">Emby</h3>
              <UBadge color="info" variant="subtle">{{ t('settings.emby.badgeLabel') }}</UBadge>
            </div>
          </template>
          <div class="space-y-4">
            <UFormField :label="t('settings.emby.server')">
              <UInput v-model="store.draft.emby!.server" placeholder="http://127.0.0.1:8096" />
            </UFormField>
            <UFormField :label="t('settings.emby.apiKey')">
              <UInput v-model="store.draft.emby!.api_key" type="password" placeholder="Emby API Key" />
            </UFormField>
            <UFormField :label="t('settings.emby.userId')">
              <UInput v-model="store.draft.emby!.user_id" placeholder="Emby User ID" />
            </UFormField>
            <UFormField :label="t('settings.emby.enabledLibraries')">
              <UInput :model-value="store.draft.emby!.enabled_library_ids?.join(',')" placeholder="e.g. 3,5" @update:model-value="store.draft.emby!.enabled_library_ids = ($event as string).split(',').map((i: string) => i.trim()).filter(Boolean)" />
            </UFormField>
          </div>
          <template #footer>
            <div class="flex justify-end gap-3">
              <UButton color="neutral" variant="ghost" :loading="store.saving === 'test-emby'" @click="store.testEmby()">{{ t('settings.emby.testConnection') }}</UButton>
              <UButton color="primary" :loading="store.saving === 'emby'" @click="store.saveEmby()">{{ t('settings.emby.save') }}</UButton>
            </div>
          </template>
        </UCard>

        <UCard>
          <template #header>
            <h3 class="text-base font-semibold">{{ t('settings.storage.title') }}</h3>
          </template>
          <div class="space-y-4">
            <UFormField :label="t('settings.storage.source')">
              <UInput v-model="store.draft.storage!.source_dir" />
            </UFormField>
            <UFormField :label="t('settings.storage.output')">
              <UInput v-model="store.draft.storage!.output_dir" />
            </UFormField>
            <UFormField :label="t('settings.storage.whisperModelDir')">
              <UInput v-model="store.draft.storage!.whisper_model_dir" />
            </UFormField>
            <UFormField :label="t('settings.storage.ladaModelDir')">
              <UInput v-model="store.draft.storage!.lada_model_weights_dir" />
            </UFormField>
          </div>
          <template #footer>
            <div class="flex justify-end">
              <UButton color="primary" :loading="store.saving === 'storage'" @click="store.saveStorage()">{{ t('settings.storage.save') }}</UButton>
            </div>
          </template>
        </UCard>

        <UCard>
          <template #header>
            <div class="flex items-center justify-between">
              <h3 class="text-base font-semibold">Whisper</h3>
              <UBadge color="info" variant="subtle">{{ pipelineLabel(store.draft.whisper!.strategy || 'default') }}</UBadge>
            </div>
          </template>
          <div class="space-y-4">
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <UFormField :label="t('settings.whisper.strategy')"><UInput v-model="store.draft.whisper!.strategy" /></UFormField>
              <UFormField :label="t('settings.whisper.mainModel')"><UInput v-model="store.draft.whisper!.model" /></UFormField>
              <UFormField :label="t('settings.whisper.pipelineMode')"><UInput v-model="store.draft.whisper!.pipeline_mode" /></UFormField>
              <UFormField :label="t('settings.whisper.language')"><UInput v-model="store.draft.whisper!.language" /></UFormField>
              <UFormField :label="t('settings.whisper.pass1')"><UInput v-model="store.draft.whisper!.pass1_pipeline" /></UFormField>
              <UFormField :label="t('settings.whisper.pass2')"><UInput v-model="store.draft.whisper!.pass2_pipeline" :placeholder="t('settings.placeholder.pass2')" /></UFormField>
              <UFormField :label="t('settings.whisper.audioPreprocess')"><UInput v-model="store.draft.whisper!.audio_preprocess_mode" placeholder="none" /></UFormField>
              <UFormField :label="t('settings.whisper.preprocessModel')"><UInput v-model="store.draft.whisper!.audio_preprocess_model" /></UFormField>
              <UFormField :label="t('settings.whisper.translateTo')"><UInput v-model="store.draft.whisper!.translate_to" :placeholder="t('settings.placeholder.translateTo')" /></UFormField>
              <UFormField :label="t('settings.whisper.translateModel')"><UInput v-model="store.draft.whisper!.translate_model" /></UFormField>
              <UFormField :label="t('settings.whisper.translateEndpoint')" class="sm:col-span-2"><UInput v-model="store.draft.whisper!.translate_base_url" /></UFormField>
              <UFormField :label="t('settings.whisper.translateKey')" class="sm:col-span-2"><UInput v-model="store.draft.whisper!.translate_api_key" type="password" /></UFormField>
            </div>
          </div>
          <template #footer>
            <div class="flex justify-end">
              <UButton color="primary" :loading="store.saving === 'whisper'" @click="store.saveWhisper()">{{ t('settings.whisper.save') }}</UButton>
            </div>
          </template>
        </UCard>

        <UCard>
          <template #header>
            <div class="flex items-center justify-between">
              <h3 class="text-base font-semibold">LADA</h3>
              <UBadge :color="store.draft.lada!.is_docker ? 'warning' : 'success'" variant="subtle">{{ store.draft.lada!.is_docker ? 'Docker' : 'Native' }}</UBadge>
            </div>
          </template>
          <div class="space-y-4">
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <UFormField :label="t('settings.lada.cli')" class="sm:col-span-2"><UInput v-model="store.draft.lada!.cli_path" /></UFormField>
              <UFormField :label="t('settings.lada.version')" class="sm:col-span-2"><UInput :model-value="store.draft.lada!.version || ''" :placeholder="t('settings.placeholder.ladaVersion')" @update:model-value="store.draft.lada!.version = $event" /></UFormField>
              <UFormField :label="t('settings.lada.device')"><UInput v-model="store.draft.lada_defaults!.device" /></UFormField>
              <UFormField :label="t('settings.lada.detectionModel')"><UInput v-model="store.draft.lada_defaults!.detection_model" /></UFormField>
              <UFormField :label="t('settings.lada.restorationModel')"><UInput v-model="store.draft.lada_defaults!.restoration_model" /></UFormField>
              <UFormField :label="t('settings.lada.encodingPreset')"><UInput v-model="store.draft.lada_defaults!.encoding_preset" /></UFormField>
              <UFormField :label="t('settings.lada.maxClipLength')"><UInput :model-value="store.draft.lada_defaults!.max_clip_length" type="number" @update:model-value="store.draft.lada_defaults!.max_clip_length = Number($event || 0)" /></UFormField>
              <div class="flex items-center gap-6 sm:col-span-2 mt-2">
                <UCheckbox v-model="store.draft.lada_defaults!.fp16" :label="t('settings.lada.fp16')" />
                <UCheckbox v-model="store.draft.lada_defaults!.detect_face_mosaics" :label="t('settings.lada.detectFaceMosaics')" />
              </div>
            </div>
          </div>
          <template #footer>
            <div class="flex justify-end gap-3">
              <UButton color="neutral" variant="ghost" :loading="store.saving === 'lada'" @click="store.saveLada()">{{ t('settings.lada.saveCli') }}</UButton>
              <UButton color="primary" :loading="store.saving === 'lada-defaults'" @click="store.saveLadaDefaults()">{{ t('settings.lada.saveDefaults') }}</UButton>
            </div>
          </template>
        </UCard>

        <UCard class="lg:col-span-2">
          <template #header>
            <h3 class="text-base font-semibold">{{ t('settings.network.title') }}</h3>
          </template>
          <div class="space-y-4">
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              <UFormField :label="t('settings.network.mode')"><UInput v-model="store.draft.network!.acceleration_mode" placeholder="none / proxy / mirror" /></UFormField>
              <UFormField :label="t('settings.network.proxy')"><UInput v-model="store.draft.network!.http_proxy" /></UFormField>
              <UFormField :label="t('settings.network.hfToken')"><UInput v-model="store.draft.network!.hf_token" type="password" /></UFormField>
              <UFormField :label="t('settings.network.hfMirror')"><UInput v-model="store.draft.network!.hf_mirror" /></UFormField>
              <UFormField :label="t('settings.network.githubMirror')"><UInput v-model="store.draft.network!.github_mirror" /></UFormField>
              <UFormField :label="t('settings.network.pipMirror')"><UInput v-model="store.draft.network!.pip_mirror" /></UFormField>
            </div>
          </div>
          <template #footer>
            <div class="flex justify-end">
              <UButton color="primary" :loading="store.saving === 'network'" @click="store.saveNetwork()">{{ t('settings.network.save') }}</UButton>
            </div>
          </template>
        </UCard>
      </div>
    </template>
  </UDashboardPanel>
</template>
