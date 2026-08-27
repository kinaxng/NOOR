<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import VuiButton from '../ui/Button/VuiButton.vue'
import VuiBadge from '../ui/Badge/VuiBadge.vue'
import { useI18n } from '../../composables/useI18n'
import type { FileTags, MediaItem, MediaItemDetail } from '../../api/types'
import PanelHeader from './panels/PanelHeader.vue'
import api from '../../api'
import { useToast } from '../../composables/useToast'

const { t, i18nVersion, currentLang } = useI18n()
const toast = useToast()

const directorLabel = computed(() => {
  void i18nVersion.value
  return t('detail.director')
})
const errorLabel = computed(() => {
  void i18nVersion.value
  return t('common.error')
})
const closeLabel = computed(() => {
  void i18nVersion.value
  return t('common.close')
})
const codeLabel = computed(() => {
  void i18nVersion.value
  return t('detail.code')
})
const releaseLabel = computed(() => {
  void i18nVersion.value
  return t('detail.release')
})
const premieredLabel = computed(() => {
  void i18nVersion.value
  return t('detail.premiered')
})
const addedLabel = computed(() => {
  void i18nVersion.value
  return t('detail.added')
})
const ratingLabel = computed(() => {
  void i18nVersion.value
  return t('detail.rating')
})
const seriesLabel = computed(() => {
  void i18nVersion.value
  return t('detail.series')
})
const plotLabel = computed(() => {
  void i18nVersion.value
  return t('detail.plot')
})
const originalTitleLabel = computed(() => {
  void i18nVersion.value
  return t('detail.originalTitle')
})
const tagsLabel = computed(() => {
  void i18nVersion.value
  return t('detail.tags')
})
const notAvailableLabel = computed(() => {
  void i18nVersion.value
  return t('common.notAvailable')
})
const previewUnsupportedLabel = computed(() => {
  void i18nVersion.value
  return t('hardlinks.previewUnsupported')
})
const previewFailedLabel = computed(() => {
  void i18nVersion.value
  return t('detail.previewFailed')
})
const overviewLabel = computed(() => {
  void i18nVersion.value
  return t('detail.overview')
})
const panelTitleLabel = computed(() => {
  void i18nVersion.value
  return t('detail.panelTitle')
})
const filesLabel = computed(() => {
  void i18nVersion.value
  return t('detail.files')
})
const noVariantsLabel = computed(() => {
  void i18nVersion.value
  return t('detail.variant.none')
})
const chineseLabel = computed(() => {
  void i18nVersion.value
  return t('mediacard.chinese')
})
const crackedLabel = computed(() => {
  void i18nVersion.value
  return t('mediacard.cracked')
})
const leakedLabel = computed(() => {
  void i18nVersion.value
  return t('library.filter.leaked')
})
const uncensoredLabel = computed(() => {
  void i18nVersion.value
  return t('library.filter.uncensored')
})

const props = defineProps<{
  open: boolean
  item: MediaItem | null
  detail: MediaItemDetail | null
  loading: boolean
  error: string | null
}>()

const emit = defineEmits<{
  close: []
  versionMarked: [result: { old_path: string; new_path: string; mark: string; tags: FileTags }]
}>()

const previewVideoPath = ref('')
const previewStreamUrl = ref('')
const previewUseLocalFallback = ref(false)
const previewFailed = ref(false)

