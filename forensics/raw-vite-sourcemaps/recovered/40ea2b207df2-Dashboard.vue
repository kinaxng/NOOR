<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useEmbyStore } from '../stores/emby'
import { useJobsStore } from '../stores/jobs'
import { RouterLink } from 'vue-router'
import BaseIcon from '../components/BaseIcon.vue'
import VuiBadge from '../components/vision/VuiBadge/VuiBadge.vue'
import SystemMetricsCard from '../components/vision/SystemMetricsCard.vue'
import WelcomeMark from '../components/vision/WelcomeMark.vue'
import ActivityCard from '../components/vision/ActivityCard.vue'
import api from '../api'

const embyStore = useEmbyStore()
const jobsStore = useJobsStore()

// Full library tag counts (fetched separately to get accurate totals)
const fullTagCounts = ref({ total: 0, cracked: 0, chinese: 0, leaked: 0, uncensored: 0 })

onMounted(async () => {
  await embyStore.fetchLibraries()
  await jobsStore.fetchJobs()
  // Fetch all items to compute tag counts for entire library
  const params: any = { limit: 200, offset: 0 }
  if (embyStore.enabledLibraryIds.length > 0) {
    params.library_id = embyStore.enabledLibraryIds[0]
  }
  const allItems: any[] = []
  let fetched = 0
  let total = 0
  try {
    do {
      const resp = await api.get('/emby/items', { params: { ...params, offset: fetched } })
      const items: any[] = resp.data.items
      allItems.push(...items)
      total = resp.data.total
      fetched += items.length
    } while (fetched < total && fetched < 2000)
  } catch (e) {
    // ignore counting errors
  }
  fullTagCounts.value = {
    total: allItems.length,
    cracked: allItems.filter(i => i.tags?.is_cracked).length,
    chinese: allItems.filter(i => i.tags?.has_chinese).length,
    leaked: allItems.filter(i => i.tags?.is_leaked || i.tags?.release_type === '流出').length,
    uncensored: allItems.filter(i => i.tags?.is_uncensored || i.tags?.release_type === '无码').length,
  }
})

// Stats (media tag counts from emby store)
const stats = computed(() => embyStore.tagCounts)

// Recent jobs
const recentJobs = computed(() =>
  [...jobsStore.jobs]
    .sort((a, b) => new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime())
    .slice(0, 6)
)

function formatTime(dateStr?: string) {
  if (!dateStr) return '-'
  const d = new Date(dateStr)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return '刚刚'
  if (mins < 60) return `${mins} 分钟前`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours} 小时前`
  return d.toLocaleDateString('zh-CN')
}

function getStatusColor(status: string) {
  const map: Record<string, string> = {
    completed: 'success',
    running: 'primary',
    failed: 'error',
    queued: 'warning',
  }
  return map[status] || 'secondary'
}

function getStatusLabel(status: string) {
  const map: Record<string, string> = {
    completed: '完成',
    running: '运行中',
    failed: '失败',
    queued: '排队',
  }
  return map[status] || status
}
</script>

<template>
  <div class="w-full space-y-6 animate-fade-in">

    <!-- Welcome + Stats Row -->
    <div class="grid grid-cols-1 lg:grid-cols-4 gap-6">
      <!-- Welcome Card -->
      <div class="lg:col-span-2">
        <WelcomeMark username="用户" message="很高兴再次见到你！\n系统运行一切正常。" />
      </div>

      <!-- Stats Card (one big card: top=total, bottom=4 small cards) -->
      <div class="lg:col-span-2 vision-card p-5 flex flex-col">
        <!-- Total count -->
        <div class="text-center mb-4">
          <span class="text-5xl font-bold font-display text-white">{{ stats.total }}</span>
          <span class="block text-xs text-white/40 font-display mt-1">全部</span>
        </div>
        <!-- 4 small stats in a row -->
        <div class="grid grid-cols-4 gap-2">
          <RouterLink
            v-for="stat in [
              { label: '已破', value: stats.cracked, color: 'text-[#0075FF]', filter: 'cracked' },
              { label: '中字', value: stats.chinese, color: 'text-[#01B574]', filter: 'chinese' },
              { label: '流出', value: stats.leaked, color: 'text-[#FFB547]', filter: 'leaked' },
              { label: '无码', value: stats.uncensored, color: 'text-white', filter: 'uncensored' },
            ]"
            :key="stat.label"
            :to="'/library?filter=' + stat.filter"
            class="flex flex-col items-center justify-center py-3 text-center rounded-xl cursor-pointer hover:bg-white/5 transition-colors"
            style="background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.06);"
          >
            <span class="text-lg font-bold font-display" :class="stat.color">{{ stat.value }}</span>
            <span class="text-xs text-white/40 font-display mt-0.5">{{ stat.label }}</span>
          </RouterLink>
        </div>
      </div>
    </div>

    <!-- Activity Card -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div class="lg:col-span-2">
        <!-- GPU Metrics -->
        <SystemMetricsCard
          title="GPU 状态"
          :metrics="[
            { label: 'GPU 利用率', value: '67', unit: '%' },
            { label: '显存使用', value: '8.2', unit: 'GB / 16 GB' },
            { label: 'GPU 温度', value: '62', unit: '°C' },
            { label: '功耗', value: '187', unit: 'W' },
          ]"
          :progress-value="67"
          progress-label="GPU"
          class="mb-6"
        />

        <!-- CPU / Memory Metrics -->
        <SystemMetricsCard
          title="CPU & 内存"
          :metrics="[
            { label: 'CPU 利用率', value: '23', unit: '%' },
            { label: '内存使用', value: '16.3', unit: 'GB / 32 GB' },
            { label: 'CPU 温度', value: '48', unit: '°C' },
            { label: '磁盘读取', value: '127', unit: 'MB/s' },
          ]"
          :progress-value="51"
          progress-label="内存"
          progress-color="#01B574"
        />
      </div>

      <!-- Recent Activity -->
      <div>
        <ActivityCard title="最近任务">
          <template #action>
            <RouterLink to="/jobs" class="text-xs font-medium text-[#0075FF]">
              查看全部 →
            </RouterLink>
          </template>

          <div v-if="recentJobs.length === 0" class="py-8 text-center">
            <p class="text-sm text-white/30">暂无任务记录</p>
          </div>

          <div
            v-for="job in recentJobs"
            :key="job.id"
            class="activity-item"
          >
            <div class="activity-item__icon" :class="`activity-item__icon--${getStatusColor(job.status)}`">
              <BaseIcon
                :name="job.status === 'completed' ? 'check' : job.status === 'failed' ? 'x' : job.status === 'running' ? 'loading' : 'clock'"
                class="w-3.5 h-3.5"
              />
            </div>
            <div class="activity-item__content">
              <p class="activity-item__name">{{ job.emby_item_name || job.input_path?.split('/').pop() || 'Unknown' }}</p>
              <p class="activity-item__meta">{{ job.job_type || 'nfo' }} · {{ formatTime(job.created_at) }}</p>
            </div>
            <VuiBadge
              color="info"
              variant="gradient"
              size="xs"
            >
              {{ getStatusLabel(job.status) }}
            </VuiBadge>
          </div>
        </ActivityCard>
      </div>
    </div>
  </div>
</template>
