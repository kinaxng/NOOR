<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useMediaStore } from '../stores/media'
import NoorButton from '../noor-kit/NoorButton.vue'
import NoorBadge from '../noor-kit/NoorBadge.vue'
import NoorPagination from '../noor-kit/NoorPagination.vue'
import NoorSelect from '../noor-kit/NoorSelect.vue'
import NoorState from '../noor-kit/NoorState.vue'
import NoorTabs from '../noor-kit/NoorTabs.vue'
import NoorToggle from '../noor-kit/NoorToggle.vue'

const media = useMediaStore()
const searchText = ref('')
const subtitleTab = ref<'local' | 'online' | 'whisper'>('local')

const subtitleTabs = computed(() => [
  { key: 'local', label: `本地字幕 ${media.subtitles.length}` },
  { key: 'online', label: `字幕搜索 ${media.onlineSubtitles.length}` },
  { key: 'whisper', label: '生成字幕' },
])

const libraryOptions = computed(() => [
  { label: '全部媒体库', value: '' },
  ...media.libraries.map(library => ({ label: library.name, value: library.id })),
])

function fileNameOf(path?: string | null, fallback = '-') {
  if (!path) return fallback
  return path.split('/').pop() || fallback
}

function formatBytes(value?: number | null) {
  const size = Number(value || 0)
  if (!size) return '-'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let n = size
  let i = 0
  while (n >= 1024 && i < units.length - 1) {
    n /= 1024
    i += 1
  }
  return `${n.toFixed(i === 0 ? 0 : 1)} ${units[i]}`
}

onMounted(() => media.initialize())
</script>