// Merge genres from NFO and Emby, removing duplicates.
// Filter out:
// - labeled scraper fields like "发行: xxx"
// - media-type style placeholders like "单体作品"
// - tags that duplicate studio / series / code prefix
const allGenres = computed(() => {
  if (!props.detail) return []
  const blocked = new Set<string>()
  const codeLikeSources = [
    props.detail.nfo?.num,
    props.detail.nfo?.id,
    props.detail.name,
    props.detail.file_path?.split('/').pop()?.replace(/\.[^.]+$/, ''),
  ]

  for (const source of codeLikeSources) {
    const match = source?.match(/[A-Za-z]{2,10}-?\d{2,6}/)
    const code = match?.[0]?.trim()
    const prefix = code?.split('-')?.[0]?.trim()
    if (code) blocked.add(code.toLowerCase())
    if (prefix) blocked.add(prefix.toLowerCase())
  }

  for (const value of [
    props.detail.nfo?.set,
    props.detail.nfo?.maker,
    props.detail.nfo?.label,
    props.detail.nfo?.publisher,
    ...(props.detail.studios || []),
    ...(props.detail.nfo?.actors || []).map((actor) => actor?.name),
    ...(props.detail.actors || []).map((actor) => actor?.name),
  ]) {
    const normalized = value?.trim().toLowerCase()
    if (normalized) blocked.add(normalized)
  }

  const mediaTypeLike = new Set(['单体作品', '合集', '系列', 'movie', 'video'])
  const merged = [...(props.detail.nfo?.genres || []), ...(props.detail.genres || [])]
  return [...new Set(
    merged.filter((genre: string) => {
      const value = genre?.trim()
      if (!value) return false
      if (value.includes(':')) return false
      if (mediaTypeLike.has(value.toLowerCase())) return false
      if (blocked.has(value.toLowerCase())) return false
      return true
    })
  )]
})

// All file paths in the same folder (current + siblings)
const allFolderPaths = computed(() => {
  if (!props.detail?.file_path) return []
  const paths = [props.detail.file_path]
  for (const s of (props.detail.siblings || [])) {
    if (s.file_path && !paths.includes(s.file_path)) {
      paths.push(s.file_path)
    }
  }
  return paths
})

const previewVideoName = computed(() => previewVideoPath.value.split('/').pop() || previewVideoPath.value)

const previewLocalUrl = computed(() => {
  if (!previewVideoPath.value) return ''
  return `/api/media-library/hardlinks/preview-file?path=${encodeURIComponent(previewVideoPath.value)}`
})

const previewVideoUrl = computed(() => {
  if (previewUseLocalFallback.value || !previewStreamUrl.value) return previewLocalUrl.value
  return previewStreamUrl.value
})

const variantCount = computed(() => props.detail?.variant_count || allFolderPaths.value.length)

const displayTitle = computed(() => {
  if (!props.detail) return ''
  return props.detail.nfo?.title || props.detail.nfo?.originaltitle || props.detail.name
})

const originalTitle = computed(() => {
  const title = props.detail?.nfo?.originaltitle?.trim()
  if (!title) return ''
  return title !== displayTitle.value ? title : ''
})

const releaseDisplay = computed(() => {
  const year = props.detail?.nfo?.year?.trim()
  if (year) return year
  const premiered = props.detail?.nfo?.premiered || props.detail?.premiered
  if (!premiered) return ''
  return formatDate(premiered)
})

const premieredDisplay = computed(() => {
  const premiered = props.detail?.premiered || props.detail?.nfo?.premiered
  if (!premiered) return ''
  const formatted = formatDate(premiered)
  return formatted !== releaseDisplay.value ? formatted : ''
})

const studioItems = computed(() => {
  const values = [
    props.detail?.nfo?.maker,
    props.detail?.nfo?.label,
    props.detail?.nfo?.publisher,
    ...(props.detail?.studios || []),
  ]
  return [...new Set(values.map((value) => value?.trim()).filter(Boolean) as string[])]
})

const detailTagItems = computed(() => variantTagItems(props.detail?.tags))

function fileNameOf(path?: string, fallback?: string) {
  if (path) {
    const name = path.split('/').pop()
    if (name) return name
  }
  return fallback || notAvailableLabel.value
}

function dirNameOf(path?: string) {
  if (!path) return ''
  const idx = path.lastIndexOf('/')
  if (idx <= 0) return path
  return path.slice(0, idx)
}

const variantRows = computed(() => {
  if (!props.detail?.file_path) return []
  const current = {
    id: props.detail.id,
    path: props.detail.file_path,
    streamUrl: props.detail.stream_url,
    name: fileNameOf(props.detail.file_path, props.detail.name),
    dir: dirNameOf(props.detail.file_path),
    tags: props.detail.tags,
  }
  const siblings = (props.detail.siblings || [])
    .filter((s) => s.file_path)
    .map((s, index) => ({
      id: s.id || `${props.detail?.id}-sib-${index}`,
      path: s.file_path!,
      streamUrl: s.stream_url,
      name: fileNameOf(s.file_path, s.name || s.label || `${filesLabel.value} ${index + 1}`),
      dir: dirNameOf(s.file_path),
      tags: s.tags,
    }))
  return [current, ...siblings]
})

