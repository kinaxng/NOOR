<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useMediaStore } from '../stores/media'
import NoorButton from '../noor-kit/NoorButton.vue'
import NoorBadge from '../noor-kit/NoorBadge.vue'
import NoorPagination from '../noor-kit/NoorPagination.vue'
import NoorState from '../noor-kit/NoorState.vue'

const media = useMediaStore()
const searchText = ref('')

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
        <select v-model="media.selectedLibraryId" class="input" @change="media.selectLibrary(media.selectedLibraryId)">
          <option value="">全部媒体库</option>
          <option v-for="library in media.libraries" :key="library.id" :value="library.id">{{ library.name }}</option>
        </select>
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
            <NoorButton class="detail-close" @click="media.closeDetail()">关闭</NoorButton>
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
              <button type="button" class="version-row is-active">
                <strong>{{ media.selectedItem.file_path || media.selectedItem.name }}</strong>
              </button>
              <button v-for="sibling in media.selectedItem.siblings || []" :key="sibling.id || sibling.file_path" type="button" class="version-row">
                <strong>{{ sibling.file_path || sibling.name || sibling.label }}</strong>
              </button>
            </section>
          </div>
        </template>
      </aside>
    </div>
  </section>
</template>
