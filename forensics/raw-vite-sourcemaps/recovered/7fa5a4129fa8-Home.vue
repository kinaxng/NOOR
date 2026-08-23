<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useEmbyStore } from '../stores/emby'
import { useJobsStore } from '../stores/jobs'
import type { EmbyItem, EmbyItemDetail, JobSettings } from '../api/types'

const embyStore = useEmbyStore()
const jobsStore = useJobsStore()

const showModal = ref(false)
const selectedVideo = ref<EmbyItem | null>(null)
const videoDetail = ref<EmbyItemDetail | null>(null)
const loadingDetail = ref(false)
const submitting = ref(false)
const imageLoadErrors = ref<Set<string>>(new Set())

const settings = ref<JobSettings>({
  detection_model: 'v4-fast',
  restoration_model: 'basicvsrpp-v1.2',
  encoding_preset: 'hevc-nvidia-gpu-hq',
})

onMounted(() => {
  embyStore.fetchLibraries()
})

watch(() => embyStore.selectedLibrary, (library) => {
  if (library) {
    embyStore.fetchItems(library.id)
  }
})

function selectLibrary(library: any) {
  embyStore.selectLibrary(library)
}

function selectVideo(item: EmbyItem) {
  selectedVideo.value = item
  showModal.value = true
  loadingDetail.value = true
  videoDetail.value = null

  embyStore.fetchItemDetail(item.id).then(() => {
    videoDetail.value = embyStore.selectedItem
  }).catch((e) => {
    console.error(e)
  }).finally(() => {
    loadingDetail.value = false
  })
}

function closeModal() {
  showModal.value = false
  selectedVideo.value = null
  videoDetail.value = null
}

function onImageError(itemId: string) {
  imageLoadErrors.value.add(itemId)
}

function getDisplayName(item: EmbyItem): string {
  return item.nfo?.title || item.nfo?.originaltitle || item.name
}

function getDisplayTitle(item: EmbyItemDetail): string {
  return item.nfo?.title || item.nfo?.originaltitle || item.name
}

async function submitJob() {
  if (!selectedVideo.value || !videoDetail.value?.file_path) return

  submitting.value = true
  try {
    const displayName = getDisplayTitle(videoDetail.value)
    const job = await jobsStore.createJob({
      emby_item_id: selectedVideo.value.id,
      emby_item_name: displayName,
      input_path: videoDetail.value.file_path,
      settings: settings.value,
    })
    closeModal()
    alert(`Job submitted! Job ID: ${job.id}`)
  } catch (e) {
    console.error(e)
    alert('Failed to submit job')
  } finally {
    submitting.value = false
  }
}

async function quickSubmit(item: EmbyItem) {
  if (!item.path) {
    try {
      await embyStore.fetchItemDetail(item.id)
      const detail = embyStore.selectedItem
      if (detail?.file_path) {
        const job = await jobsStore.createJob({
          emby_item_id: item.id,
          emby_item_name: getDisplayName(item),
          input_path: detail.file_path,
          settings: settings.value,
        })
        alert(`Job submitted! Job ID: ${job.id}`)
      }
    } catch (e) {
      console.error(e)
      alert('Failed to submit job')
    }
  } else {
    const job = await jobsStore.createJob({
      emby_item_id: item.id,
      emby_item_name: getDisplayName(item),
      input_path: item.path,
      settings: settings.value,
    })
    alert(`Job submitted! Job ID: ${job.id}`)
  }
}

function goNextPage() {
  embyStore.nextPage()
}

function goPrevPage() {
  embyStore.prevPage()
}

const filterButtons = [
  { key: 'all', label: '全部' },
  { key: 'cracked', label: '破解' },
  { key: 'chinese', label: '中文' },
  { key: 'leaked', label: '流出' },
  { key: 'uncensored', label: '无码' },
]

function setFilter(key: string) {
  embyStore.setFilter(key === 'all' ? null : key)
}
</script>