const selectedVariantPath = ref('')

watch(previewVideoPath, (value) => {
  document.body.style.overflow = value ? 'hidden' : ''
})

watch(variantRows, (rows) => {
  if (!rows.length) {
    selectedVariantPath.value = ''
    return
  }
  if (!rows.some((variant) => variant.path === selectedVariantPath.value)) {
    selectedVariantPath.value = rows[0].path
  }
}, { immediate: true })

const selectedVariant = computed(() => {
  return variantRows.value.find((variant) => variant.path === selectedVariantPath.value) || variantRows.value[0] || null
})

const selectedVariantName = computed(() => selectedVariant.value?.name || '')
const markingVersion = ref(false)
const selectedVersionMark = computed(() => {
  const tags = selectedVariant.value?.tags
  if (tags?.is_cracked && tags?.has_chinese) return '破解-C'
  if (tags?.is_cracked) return '破解'
  if (tags?.has_chinese) return 'C'
  return ''
})

async function setVersionMark(mark: string) {
  const path = selectedVariant.value?.path
  if (!path || markingVersion.value || mark === selectedVersionMark.value) return
  markingVersion.value = true
  try {
    const { data } = await api.post('/media-library/hardlinks/version-mark', { file_path: path, mark })
    selectedVariantPath.value = data.new_path
    emit('versionMarked', data)
    toast.success(`版本标记已更新为 ${mark || '未标记'}`)
  } catch (error: any) {
    toast.error(error?.response?.data?.detail || error?.message || '版本标记更新失败')
  } finally {
    markingVersion.value = false
  }
}

function selectVariant(path: string) {
  selectedVariantPath.value = path
}

function variantTagItems(tags?: FileTags) {
  if (!tags) return []
  const items: { key: string; label: string; tone: 'blue' | 'green' | 'amber' | 'slate' }[] = []
  if (tags.has_chinese) items.push({ key: 'chinese', label: chineseLabel.value, tone: 'green' })
  if (tags.release_type_key === 'leaked') {
    items.push({ key: 'leaked', label: leakedLabel.value, tone: 'amber' })
  } else if (tags.release_type_key === 'uncensored') {
    items.push({ key: 'uncensored', label: uncensoredLabel.value, tone: 'slate' })
  }
  if (tags.is_cracked) items.push({ key: 'cracked', label: crackedLabel.value, tone: 'blue' })
  return items
}

function handleClose() {
  emit('close')
}

function openPreview(path?: string) {
  const targetVariant = path
    ? variantRows.value.find((variant) => variant.path === path)
    : selectedVariant.value
  const targetPath = path || targetVariant?.path || props.detail?.file_path
  if (!targetPath) return
  previewFailed.value = false
  previewUseLocalFallback.value = false
  previewVideoPath.value = targetPath
  previewStreamUrl.value = targetVariant?.streamUrl || props.detail?.stream_url || ''
}


function closePreview() {
  previewVideoPath.value = ''
  previewStreamUrl.value = ''
  previewUseLocalFallback.value = false
  previewFailed.value = false
}

function handlePreviewError() {
  if (!previewUseLocalFallback.value && previewLocalUrl.value) {
    previewUseLocalFallback.value = true
    return
  }
  previewFailed.value = true
}

function formatDate(dateStr: string | undefined): string {
  if (!dateStr) return notAvailableLabel.value
  return new Date(dateStr).toLocaleDateString(currentLang.value === 'zh' ? 'zh-CN' : 'en-US', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  })
}
</script>

