<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

type Job = { id: string; job_type: string; emby_item_name: string; status: string; progress: number; detail?: string }
type Plugin = { id: string; name?: string; enabled: boolean; loaded: boolean }
type Recommendation = { code: string; title: string; cover_url?: string; release_date?: string; score?: number; recommendation_score?: number; actors: string[]; categories: string[]; is_today_increment: boolean }
type JavdbItem = { code: string; title: string; cover_url?: string; release_date?: string; actors?: string[]; categories?: string[]; magnets_count?: number }
type JavdbDetail = JavdbItem & { origin_title?: string; duration?: string; maker?: string; series?: string; director?: string; magnets?: Array<{ name?: string; size?: string; size_mb?: number }> }
type Actor = { id: string; name: string; avatar_url?: string; name_zht?: string; other_name?: string }
type Page = 'overview' | 'recommendations' | 'javdb' | 'actors' | 'tasks' | 'plugins' | 'settings'

const page = ref<Page>('overview')
const loading = ref(true)
const error = ref('')
const healthy = ref(false)
const jobs = ref<Job[]>([])
const plugins = ref<Plugin[]>([])
const settings = ref<Record<string, unknown>>({})
const recommendations = ref<Recommendation[]>([])
const recommendationMode = ref<'latest' | 'full'>('latest')
const javdbItems = ref<JavdbItem[]>([])
const javdbQuery = ref('')
const javdbLoading = ref(false)
const javdbDetail = ref<JavdbDetail | null>(null)
const actors = ref<Actor[]>([])
const actorQuery = ref('')
const actorLoading = ref(false)
const selectedActor = ref<Actor | null>(null)
const actorMovies = ref<JavdbItem[]>([])

const title = computed(() => ({ overview: '概览', recommendations: '推荐中心', javdb: 'JavDB', actors: '演员', tasks: '任务', plugins: '插件', settings: '设置' }[page.value]))
const runningJobs = computed(() => jobs.value.filter((job) => ['queued', 'running', 'blocked'].includes(job.status)))
const filteredActors = computed(() => {
  const query = actorQuery.value.trim().toLowerCase()
  if (!query) return actors.value
  return actors.value.filter((actor) => [actor.name, actor.name_zht, actor.other_name].join(' ').toLowerCase().includes(query))
})

async function request<T>(path: string): Promise<T> {
  const response = await fetch(path)
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`)
  return response.json() as Promise<T>
}

async function pluginAction<T>(plugin: string, action: string, payload: Record<string, unknown> = {}): Promise<T> {
  const response = await fetch(`/api/plugins/${plugin}/actions/${action}`, {
    method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ payload }),
  })
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`)
  return response.json() as Promise<T>
}

async function loadRecommendations() {
  const data = await pluginAction<{ items: Recommendation[] }>('av-recommend', 'recommendations', { limit: 48, source_mode: recommendationMode.value })
  recommendations.value = data.items || []
}

async function setRecommendationMode(mode: 'latest' | 'full') {
  recommendationMode.value = mode
  loading.value = true
  error.value = ''
  try { await loadRecommendations() } catch (cause) { error.value = cause instanceof Error ? cause.message : '推荐加载失败' } finally { loading.value = false }
}

async function feedback(item: Recommendation, kind: 'like' | 'dislike' | 'ignore') {
  try {
    await pluginAction('av-recommend', 'feedback', { kind, code: item.code, actors: item.actors, categories: item.categories })
    await loadRecommendations()
  } catch (cause) { error.value = cause instanceof Error ? cause.message : '保存反馈失败' }
}

async function loadJavdb() {
  javdbLoading.value = true
  error.value = ''
  try {
    const query = javdbQuery.value.trim()
    const result = query
      ? await pluginAction<{ items: JavdbItem[] }>('javdb', 'search', { q: query, page: 1, limit: 30 })
      : await pluginAction<{ items: JavdbItem[] }>('javdb', 'latest', { page: 1, limit: 30, type: 'all', filter_by: 'magnets', sort_by: 'update' })
    javdbItems.value = result.items || []
  } catch (cause) { error.value = cause instanceof Error ? cause.message : 'JavDB 加载失败' } finally { javdbLoading.value = false }
}

async function openJavdbDetail(item: JavdbItem) {
  try {
    const result = await pluginAction<{ data: JavdbDetail }>('javdb', 'video', { code: item.code })
    javdbDetail.value = result.data || null
  } catch (cause) { error.value = cause instanceof Error ? cause.message : '作品详情加载失败' }
}

async function loadActors() {
  actorLoading.value = true
  error.value = ''
  try {
    const result = await pluginAction<{ items: Actor[] }>('javdb', 'actors', { type: 0 })
    actors.value = result.items || []
  } catch (cause) { error.value = cause instanceof Error ? cause.message : '演员列表加载失败' } finally { actorLoading.value = false }
}