<template>
  <div class="flex h-[calc(100vh-3.5rem)]">
    <!-- Sidebar - Libraries -->
    <div class="w-64 bg-gray-800 border-r border-gray-700 overflow-y-auto">
      <div class="p-4">
        <h2 class="text-sm font-semibold text-gray-400 uppercase mb-3">Media Libraries</h2>
        <div v-if="embyStore.loading && embyStore.libraries.length === 0" class="text-gray-400">Loading...</div>
        <div v-else-if="embyStore.error" class="text-red-400 text-sm">{{ embyStore.error }}</div>
        <div v-else class="space-y-1">
          <button
            v-for="lib in embyStore.libraries"
            :key="lib.id"
            @click="selectLibrary(lib)"
            :class="[
              'w-full text-left px-3 py-2 rounded-md text-sm transition-colors flex items-center gap-2',
              embyStore.selectedLibrary?.id === lib.id
                ? 'bg-blue-600 text-white'
                : 'text-gray-300 hover:bg-gray-700'
            ]"
          >
            <span v-if="lib.poster_path" class="w-8 h-10 bg-gray-600 rounded overflow-hidden flex-shrink-0">
              <img :src="lib.poster_path" class="w-full h-full object-cover" @error="() => {}" />
            </span>
            <span class="truncate">{{ lib.name }}</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Main Content - Items -->
    <div class="flex-1 overflow-y-auto p-6">
      <div v-if="!embyStore.selectedLibrary" class="h-full flex items-center justify-center text-gray-400">
        Select a library to browse videos
      </div>
      <div v-else>
        <!-- Header with filters and pagination -->
        <div class="flex flex-wrap justify-between items-center gap-4 mb-6">
          <div>
            <h2 class="text-2xl font-bold">{{ embyStore.selectedLibrary.name }}</h2>
            <p class="text-gray-400 text-sm">{{ embyStore.total }} items</p>
          </div>

          <!-- Filter buttons -->
          <div class="flex flex-wrap gap-2">
            <button
              v-for="btn in filterButtons"
              :key="btn.key"
              @click="setFilter(btn.key)"
              :class="[
                'px-3 py-1 rounded text-sm transition-colors',
                (btn.key === 'all' ? null : btn.key) === embyStore.filterTag
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
              ]"
            >
              {{ btn.label }}
            </button>
          </div>
        </div>

        <!-- Loading -->
        <div v-if="embyStore.loading" class="text-gray-400">Loading...</div>

        <!-- Items grid -->
        <div v-else-if="embyStore.filteredItems.length === 0" class="text-gray-400">
          No items found with current filter
        </div>
        <div v-else class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8 gap-4">
          <div
            v-for="item in embyStore.filteredItems"
            :key="item.id"
            @click="selectVideo(item)"
            class="bg-gray-800 rounded-lg overflow-hidden cursor-pointer hover:ring-2 hover:ring-blue-500 transition-all group"
          >
            <div class="aspect-[2/3] bg-gray-700 relative">
              <img
                v-if="item.poster_path && !imageLoadErrors.has(item.id)"
                :src="item.poster_path"
                :alt="item.name"
                class="w-full h-full object-cover"
                loading="lazy"
                @error="() => onImageError(item.id)"
              />
              <div v-else class="w-full h-full flex items-center justify-center text-gray-500 text-xs">
                No Cover
              </div>
              <!-- NFO badge -->
              <div v-if="item.nfo" class="absolute top-1 right-1 bg-yellow-500 text-black text-xs px-1 rounded">
                NFO
              </div>
            </div>
            <div class="p-2">
              <p class="text-xs truncate" :title="getDisplayName(item)">{{ getDisplayName(item) }}</p>
              <!-- Tags row -->
              <div class="flex flex-wrap gap-1 mt-1">
                <!-- Cracked/Uncracked button -->
                <button
                  v-if="item.tags?.is_cracked"
                  class="text-xs px-1.5 py-0.5 rounded bg-green-600 text-white hover:bg-green-500"
                  @click.stop="quickSubmit(item)"
                  title="点击提交任务"
                >
                  破解
                </button>
                <span
                  v-else
                  class="text-xs px-1.5 py-0.5 rounded bg-gray-600 text-gray-400"
                >
                  未破解
                </span>
                <!-- Chinese button -->
                <span
                  v-if="item.tags?.has_chinese"
                  class="text-xs px-1.5 py-0.5 rounded bg-red-600 text-white"
                >
                  中文
                </span>
                <!-- Release type badge -->
                <span
                  v-if="item.tags?.release_type"
                  class="text-xs px-1.5 py-0.5 rounded"
                  :class="item.tags?.is_uncensored ? 'bg-orange-600 text-white' : 'bg-purple-600 text-white'"
                >
                  {{ item.tags.release_type }}
                </span>
              </div>
            </div>
          </div>
        </div>

        <!-- Pagination -->
        <div v-if="embyStore.totalPages > 1" class="flex justify-center items-center gap-4 mt-6">
          <button
            @click="goPrevPage"
            :disabled="embyStore.currentPage <= 1"
            class="px-4 py-2 rounded bg-gray-700 hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Previous
          </button>
          <span class="text-gray-400">
            Page {{ embyStore.currentPage }} / {{ embyStore.totalPages }}
          </span>
          <button
            @click="goNextPage"
            :disabled="embyStore.currentPage >= embyStore.totalPages"
            class="px-4 py-2 rounded bg-gray-700 hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Next
          </button>
        </div>
      </div>
    </div>

    <!-- Modal -->
    <Teleport to="body">
      <div
        v-if="showModal"
        class="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
        @click.self="closeModal"
      >
        <div class="bg-gray-800 rounded-lg w-full max-w-lg p-6 max-h-[90vh] overflow-y-auto">
          <div v-if="loadingDetail" class="text-gray-400 text-center py-8">Loading...</div>
          <template v-else-if="videoDetail">
            <!-- Header with poster -->
            <div class="flex gap-4 mb-4">
              <div v-if="videoDetail.poster_path" class="w-24 aspect-[2/3] bg-gray-700 rounded flex-shrink-0">
                <img :src="videoDetail.poster_path" class="w-full h-full object-cover rounded" />
              </div>
              <div class="flex-1">
                <h3 class="text-xl font-bold">{{ getDisplayTitle(videoDetail) }}</h3>
                <p v-if="videoDetail.nfo?.originaltitle && videoDetail.nfo.originaltitle !== videoDetail.name" class="text-gray-400 text-sm">
                  {{ videoDetail.nfo.originaltitle }}
                </p>
                <div class="flex flex-wrap gap-2 mt-2">
                  <span v-if="videoDetail.nfo?.year" class="bg-gray-700 px-2 py-0.5 rounded text-xs">{{ videoDetail.nfo.year }}</span>
                  <span v-if="videoDetail.nfo?.rating" class="bg-gray-700 px-2 py-0.5 rounded text-xs">⭐ {{ videoDetail.nfo.rating }}</span>
                  <span v-if="videoDetail.nfo?.director" class="bg-gray-700 px-2 py-0.5 rounded text-xs">{{ videoDetail.nfo.director }}</span>
                </div>
                <div v-if="videoDetail.nfo?.genres?.length" class="flex flex-wrap gap-1 mt-2">
                  <span v-for="genre in videoDetail.nfo.genres.slice(0, 3)" :key="genre" class="bg-blue-600/50 px-2 py-0.5 rounded text-xs">
                    {{ genre }}
                  </span>
                </div>
              </div>
            </div>

            <!-- Plot -->
            <div v-if="videoDetail.nfo?.plot" class="mb-4">
              <p class="text-sm text-gray-300">{{ videoDetail.nfo.plot }}</p>
            </div>

            <!-- File Path -->
            <div class="mb-4">
              <p class="text-sm text-gray-400 mb-1">File Path:</p>
              <p class="text-sm font-mono bg-gray-900 p-2 rounded break-all">{{ videoDetail.file_path || 'N/A' }}</p>
            </div>

            <!-- Settings -->
            <div class="space-y-3 mb-6">
              <div>
                <label class="block text-sm text-gray-400 mb-1">Detection Model</label>
                <select v-model="settings.detection_model" class="w-full bg-gray-700 rounded px-3 py-2">
                  <option value="v4-fast">v4-fast</option>
                  <option value="v4">v4</option>
                  <option value="v3.1-accurate">v3.1-accurate</option>
                </select>
              </div>
              <div>
                <label class="block text-sm text-gray-400 mb-1">Restoration Model</label>
                <select v-model="settings.restoration_model" class="w-full bg-gray-700 rounded px-3 py-2">
                  <option value="basicvsrpp-v1.2">basicvsrpp-v1.2</option>
                  <option value="basicvsrpp-v1">basicvsrpp-v1</option>
                </select>
              </div>
              <div>
                <label class="block text-sm text-gray-400 mb-1">Encoding Preset</label>
                <select v-model="settings.encoding_preset" class="w-full bg-gray-700 rounded px-3 py-2">
                  <option value="hevc-nvidia-gpu-hq">hevc-nvidia-gpu-hq</option>
                  <option value="hevc-nvidia-gpu">hevc-nvidia-gpu</option>
                  <option value="hevc-nvidia">hevc-nvidia</option>
                </select>
              </div>
            </div>

            <!-- Actions -->
            <div class="flex space-x-3">
              <button
                @click="submitJob"
                :disabled="submitting || !videoDetail?.file_path"
                class="flex-1 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 text-white py-2 rounded font-medium transition-colors"
              >
                {{ submitting ? 'Submitting...' : 'Start Restoration' }}
              </button>
              <button
                @click="closeModal"
                class="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded transition-colors"
              >
                Cancel
              </button>
            </div>
          </template>
        </div>
      </div>
    </Teleport>
  </div>
</template>