<template>
  <Teleport to="body">
    <Transition name="panel">
      <div
        v-if="open"
        class="fixed inset-0 z-50 flex justify-end"
      >
        <!-- Backdrop -->
        <div
          class="absolute inset-0 bg-bg-void/80 backdrop-blur-sm"
          @click="handleClose"
        ></div>

        <!-- Panel -->
        <div class="relative bg-bg-surface border-l border-border-default flex flex-col overflow-hidden shadow-2xl h-full w-full lg:w-[min(50vw,960px)]">

          <!-- Loading State -->
          <div v-if="loading" class="flex items-center justify-center flex-1">
            <div class="animate-spin w-8 h-8 border-2 border-accent-cyan border-t-transparent rounded-full"></div>
          </div>

          <!-- Error State -->
          <div v-else-if="error" class="flex flex-col items-center justify-center flex-1 p-8 text-center">
            <div class="text-status-error text-lg mb-2">{{ errorLabel }}</div>
            <div class="text-text-secondary text-sm max-w-md">{{ error }}</div>
            <VuiButton variant="outlined" color="secondary" size="small" @click="handleClose" class="mt-4">
              {{ closeLabel }}
            </VuiButton>
          </div>

          <!-- Content -->
          <template v-else-if="detail">
            <!-- Scrollable wrapper -->
            <div class="flex-1 overflow-y-auto p-4 space-y-4 relative">

              <div class="detail-panel-topbar">
                <div class="detail-panel-topbar__meta">
                  <span class="detail-panel-topbar__eyebrow">{{ panelTitleLabel }}</span>
                </div>
                <button
                  @click="handleClose"
                  :title="closeLabel"
                  :aria-label="closeLabel"
                  class="detail-panel-topbar__close"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>

              <!-- Shared Header: backdrop + title + tagline + actors -->
              <PanelHeader :detail="detail" :selected-variant-name="selectedVariantName" :show-play="true" @play="openPreview" />

              <section class="ui-card detail-panel-section">
                <div class="detail-panel-section__head">
                  <span class="detail-panel-section__title">{{ overviewLabel }}</span>
                </div>

                <div class="grid grid-cols-2 gap-3">
                  <div v-if="detail.nfo?.num">
                    <span class="text-[10px] text-text-muted uppercase tracking-wider">{{ codeLabel }}</span>
                    <p class="text-sm text-accent-cyan font-medium mt-0.5 font-mono">{{ detail.nfo.num }}</p>
                  </div>
                  <div v-if="releaseDisplay">
                    <span class="text-[10px] text-text-muted uppercase tracking-wider">{{ releaseLabel }}</span>
                    <p class="text-sm text-text-primary mt-0.5">{{ releaseDisplay }}</p>
                  </div>
                  <div v-if="detail.date_created">
                    <span class="text-[10px] text-text-muted uppercase tracking-wider">{{ addedLabel }}</span>
                    <p class="text-sm text-text-primary mt-0.5">{{ formatDate(detail.date_created) }}</p>
                  </div>
                  <div v-if="detail.nfo?.rating">
                    <span class="text-[10px] text-text-muted uppercase tracking-wider">{{ ratingLabel }}</span>
                    <div class="flex items-center gap-1 mt-0.5">
                      <svg class="w-4 h-4 text-accent-amber" fill="currentColor" viewBox="0 0 20 20"><path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" /></svg>
                      <span class="text-sm text-accent-amber font-medium">{{ detail.nfo.rating }}</span>
                      <span v-if="detail.nfo?.votes" class="text-xs text-text-muted">({{ detail.nfo.votes }})</span>
                    </div>
                  </div>
                  <div v-if="detail.nfo?.director">
                    <span class="text-[10px] text-text-muted uppercase tracking-wider">{{ directorLabel }}</span>
                    <p class="text-sm text-text-primary mt-0.5 truncate" :title="detail.nfo.director">{{ detail.nfo.director }}</p>
                  </div>
                </div>

                <div
                  v-if="originalTitle || premieredDisplay || detailTagItems.length"
                  class="detail-panel-block"
                >
                  <div class="grid grid-cols-2 gap-3">
                    <div v-if="originalTitle" class="col-span-2">
                      <span class="text-[10px] text-text-muted uppercase tracking-wider">{{ originalTitleLabel }}</span>
                      <p class="text-sm text-text-primary mt-0.5 leading-relaxed">{{ originalTitle }}</p>
                    </div>
                    <div v-if="premieredDisplay">
                      <span class="text-[10px] text-text-muted uppercase tracking-wider">{{ premieredLabel }}</span>
                      <p class="text-sm text-text-primary mt-0.5">{{ premieredDisplay }}</p>
                    </div>
                    <div v-if="detailTagItems.length" class="col-span-2">
                      <span class="text-[10px] text-text-muted uppercase tracking-wider">{{ tagsLabel }}</span>
                      <div class="mt-1 flex flex-wrap gap-1">
                        <span
                          v-for="tag in detailTagItems"
                          :key="tag.key"
                          class="rounded-full px-2 py-0.5 text-[10px]"
                          :class="{
                            'border border-emerald-400/20 bg-emerald-500/10 text-emerald-200': tag.tone === 'green',
                            'border border-sky-400/20 bg-sky-500/10 text-sky-200': tag.tone === 'blue',
                            'border border-amber-400/20 bg-amber-500/10 text-amber-200': tag.tone === 'amber',
                            'border border-white/15 bg-white/10 text-white/75': tag.tone === 'slate',
                          }"
                        >
                          {{ tag.label }}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>

                <div v-if="detail.nfo?.set || studioItems.length" class="detail-panel-block">
                  <div v-if="detail.nfo?.set" class="mb-3">
                    <span class="text-[10px] text-text-muted uppercase tracking-wider">{{ seriesLabel }}</span>
                    <p class="mt-1">
                      <VuiBadge color="purple">{{ detail.nfo.set }}</VuiBadge>
                    </p>
                  </div>
                  <div v-if="studioItems.length" class="mb-2">
                    <span class="text-[10px] text-text-muted uppercase tracking-wider">{{ t('detail.studio') }}</span>
                    <div class="flex flex-wrap gap-1 mt-1">
                      <VuiBadge v-for="studio in studioItems" :key="studio" color="magenta">{{ studio }}</VuiBadge>
                    </div>
                  </div>
                </div>

                <div v-if="allGenres.length" class="detail-panel-block">
                  <span class="text-[10px] text-text-muted uppercase tracking-wider">{{ t('detail.genres') }}</span>
                  <div class="flex flex-wrap gap-1 mt-2">
                    <VuiBadge v-for="genre in allGenres" :key="genre" color="cyan">
                      {{ genre }}
                    </VuiBadge>
                  </div>
                </div>

                <div v-if="detail.nfo?.outline || detail.nfo?.plot" class="detail-panel-block">
                  <span class="text-[10px] text-text-muted uppercase tracking-wider">{{ plotLabel }}</span>
                  <div class="mt-2 space-y-2">
                    <p v-if="detail.nfo?.outline" class="text-sm text-text-secondary leading-relaxed">
                      {{ detail.nfo.outline }}
                    </p>
                    <p v-if="detail.nfo?.plot" class="text-sm text-text-secondary leading-relaxed">
                      {{ detail.nfo.plot }}
                    </p>
                  </div>
                </div>
              </section>

              <section class="ui-card detail-panel-section">
                <div class="detail-panel-section__head">
                  <span class="detail-panel-section__title">{{ filesLabel }}</span>
                  <span v-if="variantCount > 1" class="detail-panel-section__meta">{{ variantCount }}</span>
                </div>

                <div v-if="variantRows.length">
                  <div class="version-mark-control">
                    <span class="version-mark-control__label">版本标记</span>
                    <div class="version-mark-control__options">
                      <button
                        v-for="option in [{ value: '', label: '未标记' }, { value: '破解', label: '破解' }, { value: 'C', label: 'C 中文' }, { value: '破解-C', label: '破解-C 破解中文' }]"
                        :key="option.value || 'none'"
                        type="button"
                        class="version-mark-control__option"
                        :class="{ 'version-mark-control__option--active': selectedVersionMark === option.value }"
                        :disabled="markingVersion"
                        @click="setVersionMark(option.value)"
                      >{{ option.label }}</button>
                    </div>
                  </div>
                  <div class="space-y-2">
                    <div
                      v-for="variant in variantRows"
                      :key="variant.path"
                      class="detail-variant-card rounded-lg px-2.5 py-2"
                      :class="{ 'detail-variant-card--active': selectedVariant?.path === variant.path }"
                      @click="selectVariant(variant.path)"
                    >
                      <div class="flex items-start justify-between gap-2">
                        <div class="min-w-0 flex-1">
                          <div class="detail-variant-card__top">
                            <span class="truncate text-xs font-medium text-white/82">{{ variant.name }}</span>
                            <span v-if="selectedVariant?.path === variant.path" class="detail-variant-card__selected">{{ t('detail.selected') }}</span>
                          </div>
                          <p
                            v-if="selectedVariant?.path === variant.path && variant.dir"
                            class="detail-variant-card__dir"
                            :title="variant.path"
                          >
                            {{ variant.dir }}
                          </p>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
                <div v-else class="detail-panel-strip">
                  {{ noVariantsLabel }}
                </div>
              </section>

            </div>
          </template>

        </div>
      </div>
    </Transition>
  </Teleport>

  <Teleport to="body">
    <div v-if="previewVideoPath" class="preview-overlay">
      <div class="preview-overlay__backdrop" @click="closePreview"></div>
      <div class="preview-overlay__dialog">
        <button
          class="preview-overlay__close"
          :title="closeLabel"
          :aria-label="closeLabel"
          @click="closePreview"
        >
            <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
        </button>
        <div class="preview-overlay__body">
          <video
            :key="previewVideoUrl"
            class="preview-modal__player"
            :src="previewVideoUrl"
            controls
            autoplay
            preload="metadata"
            playsinline
            @error="handlePreviewError"
          />
          <div class="preview-overlay__meta">
            <span class="preview-overlay__name">{{ previewVideoName }}</span>
            <span v-if="previewFailed" class="preview-modal__error">{{ previewFailedLabel }}</span>
            <span v-else class="preview-modal__hint">{{ previewUnsupportedLabel }}</span>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>

