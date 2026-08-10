<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

type Job = { id: string; job_type: string; emby_item_name: string; status: string; progress: number; detail?: string }
type Plugin = { id: string; name?: string; enabled: boolean; loaded: boolean }
type Recommendation = { code: string; title: string; cover_url?: string; release_date?: string; score?: number; actors: string[]; categories: string[]; is_today_increment: boolean }
type Page = 'overview' | 'recommendations' | 'tasks' | 'plugins' | 'settings'

const page = ref<Page>('overview')
const loading = ref(true)
const error = ref('')
const healthy = ref(false)
const jobs = ref<Job[]>([])
const plugins = ref<Plugin[]>([])
const settings = ref<Record<string, unknown>>({})
const recommendations = ref<Recommendation[]>([])

const title = computed(() => ({ overview: '概览', recommendations: '推荐中心', tasks: '任务', plugins: '插件', settings: '设置' }[page.value]))
const runningJobs = computed(() => jobs.value.filter((job) => ['queued', 'running', 'blocked'].includes(job.status)))

async function request<T>(path: string): Promise<T> {
  const response = await fetch(path)
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`)
  return response.json() as Promise<T>
}

async function refresh() {
  loading.value = true
  error.value = ''
  try {
    const [health, jobData, pluginData, settingsData, recommendationData] = await Promise.all([
      request<{ status: string }>('/api/health'),
      request<{ jobs: Job[] }>('/api/jobs'),
      request<{ items: Plugin[] }>('/api/plugins'),
      request<Record<string, unknown>>('/api/settings'),
      fetch('/api/plugins/av-recommend/actions/get_recommendations', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ payload: { limit: 24 } }) }).then(async (response) => response.ok ? response.json() as Promise<{ items: Recommendation[] }> : { items: [] }),
    ])
    healthy.value = health.status === 'ok'
    jobs.value = jobData.jobs || []
    plugins.value = pluginData.items || []
    settings.value = settingsData
    recommendations.value = recommendationData.items || []
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '无法连接 NOOR 后端'
    healthy.value = false
  } finally {
    loading.value = false
  }
}

onMounted(refresh)
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand"><span class="brand-mark">N</span><span>NOOR</span></div>
      <nav aria-label="主导航">
        <button :class="{ active: page === 'overview' }" @click="page = 'overview'">概览</button>
        <button :class="{ active: page === 'recommendations' }" @click="page = 'recommendations'">推荐</button>
        <button :class="{ active: page === 'tasks' }" @click="page = 'tasks'">任务 <span v-if="runningJobs.length" class="count">{{ runningJobs.length }}</span></button>
        <button :class="{ active: page === 'plugins' }" @click="page = 'plugins'">插件</button>
        <button :class="{ active: page === 'settings' }" @click="page = 'settings'">设置</button>
      </nav>
      <div class="sidebar-foot"><span :class="['status-dot', { online: healthy }]" />{{ healthy ? '后端已连接' : '后端未连接' }}</div>
    </aside>
    <main>
      <header><div><p class="eyebrow">NOOR RECOVERY</p><h1>{{ title }}</h1></div><button class="icon-button" title="刷新" aria-label="刷新" @click="refresh">↻</button></header>
      <section v-if="error" class="notice error">{{ error }}</section>
      <section v-else-if="loading" class="notice">正在读取 NOOR 状态...</section>
      <template v-else>
        <section v-if="page === 'overview'" class="overview-grid">
          <article class="stat"><span>活动任务</span><strong>{{ runningJobs.length }}</strong></article>
          <article class="stat"><span>全部任务</span><strong>{{ jobs.length }}</strong></article>
          <article class="stat"><span>已加载插件</span><strong>{{ plugins.filter((item) => item.loaded).length }}</strong></article>
          <article class="stat"><span>媒体服务器</span><strong>{{ settings.emby ? '已配置' : '未配置' }}</strong></article>
          <section class="panel wide"><div class="panel-heading"><h2>最近任务</h2><button @click="page = 'tasks'">查看全部</button></div><p v-if="!jobs.length" class="empty">暂无任务</p><div v-for="job in jobs.slice(0, 6)" :key="job.id" class="job-row"><div><b>{{ job.emby_item_name || job.job_type }}</b><small>{{ job.job_type }} · {{ job.detail || job.status }}</small></div><span>{{ job.progress }}%</span></div></section>
        </section>
        <section v-else-if="page === 'tasks'" class="panel"><div class="panel-heading"><h2>任务队列</h2><button @click="refresh">刷新</button></div><p v-if="!jobs.length" class="empty">暂无任务</p><div v-for="job in jobs" :key="job.id" class="job-row"><div><b>{{ job.emby_item_name || job.job_type }}</b><small>{{ job.job_type }} · {{ job.detail || job.status }}</small><div class="progress"><i :style="{ width: `${job.progress}%` }" /></div></div><span :class="['badge', job.status]">{{ job.status }}</span></div></section>
        <section v-else-if="page === 'recommendations'" class="recommendations"><p v-if="!recommendations.length" class="empty">候选池暂无作品</p><article v-for="item in recommendations" :key="item.code" class="work-card"><div class="poster"><img v-if="item.cover_url" :src="item.cover_url" :alt="item.title" loading="lazy" /><span v-if="item.is_today_increment">今日</span></div><div><b>{{ item.code }}</b><p>{{ item.title }}</p><small>{{ item.release_date || '日期未知' }}<template v-if="item.actors.length"> · {{ item.actors.slice(0, 2).join('、') }}</template></small></div></article></section>
        <section v-else-if="page === 'plugins'" class="panel"><div class="panel-heading"><h2>插件</h2><button @click="refresh">重新扫描</button></div><p v-if="!plugins.length" class="empty">尚未恢复插件源码</p><div v-for="plugin in plugins" :key="plugin.id" class="job-row"><div><b>{{ plugin.name || plugin.id }}</b><small>{{ plugin.id }}</small></div><span :class="['badge', plugin.loaded ? 'completed' : 'failed']">{{ plugin.loaded ? '已加载' : '加载失败' }}</span></div></section>
        <section v-else class="panel"><h2>设置</h2><p class="empty">已恢复的设置 API 可用。复杂设置界面将在原组件源码恢复后接回。</p><pre>{{ JSON.stringify(settings, null, 2) }}</pre></section>
      </template>
    </main>
  </div>
</template>

<style>
:root { color: #e9edf2; background: #11151b; font-family: Inter, "Noto Sans SC", system-ui, sans-serif; }
* { box-sizing: border-box; }
body { margin: 0; min-width: 320px; }
button { font: inherit; cursor: pointer; }
.app-shell { min-height: 100vh; display: grid; grid-template-columns: 224px minmax(0, 1fr); background: #11151b; }
.sidebar { background: #171c24; border-right: 1px solid #2b333f; padding: 18px 12px; display: flex; flex-direction: column; gap: 30px; }
.brand { display: flex; align-items: center; gap: 10px; font-weight: 700; letter-spacing: 0; padding: 0 8px; }
.brand-mark { width: 28px; height: 28px; display: grid; place-items: center; background: #168bdf; color: white; font-size: 14px; }
nav { display: grid; gap: 4px; }
nav button { color: #aab4c1; background: transparent; border: 0; text-align: left; padding: 10px 12px; border-radius: 5px; display: flex; justify-content: space-between; }
nav button:hover, nav button.active { color: #fff; background: #26313e; }
.count { color: #b9dfff; font-size: 12px; }
.sidebar-foot { margin-top: auto; color: #8995a5; font-size: 12px; display: flex; align-items: center; gap: 7px; padding: 8px; }
.status-dot { width: 8px; height: 8px; border-radius: 50%; background: #cf5663; }.status-dot.online { background: #45c18a; }
main { min-width: 0; padding: 30px; max-width: 1440px; width: 100%; margin: auto; }
header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 28px; } .eyebrow { color: #6e8095; font-size: 12px; margin: 0 0 5px; } h1, h2, p { margin-top: 0; } h1 { font-size: 26px; margin-bottom: 0; } h2 { font-size: 16px; }
.icon-button { width: 36px; height: 36px; border: 1px solid #3a4655; background: #202833; color: #e9edf2; border-radius: 5px; font-size: 20px; }
.overview-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; }.stat, .panel, .notice { background: #1a212b; border: 1px solid #303a47; border-radius: 6px; }.stat { padding: 18px; display: grid; gap: 8px; }.stat span, small { color: #98a6b7; }.stat strong { font-size: 30px; }.wide { grid-column: 1 / -1; }.panel { padding: 18px; }.panel-heading { display: flex; align-items: center; justify-content: space-between; }.panel-heading button { color: #8fc9f5; border: 0; background: none; }.job-row { display: flex; justify-content: space-between; align-items: center; gap: 14px; padding: 13px 0; border-top: 1px solid #2b3440; }.job-row div { min-width: 0; }.job-row b, .job-row small { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }.job-row small { margin-top: 4px; }.badge { font-size: 12px; padding: 4px 8px; border-radius: 999px; background: #394553; color: #dce5ee; }.badge.completed { background: #173f31; color: #8fe4b8; }.badge.failed { background: #4b2830; color: #ffafb9; }.progress { margin-top: 8px; height: 4px; background: #303a47; width: min(300px, 100%); }.progress i { display: block; height: 100%; background: #168bdf; }.notice { padding: 14px; color: #aeb9c6; }.notice.error { border-color: #80424d; color: #ffbec6; } .empty { color: #93a0b0; padding: 22px 0; } pre { max-height: 60vh; overflow: auto; color: #cdd9e6; font-size: 12px; line-height: 1.55; }
.recommendations { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 14px; }.work-card { min-width: 0; background: #1a212b; border: 1px solid #303a47; border-radius: 6px; overflow: hidden; }.poster { position: relative; aspect-ratio: 2 / 3; background: #242d39; }.poster img { display: block; width: 100%; height: 100%; object-fit: cover; }.poster span { position: absolute; top: 8px; left: 8px; padding: 3px 6px; background: #168bdf; color: white; font-size: 11px; border-radius: 4px; }.work-card > div:last-child { padding: 10px; }.work-card b { color: #a9d5f7; font-size: 12px; }.work-card p { margin: 6px 0; font-size: 13px; line-height: 1.4; min-height: 54px; overflow: hidden; }.work-card small { line-height: 1.4; }
@media (max-width: 760px) { .app-shell { grid-template-columns: 1fr; }.sidebar { position: sticky; top: 0; z-index: 2; padding: 10px; flex-direction: row; align-items: center; gap: 12px; }.brand { padding: 0; }.sidebar nav { display: flex; overflow-x: auto; flex: 1; }.sidebar nav button { white-space: nowrap; }.sidebar-foot { display: none; } main { padding: 18px; }.overview-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }.wide { grid-column: 1 / -1; } }
</style>