async function openActor(actor: Actor) {
  selectedActor.value = actor
  actorMovies.value = []
  try {
    const result = await pluginAction<{ items: JavdbItem[] }>('javdb', 'actor_movies', { actor_id: actor.id, page: 1, limit: 24 })
    actorMovies.value = result.items || []
  } catch (cause) { error.value = cause instanceof Error ? cause.message : '演员作品加载失败' }
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
      pluginAction<{ items: Recommendation[] }>('av-recommend', 'recommendations', { limit: 48, source_mode: recommendationMode.value }),
    ])
    healthy.value = health.status === 'ok'
    jobs.value = jobData.jobs || []
    plugins.value = pluginData.items || []
    settings.value = settingsData
    recommendations.value = recommendationData.items || []
    await loadJavdb()
    await loadActors()
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
        <button :class="{ active: page === 'javdb' }" @click="page = 'javdb'; loadJavdb()">JavDB</button>
        <button :class="{ active: page === 'actors' }" @click="page = 'actors'; loadActors()">演员</button>
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
        <section v-else-if="page === 'recommendations'"><div class="panel-heading recommendation-controls"><div class="segmented" aria-label="推荐范围"><button :class="{ active: recommendationMode === 'latest' }" @click="setRecommendationMode('latest')">最新推荐</button><button :class="{ active: recommendationMode === 'full' }" @click="setRecommendationMode('full')">完整推荐</button></div><span class="muted">{{ recommendations.length }} 部作品</span></div><div class="recommendations"><p v-if="!recommendations.length" class="empty">候选池暂无作品</p><article v-for="item in recommendations" :key="item.code" class="work-card"><div class="poster"><img v-if="item.cover_url" :src="item.cover_url" :alt="item.title" loading="lazy" /><span v-if="item.is_today_increment">今日</span></div><div><div class="card-title"><b>{{ item.code }}</b><strong>{{ item.recommendation_score ?? item.score ?? 0 }}</strong></div><p>{{ item.title }}</p><small>{{ item.release_date || '日期未知' }}<template v-if="item.actors.length"> · {{ item.actors.slice(0, 2).join('、') }}</template></small><div class="card-actions"><button title="喜欢" aria-label="喜欢" @click="feedback(item, 'like')">+</button><button title="不喜欢" aria-label="不喜欢" @click="feedback(item, 'dislike')">-</button><button title="忽略" aria-label="忽略" @click="feedback(item, 'ignore')">x</button></div></div></article></div></section>
        <section v-else-if="page === 'javdb'"><form class="javdb-search" @submit.prevent="loadJavdb"><input v-model="javdbQuery" aria-label="搜索作品" placeholder="番号或标题" /><button type="submit">搜索</button><button type="button" title="恢复最近更新" @click="javdbQuery = ''; loadJavdb()">最新</button></form><p v-if="javdbLoading" class="empty">正在读取 JavDB...</p><div v-else class="recommendations"><p v-if="!javdbItems.length" class="empty">没有找到作品</p><article v-for="item in javdbItems" :key="item.code" class="work-card clickable" @click="openJavdbDetail(item)"><div class="poster"><img v-if="item.cover_url" :src="item.cover_url" :alt="item.title" loading="lazy" /></div><div><div class="card-title"><b>{{ item.code }}</b><strong v-if="item.magnets_count">{{ item.magnets_count }} 磁链</strong></div><p>{{ item.title }}</p><small>{{ item.release_date || '日期未知' }}<template v-if="item.actors?.length"> · {{ item.actors.slice(0, 2).join('、') }}</template></small></div></article></div><section v-if="javdbDetail" class="detail-panel"><div class="panel-heading"><div><h2>{{ javdbDetail.code }}</h2><small>{{ javdbDetail.title }}</small></div><button title="关闭详情" aria-label="关闭详情" @click="javdbDetail = null">x</button></div><img v-if="javdbDetail.cover_url" class="detail-cover" :src="javdbDetail.cover_url" :alt="javdbDetail.title" /><p v-if="javdbDetail.origin_title">{{ javdbDetail.origin_title }}</p><p><b>演员：</b>{{ javdbDetail.actors?.join('、') || '未知' }}</p><p><b>类型：</b>{{ javdbDetail.categories?.join('、') || '未知' }}</p><p><b>磁链：</b>{{ javdbDetail.magnets?.length || 0 }}</p></section></section>
        <section v-else-if="page === 'actors'"><div class="javdb-search"><input v-model="actorQuery" aria-label="筛选演员" placeholder="筛选演员名称" /><button type="button" title="刷新演员列表" @click="loadActors()">刷新</button></div><p v-if="actorLoading" class="empty">正在读取演员列表...</p><div v-else class="actor-grid"><button v-for="actor in filteredActors" :key="actor.id" class="actor-card" @click="openActor(actor)"><img v-if="actor.avatar_url" :src="actor.avatar_url" :alt="actor.name" loading="lazy" /><span v-else class="actor-placeholder">{{ actor.name.slice(0, 1) }}</span><b>{{ actor.name }}</b><small>{{ actor.name_zht || actor.other_name }}</small></button></div><section v-if="selectedActor" class="detail-panel"><div class="panel-heading"><div class="actor-heading"><img v-if="selectedActor.avatar_url" :src="selectedActor.avatar_url" :alt="selectedActor.name" /><div><h2>{{ selectedActor.name }}</h2><small>{{ selectedActor.name_zht || selectedActor.other_name }}</small></div></div><button title="关闭演员详情" aria-label="关闭演员详情" @click="selectedActor = null">x</button></div><div class="recommendations compact"><article v-for="item in actorMovies" :key="item.code" class="work-card clickable" @click="openJavdbDetail(item)"><div class="poster"><img v-if="item.cover_url" :src="item.cover_url" :alt="item.title" loading="lazy" /></div><div><b>{{ item.code }}</b><p>{{ item.title }}</p></div></article></div></section></section>
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
.recommendation-controls { margin-bottom: 14px; }.segmented { display: inline-flex; border: 1px solid #3a4655; border-radius: 5px; overflow: hidden; }.segmented button { border: 0; background: transparent; color: #aab4c1; padding: 7px 11px; }.segmented button.active { background: #26394c; color: #fff; }.muted { color: #98a6b7; font-size: 12px; }.javdb-search { display: flex; gap: 8px; margin-bottom: 14px; }.javdb-search input { flex: 1; min-width: 0; border: 1px solid #3a4655; border-radius: 5px; background: #171c24; color: #e9edf2; padding: 8px 10px; }.javdb-search button { border: 1px solid #3a4655; border-radius: 5px; background: #202833; color: #dce5ee; padding: 7px 11px; }.recommendations { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 14px; }.work-card { min-width: 0; background: #1a212b; border: 1px solid #303a47; border-radius: 6px; overflow: hidden; }.work-card.clickable { cursor: pointer; }.poster { position: relative; aspect-ratio: 2 / 3; background: #242d39; }.poster img { display: block; width: 100%; height: 100%; object-fit: cover; }.poster span { position: absolute; top: 8px; left: 8px; padding: 3px 6px; background: #168bdf; color: white; font-size: 11px; border-radius: 4px; }.work-card > div:last-child { padding: 10px; }.card-title { display: flex; align-items: center; justify-content: space-between; gap: 8px; }.work-card b { color: #a9d5f7; font-size: 12px; }.card-title strong { color: #8fe4b8; font-size: 14px; }.work-card p { margin: 6px 0; font-size: 13px; line-height: 1.4; min-height: 54px; overflow: hidden; }.work-card small { line-height: 1.4; }.card-actions { display: flex; justify-content: flex-end; gap: 5px; margin-top: 10px; }.card-actions button { width: 25px; height: 25px; border: 1px solid #3a4655; background: #202833; color: #c9d3dd; border-radius: 4px; }.actor-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(116px, 1fr)); gap: 10px; }.actor-card { min-width: 0; border: 1px solid #303a47; border-radius: 6px; padding: 8px; background: #1a212b; color: #dce5ee; text-align: left; display: grid; gap: 6px; }.actor-card img, .actor-placeholder { width: 100%; aspect-ratio: 1; object-fit: cover; background: #242d39; display: grid; place-items: center; color: #98a6b7; }.actor-card b, .actor-card small { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }.actor-card small { color: #98a6b7; }.detail-panel { margin-top: 18px; padding: 18px; background: #1a212b; border: 1px solid #303a47; border-radius: 6px; overflow: auto; }.detail-panel .panel-heading button { width: 30px; height: 30px; border: 1px solid #3a4655; background: #202833; color: #dce5ee; border-radius: 4px; }.detail-cover { width: min(240px, 100%); margin: 12px 0; display: block; }.actor-heading { display: flex; align-items: center; gap: 12px; }.actor-heading img { width: 64px; height: 64px; object-fit: cover; }.compact { margin-top: 14px; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); }
@media (max-width: 760px) { .app-shell { grid-template-columns: 1fr; }.sidebar { position: sticky; top: 0; z-index: 2; padding: 10px; flex-direction: row; align-items: center; gap: 12px; }.brand { padding: 0; }.sidebar nav { display: flex; overflow-x: auto; flex: 1; }.sidebar nav button { white-space: nowrap; }.sidebar-foot { display: none; } main { padding: 18px; }.overview-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }.wide { grid-column: 1 / -1; } }
</style>