.detail-panel-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
}

.detail-panel-topbar__meta {
  min-width: 0;
}

.detail-panel-topbar__eyebrow {
  display: inline-flex;
  align-items: center;
  min-height: 1.5rem;
  font-size: 0.72rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--color-text-muted);
}

.detail-panel-topbar__close {
  width: 2.1rem;
  height: 2.1rem;
  flex: none;
  border-radius: 0.7rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--color-text-secondary);
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border-default);
  transition: color 0.16s ease, background 0.16s ease, border-color 0.16s ease, transform 0.16s ease;
}

.detail-panel-topbar__close:hover {
  color: var(--color-text-primary);
  background: var(--color-bg-hover);
  border-color: var(--color-border-strong);
  transform: translateY(-1px);
}

.detail-variant-card {
  cursor: pointer;
  border: 1px solid transparent;
  background: var(--color-bg-surface);
  transition: border-color 0.16s ease, background 0.16s ease, transform 0.16s ease, box-shadow 0.16s ease;
}

.detail-variant-card:hover {
  background: var(--color-bg-hover);
}

.detail-variant-card--active {
  border-color: color-mix(in srgb, var(--color-border-focus) 38%, transparent);
  background: color-mix(in srgb, var(--color-border-focus) 10%, transparent);
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--color-border-focus) 14%, transparent);
}