<template>
  <section class="page stack">
    <div class="page-heading">
      <div>
        <h1>媒体库</h1>
        <p>来自 Emby API 的作品列表。</p>
      </div>
      <div class="actions">
        <NoorSelect :model-value="media.selectedLibraryId" :options="libraryOptions" @update:model-value="media.selectLibrary(String($event))" />
        <input v-model="searchText" class="input" placeholder="搜索作品" @keyup.enter="media.search(searchText)" />
        <NoorButton tone="primary" @click="media.search(searchText)">搜索</NoorButton>
      </div>
    </div>

    <NoorState v-if="media.loading" type="loading" title="加载媒体库" />
    <NoorState v-else-if="media.error" type="error" :title="media.error" />
    <NoorState v-else-if="!media.items.length" type="empty" title="暂无作品" />

    <template v-else>
      <div class="media-grid">
        <article v-for="item in media.items" :key="item.id" class="media-card" role="button" tabindex="0" @click="media.fetchItemDetail(item.id)" @keydown.enter="media.fetchItemDetail(item.id)">
          <div class="media-cover">
            <img v-if="item.poster_path || item.fanart_path" :src="item.poster_path || item.fanart_path" :alt="item.name" loading="lazy" />
            <span v-else>NO IMAGE</span>
          </div>
          <div class="media-card__body">
            <h2>{{ item.name }}</h2>
            <p>{{ item.path || item.date_created || '-' }}</p>
          </div>
        </article>
      </div>
      <NoorPagination v-model:page="media.page" :total="media.total" :page-size="media.pageSize" @update:page="media.fetchItems" />
    </template>

    <div v-if="media.selectedItem || media.detailLoading" class="detail-mask" @click.self="media.closeDetail()">
      <aside class="detail-panel">
        <NoorState v-if="media.detailLoading" type="loading" title="加载作品详情" />
        <template v-else-if="media.selectedItem">
          <div class="detail-hero">
            <img v-if="media.selectedItem.backdrop_path || media.selectedItem.poster_path" :src="media.selectedItem.backdrop_path || media.selectedItem.poster_path" :alt="media.selectedItem.name" />
            <div class="detail-hero__actions">
              <NoorButton tone="primary" :disabled="!media.previewVideoUrl()" @click="media.openSelectedVideo()">播放选中版本</NoorButton>
              <NoorButton class="detail-close" @click="media.closeDetail()">关闭</NoorButton>
            </div>
          </div>
          <div class="detail-body">
            <h2>{{ media.selectedItem.name }}</h2>
            <p>{{ media.selectedItem.file_path || media.selectedItem.path }}</p>

            <div class="detail-meta">
              <span>演员：{{ media.selectedItem.actors?.map(actor => actor.name).join('、') || '-' }}</span>
              <span>片商：{{ media.selectedItem.studios?.join('、') || '-' }}</span>
              <span>发行：{{ media.selectedItem.premiered || '-' }}</span>
            </div>

            <div class="chip-row">
              <NoorBadge v-for="genre in media.selectedItem.genres?.slice(0, 20)" :key="genre">{{ genre }}</NoorBadge>
            </div>

            <section class="versions">
              <h3>文件版本</h3>
              <NoorButton tone="ghost" class="version-row" :class="{ 'is-active': media.selectedVersionPath === (media.selectedItem.file_path || media.selectedItem.path) }" @click="media.selectVersion(media.selectedItem.file_path || media.selectedItem.path)">
                <strong>{{ fileNameOf(media.selectedItem.file_path || media.selectedItem.path, media.selectedItem.name) }}</strong>
                <span>{{ media.selectedItem.file_path || media.selectedItem.path }}</span>
              </NoorButton>
              <NoorButton v-for="sibling in media.selectedItem.siblings || []" :key="sibling.id || sibling.file_path" tone="ghost" class="version-row" :class="{ 'is-active': media.selectedVersionPath === sibling.file_path }" @click="media.selectVersion(sibling.file_path)">
                <strong>{{ fileNameOf(sibling.file_path, sibling.name || sibling.label) }}</strong>
                <span>{{ sibling.file_path }}</span>
              </NoorButton>
            </section>

            <section class="subtitle-panel">
              <div class="subtitle-panel__head">
                <div>
                  <h3>字幕</h3>
                  <p>当前版本：{{ fileNameOf(media.selectedVersionPath) }}</p>
                </div>
                <div class="actions">
                  <NoorButton :disabled="media.subtitleLoading" @click="media.fetchSubtitles()">{{ media.subtitleLoading ? '扫描中' : '重新扫描' }}</NoorButton>
                  <NoorButton tone="primary" :disabled="media.onlineSearching" @click="media.searchOnlineSubtitles(false)">{{ media.onlineSearching ? '搜索中' : '搜索字幕' }}</NoorButton>
                </div>
              </div>

              <NoorTabs v-model="subtitleTab" :tabs="subtitleTabs" />
              <NoorState v-if="media.subtitleError" type="error" :title="media.subtitleError" />

              <div v-if="subtitleTab === 'local'" class="subtitle-list">
                <NoorState v-if="media.subtitleLoading" type="loading" title="扫描本地字幕" />
                <NoorState v-else-if="!media.subtitles.length" type="empty" title="未发现本地字幕" />
                <template v-else>
                  <article v-for="subtitle in media.subtitles" :key="subtitle.path" class="subtitle-row">
                    <div>
                      <strong>{{ subtitle.filename }}</strong>
                      <span>{{ subtitle.ext }} · {{ formatBytes(subtitle.size) }}</span>
                    </div>
                    <div class="actions">
                      <NoorButton :disabled="media.subtitleAction === subtitle.path" @click="media.previewLocalSubtitle(subtitle)">预览</NoorButton>
                      <NoorButton tone="danger" :disabled="media.subtitleAction === subtitle.path" @click="media.deleteLocalSubtitle(subtitle)">删除</NoorButton>
                    </div>
                  </article>
                </template>
              </div>

              <div v-else-if="subtitleTab === 'online'" class="subtitle-list">
                <NoorState v-if="media.onlineSearching" type="loading" title="搜索字幕源" />
                <NoorState v-else-if="!media.onlineSubtitles.length" type="empty" title="暂无搜索结果" />
                <template v-else>
                  <article v-for="subtitle in media.onlineSubtitles" :key="subtitle.url" class="subtitle-row">
                    <div>
                      <strong>{{ subtitle.name }}</strong>
                      <span>{{ subtitle.source || subtitle.source_key || '字幕源' }} · {{ subtitle.language || '-' }} · {{ subtitle.ext || '.srt' }}</span>
                    </div>
                    <div class="actions">
                      <NoorButton :disabled="media.subtitleAction === subtitle.url" @click="media.previewOnlineSubtitle(subtitle)">预览</NoorButton>
                      <NoorButton tone="primary" :disabled="media.subtitleAction === subtitle.url" @click="media.downloadOnlineSubtitle(subtitle)">下载</NoorButton>
                    </div>
                  </article>
                </template>
              </div>

              <div v-else class="whisper-flow">
                <ol>
                  <li class="is-fixed">切分音频 / VAD</li>
                  <li class="is-fixed">Anime-Whisper 主转写</li>
                  <li class="is-fixed">large-v3 fallback</li>
                  <li class="is-fixed">Qwen fallback / 对齐补救</li>
                  <li class="is-optional"><NoorToggle v-model="media.whisperPreprocess" label="音频预处理" /></li>
                  <li class="is-optional"><NoorToggle v-model="media.whisperTranslate" label="生成后翻译中文" /></li>
                </ol>
                <NoorButton tone="primary" :disabled="media.taskSubmitting === 'whisper'" @click="media.submitWhisperTask()">{{ media.taskSubmitting === 'whisper' ? '提交中' : '提交字幕任务' }}</NoorButton>
              </div>
            </section>

            <section class="task-panel">
              <div class="task-panel__head">
                <div>
                  <h3>LADA 修复</h3>
                  <p>使用设置页里的 LADA 默认参数提交当前选中版本。</p>
                </div>
                <NoorButton tone="primary" :disabled="media.taskSubmitting === 'lada'" @click="media.submitLadaTask()">{{ media.taskSubmitting === 'lada' ? '提交中' : '提交 LADA 任务' }}</NoorButton>
              </div>
            </section>

            <div v-if="media.subtitlePreview" class="modal-mask" @click.self="media.closeSubtitlePreview()">
              <section class="subtitle-preview">
                <div>
                  <h3>{{ media.subtitlePreview.filename }}</h3>
                  <p>{{ media.subtitlePreview.source === 'local' ? '本地字幕' : '在线字幕' }}</p>
                </div>
                <pre>{{ media.subtitlePreview.content }}</pre>
                <div class="actions">
                  <NoorButton tone="primary" @click="media.closeSubtitlePreview()">关闭</NoorButton>
                </div>
              </section>
            </div>

            <NoorState v-if="media.taskMessage" type="empty" :title="media.taskMessage" />
            <NoorState v-if="media.taskError" type="error" :title="media.taskError" />
          </div>
        </template>
      </aside>
    </div>
  </section>
</template>
