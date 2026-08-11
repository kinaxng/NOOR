<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import VuiButton from '../ui/Button/VuiButton.vue'
import VuiBadge from '../ui/Badge/VuiBadge.vue'
import BaseModal from '../ui/BaseModal.vue'
import { useI18n } from '../../composables/useI18n'
import type { FileTags, MediaItem, MediaItemDetail } from '../../api/types'
import PanelHeader from './panels/PanelHeader.vue'

const { t, i18nVersion, currentLang } = useI18n()

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
}>()

const previewVideoPath = ref('')
const previewFailed = ref(false)

// Merge genres from NFO and Emby, removing duplicates
// Filter out genres containing ":" (these are labeled fields like "发行: kawaii", "片商: kawaii" from 刮削 tools)
const allGenres = computed(() => {
  if (!props.detail) return []
  const nfoGenres = (props.detail.nfo?.genres || []).filter((g: string) => !g.includes(':'))
  const embyGenres = (props.detail.genres || []).filter((g: string) => !g.includes(':'))
  return [...new Set([...nfoGenres, ...embyGenres])]
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

const previewVideoUrl = computed(() => {
  if (!previewVideoPath.value) return ''
  return `/api/media-library/hardlinks/preview-file?path=${encodeURIComponent(previewVideoPath.value)}`
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
    name: fileNameOf(props.detail.file_path, props.detail.name),
    dir: dirNameOf(props.detail.file_path),
    tags: props.detail.tags,
  }
  const siblings = (props.detail.siblings || [])
    .filter((s) => s.file_path)
    .map((s, index) => ({
      id: s.id || `${props.detail?.id}-sib-${index}`,
      path: s.file_path!,
      name: fileNameOf(s.file_path, s.name || s.label || `${filesLabel.value} ${index + 1}`),
      dir: dirNameOf(s.file_path),
      tags: s.tags,
    }))
  return [current, ...siblings]
})

const selectedVariantPath = ref('')

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
  const targetPath = path || selectedVariant.value?.path || props.detail?.file_path
  if (!targetPath) return
  previewFailed.value = false
  previewVideoPath.value = targetPath
}

function closePreview() {
  previewVideoPath.value = ''
  previewFailed.value = false
}

function handlePreviewError() {
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
        <div class="relative bg-bg-surface border-l border-border-default flex flex-col overflow-hidden shadow-2xl h-full w-full max-w-md">

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

              <!-- Shared Header: backdrop + title + tagline + actors -->
              <PanelHeader :detail="detail" :selected-variant-name="selectedVariantName" @play="openPreview" />

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
                  <div class="space-y-2">
                    <div
                      v-for="variant in variantRows"
                      :key="variant.path"
                      class="detail-variant-card rounded-lg border border-white/6 bg-bg-elevated/80 px-3 py-2"
                      :class="{ 'detail-variant-card--active': selectedVariant?.path === variant.path }"
                      @click="selectVariant(variant.path)"
                    >
                      <div class="flex items-start justify-between gap-2">
                        <div class="min-w-0 flex-1">
                          <div class="flex flex-wrap items-center gap-2">
                            <span class="truncate text-xs font-medium text-text-primary">{{ variant.name }}</span>
                            <span v-if="selectedVariant?.path === variant.path" class="detail-variant-card__selected">{{ t('detail.selected') }}</span>
                            <span
                              v-for="tag in variantTagItems(variant.tags)"
                              :key="`${variant.path}-${tag.key}`"
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

              <!-- Fixed Close Button -->
              <button
                @click="handleClose"
                :title="closeLabel"
                :aria-label="closeLabel"
                class="detail-close-btn"
              >
                <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>

            </div>
          </template>

        </div>
      </div>
    </Transition>
  </Teleport>

  <BaseModal
    v-if="previewVideoPath"
    :title="previewVideoName"
    size="lg"
    @close="closePreview"
  >
    <div class="preview-modal">
      <div class="preview-modal__meta font-mono text-xs">{{ previewVideoPath }}</div>
      <video
        :key="previewVideoUrl"
        class="preview-modal__player"
        :src="previewVideoUrl"
        controls
        autoplay
        preload="metadata"
        @error="handlePreviewError"
      />
      <p v-if="previewFailed" class="preview-modal__error">{{ previewFailedLabel }}</p>
      <p class="preview-modal__hint">{{ previewUnsupportedLabel }}</p>
    </div>
  </BaseModal>
</template>

<style scoped>

.detail-variant-card {
  cursor: pointer;
  transition: border-color 0.16s ease, background 0.16s ease, transform 0.16s ease;
}

.detail-variant-card:hover {
  border-color: rgba(255,255,255,0.14);
  background: rgba(255,255,255,0.05);
}

.detail-variant-card--active {
  border-color: rgba(0, 117, 255, 0.45);
  background: rgba(0, 117, 255, 0.08);
  box-shadow: inset 0 0 0 1px rgba(0, 117, 255, 0.14);
}

.detail-variant-card__selected {
  border-radius: 999px;
  padding: 0.125rem 0.5rem;
  font-size: 10px;
  color: rgba(189, 225, 255, 0.95);
  background: rgba(0, 117, 255, 0.18);
  border: 1px solid rgba(0, 117, 255, 0.24);
}

.detail-variant-card__dir {
  margin-top: 0.4rem;
  font-family: var(--font-mono);
  font-size: 0.625rem;
  line-height: 1.45;
  color: var(--color-text-muted);
  word-break: break-all;
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

.detail-panel-strip {
  margin-top: -0.25rem;
  border-radius: var(--radius-md);
  background: rgba(255,255,255,0.04);
  padding: 0.625rem 0.75rem;
  font-size: 0.75rem;
  color: var(--color-text-secondary);
}

.detail-panel-block {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding-top: 0.25rem;
  border-top: 1px solid rgba(255,255,255,0.06);
}

.detail-close-btn {
  position: absolute;
  top: 0.875rem;
  right: 0.875rem;
  width: 2.25rem;
  height: 2.25rem;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--color-text-secondary);
  background: rgba(3, 12, 29, 0.72);
  border: 1px solid rgba(255,255,255,0.10);
  backdrop-filter: blur(10px);
  transition: color 0.16s ease, background 0.16s ease, border-color 0.16s ease, transform 0.16s ease;
}

.detail-close-btn:hover {
  color: var(--color-text-primary);
  background: rgba(26, 31, 55, 0.92);
  border-color: rgba(255,255,255,0.16);
  transform: translateY(-1px);
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

.preview-modal {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.preview-modal__meta {
  color: var(--color-text-muted);
  word-break: break-all;
}

.preview-modal__player {
  width: 100%;
  max-height: 70vh;
  border-radius: var(--radius-md);
  background: #000;
}

.preview-modal__hint {
  margin: 0;
  color: var(--color-text-muted);
  font-size: 0.75rem;
}

.preview-modal__error {
  margin: 0;
  color: var(--color-status-error);
  font-size: 0.75rem;
}
</style>