.detail-variant-card__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
}

.detail-variant-card__selected {
  flex-shrink: 0;
  border-radius: 999px;
  padding: 0.125rem 0.5rem;
  font-size: 10px;
  font-weight: 600;
  color: var(--color-text-secondary);
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border-default);
}

.detail-variant-card--active .detail-variant-card__selected {
  color: var(--color-text-primary);
  background: color-mix(in srgb, var(--color-border-focus) 18%, transparent);
  border-color: color-mix(in srgb, var(--color-border-focus) 28%, transparent);
}

.detail-variant-card__dir {
  margin-top: 0.25rem;
  font-family: var(--font-mono);
  font-size: 0.5625rem;
  line-height: 1.35;
  color: var(--color-text-muted);
  word-break: break-all;
}

.detail-variant-card--active .detail-variant-card__dir {
  color: var(--color-text-secondary);
}

.detail-panel-section {
  display: flex;
  flex-direction: column;
  gap: 0.875rem;
}

.detail-panel-section__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
}

.detail-panel-section__title {
  font-size: 0.75rem;
  color: var(--color-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.detail-panel-section__meta {
  font-size: 0.75rem;
  color: var(--color-text-secondary);
}

.detail-action-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.375rem;
}

.detail-action-row :deep(.vui-button) {
  min-height: 2rem;
  padding-inline: 0.75rem;
}

.detail-panel-strip {
  margin-top: -0.25rem;
  border-radius: var(--radius-md);
  background: var(--color-border-subtle);
  padding: 0.625rem 0.75rem;
  font-size: 0.75rem;
  color: var(--color-text-secondary);
}

.detail-panel-block {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding-top: 0.25rem;
  border-top: 1px solid var(--color-border-subtle);
}

.panel-enter-active {
  transition: opacity 0.25s ease;
}
.panel-enter-active .bg-bg-surface {
  transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}
.panel-enter-from {
  opacity: 0;
}
.panel-enter-from .bg-bg-surface {
  transform: translateX(100%);
}
.panel-leave-active {
  transition: opacity 0.2s ease;
}
.panel-leave-to {
  opacity: 0;
}
.panel-leave-from .bg-bg-surface {
  transform: translateX(100%);
}

.preview-overlay {
  position: fixed;
  inset: 0;
  z-index: 160;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
}

.preview-overlay__backdrop {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.72);
}

.preview-overlay__dialog {
  position: relative;
  z-index: 1;
  width: min(960px, calc(100vw - 2rem));
  max-height: min(72vh, 720px);
  display: flex;
  flex-direction: column;
  background: #000;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 0.875rem;
  overflow: hidden;
  box-shadow: 0 24px 56px rgba(0, 0, 0, 0.48);
}

.preview-overlay__close {
  position: absolute;
  top: 0.75rem;
  right: 0.75rem;
  z-index: 2;
  width: 2.25rem;
  height: 2.25rem;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  background: rgba(0, 0, 0, 0.44);
  border: 1px solid rgba(255, 255, 255, 0.14);
}

.preview-overlay__body {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding: 0.75rem;
}

.preview-modal__player {
  width: 100%;
  height: auto;
  max-height: min(60vh, 620px);
  min-height: 240px;
  object-fit: contain;
  background: #000;
}

.preview-overlay__meta {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  min-height: 1.25rem;
  color: rgba(255, 255, 255, 0.72);
  font-size: 0.75rem;
  line-height: 1.2;
}

.preview-overlay__name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.preview-modal__hint,
.preview-modal__error {
  margin: 0;
  font-size: 0.75rem;
}

.preview-modal__hint {
  color: rgba(255, 255, 255, 0.54);
}

.preview-modal__error {
  color: #f87171;
}

@media (max-width: 720px) {
  .preview-overlay {
    padding: 0.5rem;
    align-items: flex-end;
  }

  .preview-overlay__dialog {
    width: 100%;
    max-height: 56vh;
    border-radius: 0.75rem;
  }

  .preview-modal__player {
    min-height: 180px;
    max-height: 44vh;
  }
}

.version-mark-control { display:flex; align-items:center; justify-content:space-between; gap:.75rem; margin-bottom:.75rem; }
.version-mark-control__label { color:var(--color-text-muted); font-size:.7rem; white-space:nowrap; }
.version-mark-control__options { display:flex; gap:.25rem; overflow-x:auto; }
.version-mark-control__option { border:1px solid var(--color-border-default); border-radius:999px; color:var(--color-text-secondary); font-size:.68rem; padding:.28rem .55rem; white-space:nowrap; }
.version-mark-control__option:hover { border-color:var(--color-accent-cyan); color:var(--color-text-primary); }
.version-mark-control__option--active { background:color-mix(in srgb, var(--color-accent-cyan) 14%, transparent); border-color:color-mix(in srgb, var(--color-accent-cyan) 48%, transparent); color:var(--color-accent-cyan); }
.version-mark-control__option:disabled { cursor:wait; opacity:.6; }
</style>
