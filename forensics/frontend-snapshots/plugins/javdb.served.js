function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>'\"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]))
}

function el(tag, cls = '', text = '') {
  const n = document.createElement(tag)
  if (cls) n.className = cls
  if (text) n.textContent = text
  return n
}

function fmtMin(v) {
  const n = Number(v || 0)
  return n ? `${n} 分钟` : ''
}

function titleOf(item) {
  const code = String(item?.number || item?.code || '').trim()
  const title = String(item?.title || item?.origin_title || '').trim()
  return code ? `[${code}] ${title}` : title
}

function titleCandidates(item) {
  const code = String(item?.number || item?.code || '').trim()
  const main = String(item?.title || '').trim()
  const smart = String(item?.display_title || item?.smart_title || (code ? `[${code}] ${main}` : main)).trim()
  return [
    { key: 'smart', label: '智能优选', value: smart, hint: '优先使用番号+标题。' },
    { key: 'main', label: '主标题', value: main, hint: '作品原始主标题。' },
    { key: 'code', label: '编号', value: code, hint: '仅使用番号。' },
  ].filter(opt => opt.value)
}

function classifyCategory(item) {
  const code = String(item?.number || item?.code || '').toUpperCase()
  const title = String(item?.title || '').toUpperCase()
  const uncensoredPrefixes = ['HEYZO', 'CARIB', 'CARIBBEAN', '1PONDO', '10MUSUME', 'PACOPACOMAMA', 'FC2-PPV', 'FC2PPV']
  if (code.startsWith('FC2') || title.includes('FC2')) return 'FC2'
  if (uncensoredPrefixes.some(prefix => code.startsWith(prefix) || title.includes(prefix))) return '无码'
  if (code.includes('TUSHY') || code.includes('BRAZZERS') || code.includes('VIXEN') || code.includes('BLACKED') || code.includes('NUBILE') || code.includes('MOFOS')) return '欧美'
  return '有码'
}

function magnetLabel(item) {
  const count = Number(item?.magnets_count || 0)
  return count > 0 ? `${count} 磁链` : ''
}

function textHasKeywords(value, keywords) {
  if (value == null) return false
  if (typeof value === 'string') {
    const text = value.toLowerCase()
    return keywords.some(keyword => text.includes(keyword))
  }
  if (Array.isArray(value)) return value.some(entry => textHasKeywords(entry, keywords))
  if (typeof value === 'object') return Object.values(value).some(entry => textHasKeywords(entry, keywords))
  return textHasKeywords(String(value), keywords)
}

function detectCnsub(detail) {
  const keywords = ['中字', '字幕', '中文', '中文字幕', 'chs', 'cht']
  return textHasKeywords(detail?.categories, keywords)
    || textHasKeywords(detail?.magnets, keywords)
    || textHasKeywords(detail?.title, keywords)
}

function detectCracked(detail) {
  const keywords = ['破解', '破解版', '无码破解', 'uncensored leak']
  return textHasKeywords(detail?.categories, keywords)
    || textHasKeywords(detail?.magnets, keywords)
    || textHasKeywords(detail?.title, keywords)
}

function formatReleaseDate(value) {
  if (!value) return ''
  const text = String(value)
  return text.includes('T') ? text.slice(0, 10) : text
}

function numericScore(value) {
  const n = Number(value || 0)
  return Number.isFinite(n) && n > 0 ? n : 0
}

function detailCode(video) {
  return String(video?.code || video?.number || '').trim()
}

function detailTitle(video) {
  const code = detailCode(video)
  const title = String(video?.title || video?.origin_title || '').trim()
  return code && title ? `${code} ${title}` : code || title || '未知作品'
}

function normalizeCode(value) {
  return String(value || '').toUpperCase().replace(/[^A-Z0-9]/g, '')
}


function magnetTone(tag) {
  const text = String(tag || '')
  if (/中字|字幕|中文/i.test(text)) return 'success'
  if (/破解|流出/i.test(text)) return 'danger'
  if (/高清|HD|4K/i.test(text)) return 'info'
  return 'neutral'
}

function resourceProviderOrder(resource) {
  const provider = String(resource?.provider || '').trim()
  if (provider === 'avdb') return 0
  if (provider === 'mteam-plugin') return 1
  if (provider === 'javdb') return 2
  return 9
}

function compactResourceSubtitle(resource) {
  const raw = String(resource?.subtitle || '').trim()
  if (!raw) return ''
  const parts = raw.split('·').map(part => part.trim()).filter(Boolean)
  if (!parts.length) return raw
  const compact = []
  for (const part of parts) {
    if (compact.some(existing => existing === part)) continue
    if (String(resource?.provider || '') === 'avdb' && compact.some(existing => existing.includes(part))) continue
    compact.push(part)
  }
  return compact.join(' · ')
}

function resourceBadgeModels(resource) {
  const badges = []
  if (resource?.features?.has_subtitle) badges.push({ label: '中字', tone: 'success' })
  if (resource?.features?.is_cracked) badges.push({ label: '破解', tone: 'danger' })
  if (resource?.features?.is_private_tracker) badges.push({ label: 'PT', tone: 'warning' })
  return badges
}

function resourceIdentity(resource) {
  const provider = String(resource?.provider || resource?.provider_label || 'other').trim().toLowerCase()
  const url = String(resource?.url || resource?.magnet || resource?.download_url || '').trim().toLowerCase()
  if (url) return `${provider}:url:${url}`
  const id = String(resource?.id || '').trim().toLowerCase()
  if (id) return `${provider}:id:${id}`
  return `${provider}:title:${String(resource?.title || '').trim().toLowerCase()}:${String(resource?.subtitle || '').trim().toLowerCase()}`
}

function mergeResources(primary, fallback) {
  const out = []
  const seen = new Set()
  ;[...(Array.isArray(primary) ? primary : []), ...(Array.isArray(fallback) ? fallback : [])].forEach(resource => {
    const key = resourceIdentity(resource)
    if (seen.has(key)) return
    seen.add(key)
    out.push(resource)
  })
  return out
}

function isPluginUnmountError(error) {
  const name = String(error?.name || '')
  const code = String(error?.code || '')
  const message = String(error?.response?.data?.detail || error?.message || error || '')
  return name === 'AbortError'
    || name === 'CanceledError'
    || code === 'ERR_CANCELED'
    || /unmounted|aborted|canceled|cancelled/i.test(message)
}

export async function mount(root, sdk) {
  const state = {
    tab: 'latest',
    latestSelectedFilters: ['magnets'],
    latestType: 'all',
    latestSort: 'update',
    videosFilter: '',
    videosActorId: '',
    videosCategoryIds: [],
    videosMinScore: '',
    videosSort: 'created',
    videosOrder: 'desc',
    videoCategories: [],
    videoActors: [],
    videoActorsLoaded: false,
    videoActorsLoading: false,
    videoCategoriesLoaded: false,
    videoCategoriesLoading: false,
    rankingMode: 'top250',
    rankingType: 0,
    rankingPeriod: 'daily',
    rankingSelectedFilters: [],
    top250Year: '',
    relation: null,
    relationActorSelectedFilters: [],
    relationActorSingleFilter: false,
    relationActorYear: '',
    relationActorSort: 'release_desc',
    page: 1,
    limit: 48,
    total: 0,
    items: [],
    loading: false,
    hasLoadedOnce: false,
    loadError: '',
    activePanel: null,
    subscriptionMap: new Map(),
  }
  const chooserState = {
    modal: null,
    search: '',
  }

  let tabControl = null
  let resizeTimer = null
  let loadSeq = 0
  const initialCode = new URLSearchParams(window.location.search).get('code')?.trim() || ''
  let initialCodeOpened = false

  root.innerHTML = ''
  const page = el('div', 'javdb-page')
    modal: null,
    search: '',
  }

  let tabControl = null
  let resizeTimer = null
  let loadSeq = 0
  const initialCode = new URLSearchParams(window.location.search).get('code')?.trim() || ''
  let initialCodeOpened = false
  let syncingRoute = false

  root.innerHTML = ''
  const page = el('div', 'javdb-page')
  const header = el('div', 'javdb-header-wrap')
  const tabsWrap = el('div', 'javdb-tabs-wrap')
  const panelWrap = el('div', 'javdb-panel-wrap')
  const loadingStatus = el('div', 'javdb-loading-status')
  const filtersWrap = el('div', 'javdb-filters-wrap')
  const grid = el('div', 'javdb-grid')
  const pager = el('div', 'javdb-pager')
  header.append(tabsWrap, loadingStatus, panelWrap, filtersWrap)
  page.append(header, grid, pager)
  root.appendChild(page)

  const tabDefs = [
    { value: 'latest', label: '最近更新', path: 'latest' },
    { value: 'rankings', label: '榜单', path: 'rankings' },
    { value: 'videos', label: '查看记录', path: 'videos' },
  ]


  function currentRouteTab() {
    const subPath = String(sdk.route?.subPath || '').replace(/^\/+|\/+$/g, '')
    const first = subPath.split('/').filter(Boolean)[0]
    return tabDefs.some(tab => tab.value === first || tab.path === first) ? first : ''
  }

  function currentRouteRelation() {
    const parts = String(sdk.route?.subPath || '').replace(/^\/+|\/+$/g, '').split('/').filter(Boolean)
    const relType = parts[0] || ''
    if (!['actor', 'series', 'director', 'maker', 'publisher', 'category', 'list'].includes(relType)) return null
    const relId = decodeRoutePart(parts[1] || '')
    if (!relId) return null
    const label = decodeRoutePart(parts.slice(2).join('/') || relId)
    return { relType, relId, label }
  }

  function relationPath(relType, relId, label) {
    return [relType, encodeRoutePart(relId), encodeRoutePart(label || relId)].filter(Boolean).join('/')
  }

  const initialTab = currentRouteTab()
  if (initialTab) state.tab = initialTab
  const initialRelation = currentRouteRelation()
  if (initialRelation) {
    state.tab = initialTab || 'rankings'
    state.relation = initialRelation
  }

  const latestFilters = [
    ['magnets', '有磁链'],
    ['cnsub', '中字'],
    ['cracked', '破解'],
  ]
  const latestTypes = [
    ['all', '全部'],
    ['0', '有码'],
    ['1', '无码'],
    ['2', '欧美'],
    ['3', 'FC2'],
    ['4', '动漫'],
  ]
  const latestSorts = [
    ['update', '更新时间'],
    ['release', '上映日期'],
  ]
  const rankingModes = [
    ['top250', 'TOP250'],
    ['daily', '日榜'],
    ['weekly', '周榜'],
    ['monthly', '月榜'],
    ['actors', '演员榜'],
  ]
  const rankingTypes = [
    [0, '有码'],
    [1, '无码'],
    [2, '欧美'],
    [3, 'FC2'],
  ]
  const rankingPeriods = [
    ['daily', '日榜'],
    ['weekly', '周榜'],
    ['monthly', '月榜'],
  ]
  const rankingFilters = [
    ['cnsub', '中字'],
    ['cracked', '破解'],
  ]
  const relationActorBadgeFilters = [
    ['magnets', '有磁链'],
    ['cnsub', '字幕'],
    ['cracked', '破解'],
  ]
  const relationActorSortOptions = [
    { label: '最新优先', value: 'release_desc' },
    { label: '最早优先', value: 'release_asc' },
    { label: '磁链数', value: 'magnets_desc' },
    { label: '标题', value: 'title_asc' },
  ]
  const videosMinScoreOptions = [
    { label: '全部评分', value: '' },
    { label: '4 分及以上', value: '4' },
    { label: '5 分及以上', value: '5' },
    { label: '6 分及以上', value: '6' },
    { label: '7 分及以上', value: '7' },
    { label: '8 分及以上', value: '8' },
    { label: '9 分及以上', value: '9' },
  ]
  const videosSortOptions = [
    { label: '入库时间', value: 'created' },
    { label: '上映时间', value: 'date' },
    { label: '更新时间', value: 'updated' },
  ]
  const videosFilterOptions = [
    ['all', '全部'],
    ['m', '可下载'],
    ['c', '字幕'],
    ['n', '无资源'],
  ]

  function isActorRankingFrame() {
    return state.tab === 'rankings' && state.rankingMode === 'actors' && !state.relation
  }

  function rerenderCurrentList() {
    renderFilters()
    renderGrid()
    renderPager()
  }

  function usesRemotePaging() {
    if (state.relation) return true
    if (state.tab === 'latest') return true
    if (state.tab === 'videos') return true
    if (state.tab === 'rankings') return state.rankingMode === 'top250'
    return false
  }

  function latestRemoteFilter() {
    if (state.latestSelectedFilters.includes('cracked')) return 'cracked'
    if (state.latestSelectedFilters.includes('cnsub')) return 'cnsub'
    if (state.latestSelectedFilters.includes('magnets')) return 'magnets'
    return 'all'
  }

  function isLatestRemoteBuffered() {
    return state.tab === 'latest' && state.latestSelectedFilters.length > 0
  }

  function estimatePageSize() {
    if (isActorRankingFrame()) {
    state.videosOrder = 'desc'
    state.rankingMode = 'top250'
    state.rankingType = 0
    state.rankingPeriod = 'daily'
    state.rankingSelectedFilters = []
    state.top250Year = ''
    state.relation = null
    if (next === 'videos') void ensureVideoCategories()
    if (next === 'videos') void ensureVideoActors()
    loadData()
  }

  function setRelation(relType, relId, label) {
    state.relation = { relType, relId, label }
    state.relationActorSelectedFilters = []
    state.relationActorSingleFilter = false
    state.relationActorYear = ''
    state.relationActorSort = 'release_desc'
    state.page = 1
    loadData()
  }

  function actorRelationYears() {
    const years = new Set()
    for (const item of state.items) {
      const year = String(item?.release_date || '').slice(0, 4)
      if (year) years.add(year)
    }
    return [...years].sort((a, b) => Number(b) - Number(a))
  }

  function normalizeCategoryOptions(items) {
    return (Array.isArray(items) ? items : [])
      .map(item => {
        const value = String(item?.id ?? item?.value ?? item?.category_id ?? item?.external_id ?? '').trim()
        const label = String(item?.name ?? item?.label ?? item?.title ?? item?.value ?? '').trim()
        return value && label ? { value, label } : null
      })
      .filter(Boolean)
  }

  async function loadSubscriptionStates() {
    try {
      const res = await sdk.api.post('/plugins/subscription-core/actions/overview', { payload: {} })
      const map = new Map()
      for (const item of (res.data?.items || [])) {
        if (!item || item.status === 'deleted') continue
        const key = normalizeCode(item.code)
        if (key) map.set(key, item)
      }
      state.subscriptionMap = map
    } catch {
      state.subscriptionMap = new Map()
    }
  }

  function subscriptionStateFor(videoData) {
    const code = detailCode(videoData)
    if (!code) return null
    return state.subscriptionMap.get(normalizeCode(code)) || null
  }

  function subscriptionActionModel(videoData) {
    const sub = subscriptionStateFor(videoData)
    const isInLibrary = !!videoData?.library?.in_library
    if (sub) {
      const running = ['matched', 'submitted', 'waiting_quota', 'submit_failed'].includes(String(sub.status || ''))
      if (sub.type === 'upgrade') return { label: running ? '洗版中' : '洗版中', state: 'upgrade-active', disabled: true }
      return { label: running ? '已订阅' : '已订阅', state: 'subscribed', disabled: true }
    }
    return isInLibrary
      ? { label: '洗版', state: 'upgrade', disabled: false }
      : { label: '订阅', state: 'subscribe', disabled: false }
  }

  async function ensureVideoCategories() {
    if (state.videoCategoriesLoaded || state.videoCategoriesLoading) return
    state.videoCategoriesLoading = true
    try {
      const res = await sdk.api.post('/plugins/javdb/actions/categories', { payload: {} })
      state.videoCategories = normalizeCategoryOptions(res.data?.items || [])
      state.videoCategoriesLoaded = true
      renderFilters()
    } catch {
      state.videoCategories = []
      state.videoCategoriesLoaded = false
    } finally {
      state.videoCategoriesLoading = false
    }
  }

  async function ensureVideoActors() {
    if (state.videoActorsLoaded || state.videoActorsLoading) return
    state.videoActorsLoading = true
    try {
      const res = await sdk.api.post('/plugins/javdb/actions/actor_options', { payload: {} })
      state.videoActors = (Array.isArray(res.data?.items) ? res.data.items : [])
        .map(item => {
          const value = String(item?.external_id ?? item?.id ?? '').trim()
          const label = String(item?.name ?? '').trim()
          return value && label ? { value, label } : null
        })
        .filter(Boolean)
      state.videoActorsLoaded = true
      renderFilters()
    } catch {
      state.videoActors = []
      state.videoActorsLoaded = false
    } finally {
        const key = normalizeCode(item.code)
        if (key) map.set(key, item)
      }
      state.subscriptionMap = map
    } catch {
      state.subscriptionMap = new Map()
    }
  }

  function subscriptionStateFor(videoData) {
    const code = detailCode(videoData)
    if (!code) return null
    return state.subscriptionMap.get(normalizeCode(code)) || null
  }

  function subscriptionActionModel(videoData) {
    const sub = subscriptionStateFor(videoData)
    const isInLibrary = !!videoData?.library?.in_library
    if (sub) {
      const running = ['matched', 'submitted', 'waiting_quota', 'submit_failed'].includes(String(sub.status || ''))
      if (sub.type === 'upgrade') return { label: running ? '洗版中' : '洗版中', state: 'upgrade-active', disabled: true }
      return { label: running ? '已订阅' : '已订阅', state: 'subscribed', disabled: true }
    }
    return isInLibrary
      ? { label: '洗版', state: 'upgrade', disabled: false }
      : { label: '订阅', state: 'subscribe', disabled: false }
  }

  async function ensureVideoCategories() {
    if (state.videoCategoriesLoaded || state.videoCategoriesLoading) return
    state.videoCategoriesLoading = true
    try {
      const res = await sdk.api.post('/plugins/javdb/actions/categories', { payload: {} })
      state.videoCategories = normalizeCategoryOptions(res.data?.items || [])
      state.videoCategoriesLoaded = true
      renderFilters()
    } catch {
      state.videoCategories = []
      state.videoCategoriesLoaded = false
    } finally {
      state.videoCategoriesLoading = false
    }
  }

  async function ensureVideoActors() {
    if (state.videoActorsLoaded || state.videoActorsLoading) return
    state.videoActorsLoading = true
    try {
      const res = await sdk.api.post('/plugins/javdb/actions/actor_options', { payload: {} })
      state.videoActors = (Array.isArray(res.data?.items) ? res.data.items : [])
        .map(item => {
          const value = String(item?.external_id ?? item?.id ?? '').trim()
          const label = String(item?.name ?? '').trim()
          return value && label ? { value, label } : null
        })
        .filter(Boolean)
      state.videoActorsLoaded = true
      renderFilters()
    } catch {
      state.videoActors = []
      state.videoActorsLoaded = false
    } finally {
      state.videoActorsLoading = false
    }
  }

  function filteredItems() {
    if (state.relation?.relType === 'actor') {
      const list = state.items.filter(item => {
        if (state.relationActorSelectedFilters.includes('magnets') && Number(item?.magnets_count || 0) <= 0) return false
        if (state.relationActorSelectedFilters.includes('cnsub') && !(item?.has_cnsub || item?.play_subtitle)) return false
        if (state.relationActorSelectedFilters.includes('cracked') && !item?.is_cracked) return false
        if (state.relationActorSingleFilter && Number(item?.actor_count || 0) > 1) return false
        if (state.relationActorYear && String(item?.release_date || '').slice(0, 4) !== state.relationActorYear) return false
        return true
      })
      const sorted = [...list]
      if (state.relationActorSort === 'release_desc') sorted.sort((a, b) => String(b.release_date || '').localeCompare(String(a.release_date || '')))
      else if (state.relationActorSort === 'release_asc') sorted.sort((a, b) => String(a.release_date || '').localeCompare(String(b.release_date || '')))
      else if (state.relationActorSort === 'magnets_desc') sorted.sort((a, b) => Number(b.magnets_count || 0) - Number(a.magnets_count || 0))
      else if (state.relationActorSort === 'title_asc') sorted.sort((a, b) => titleOf(a).localeCompare(titleOf(b), 'zh-CN'))
      return sorted
    }
    if (state.tab === 'latest') {
      return state.items.filter(item => {
        if (state.latestSelectedFilters.includes('magnets') && Number(item?.magnets_count || 0) <= 0) return false
        if (state.latestSelectedFilters.includes('cnsub') && !(item?.has_cnsub || item?.play_subtitle)) return false
        if (state.latestSelectedFilters.includes('cracked') && !item?.is_cracked) return false
        return true
      })
    }
    return state.items
  }

  async function enrichWorkItems(items) {
    const targets = (items || []).filter(item => item && item.code && !item.__detailEnriched)
    if (!targets.length) return
    const queue = targets.slice(0, state.relation?.relType === 'actor' ? 120 : 80)
    const concurrency = 8
    let index = 0
    async function worker() {
      while (index < queue.length) {
        const current = queue[index++]
        try {
          const res = await sdk.api.post('/plugins/javdb/actions/video', { payload: { code: current.code } })
          const detail = res.data?.data || {}
          current.actor_count = Array.isArray(detail.actors) ? detail.actors.length : Number(current.actor_count || 0)
          current.has_cnsub = !!(current.has_cnsub || current.play_subtitle || detectCnsub(detail))
          current.is_cracked = !!(current.is_cracked || detectCracked(detail))
          if (detail.library && typeof detail.library === 'object') current.library = detail.library
          current.__detailEnriched = true
        } catch {
          current.__detailEnriched = true
          if (current.actor_count == null) current.actor_count = 0
        }
      }
    }
    await Promise.all(Array.from({ length: concurrency }, () => worker()))
  }

  function renderTabs() {
    if (!tabControl) {
      tabControl = sdk.ui.tabs({
        tabs: tabDefs,
        value: state.tab,
        route: {
          mode: 'path',
          defaultReplace: false,
          subPath: () => sdk.route?.subPath || '',
          push: path => sdk.route?.push?.(path),
        const text = [item.name, item.name_zht, item.other_name, item.id, item.external_id].filter(Boolean).join(' ').toLowerCase()
        return text.includes(keyword)
      })
    }
    return state.items
  }

  async function enrichWorkItems(items) {
    const targets = (items || []).filter(item => item && item.code && !item.__detailEnriched)
    if (!targets.length) return
    const queue = targets.slice(0, state.relation?.relType === 'actor' ? 120 : 80)
    const concurrency = 8
    let index = 0
    async function worker() {
      while (index < queue.length) {
        const current = queue[index++]
        try {
          const res = await sdk.api.post('/plugins/javdb/actions/video', { payload: { code: current.code } })
          const detail = res.data?.data || {}
          current.actor_count = Array.isArray(detail.actors) ? detail.actors.length : Number(current.actor_count || 0)
          current.categories = Array.isArray(detail.categories) ? detail.categories : (current.categories || [])
          current.has_cnsub = !!(current.has_cnsub || current.play_subtitle || detectCnsub(detail))
          current.is_cracked = !!(current.is_cracked || detectCracked(detail))
          if (detail.library && typeof detail.library === 'object') current.library = detail.library
          current.__detailEnriched = true
        } catch {
          current.__detailEnriched = true
          if (current.actor_count == null) current.actor_count = 0
        }
      }
    }
    await Promise.all(Array.from({ length: concurrency }, () => worker()))
  }

  function renderTabs() {
    if (!tabControl) {
      tabControl = sdk.ui.tabs({
        tabs: tabDefs,
        value: state.tab,
        route: {
          mode: 'path',
          defaultReplace: false,
          subPath: () => sdk.route?.subPath || '',
          push: path => sdk.route?.push?.(path),
          replace: path => sdk.route?.replace?.(path),
        },
        onChange: setTab,
      })
      tabsWrap.appendChild(tabControl)
    }
    tabControl.__noorSetValue?.(state.tab)
  }

  function buildPanelGroup(label, children) {
    if (sdk.ui?.filterPanelGroup) return sdk.ui.filterPanelGroup({ label, items: children })
    if (sdk.ui?.controlPanelGroup) return sdk.ui.controlPanelGroup({ label, items: children })
    const group = el('div', 'noor-control-panel__group')
    if (label) group.appendChild(el('span', 'noor-control-panel__group-label', label))
    const items = el('div', 'noor-control-panel__group-items')
    ;(Array.isArray(children) ? children : [children]).filter(Boolean).forEach(child => items.appendChild(child))
    group.appendChild(items)
    return group
  }

  function buildPanelSection(label, children) {
    if (sdk.ui?.filterPanelSection) return sdk.ui.filterPanelSection({ label, items: children })
    if (sdk.ui?.controlPanelSection) return sdk.ui.controlPanelSection({ label, items: children })
    return buildPanelGroup(label, children)
  }

  function uniqueValues(values) {
    const seen = new Set()
    return (Array.isArray(values) ? values : [])
      .map(value => String(value || '').trim())
      .filter(value => value && !seen.has(value) && seen.add(value))
  }

  function pickerMultiLabel(list, values, emptyLabel, unitLabel = '项') {
    const selected = uniqueValues(values)
    if (!selected.length) return emptyLabel
    const labels = selected
      .map(value => (Array.isArray(list) ? list : []).find(item => String(item.value) === value)?.label)
      .filter(Boolean)
    if (labels.length <= 2) return labels.join(' · ')
    return `已选 ${labels.length} ${unitLabel}`
  }

  function pickerSingleLabel(list, value, emptyLabel) {
    const current = String(value || '').trim()
    if (!current) return emptyLabel
    return (Array.isArray(list) ? list : []).find(item => String(item.value) === current)?.label || emptyLabel
  }

  function openMultiPickerModal(title, items, currentValues, onApply, emptyLabel = '全部', titleMeta = '') {
    if (!sdk.ui?.modal) return
    chooserState.search = ''
    const body = el('div', 'noor-control-panel__picker-list')
    const searchWrap = el('div', 'noor-control-panel__picker-search')
    const searchInput = sdk.ui.input
      ? sdk.ui.input({
          value: '',
          placeholder: `搜索${title}`,
          className: 'noor-control-panel__search-input',
          onInput: value => {
            chooserState.search = String(value || '').trim().toLowerCase()
            renderOptions()
          },
        })
      : null
    if (searchInput) searchWrap.appendChild(searchInput)
    const optionsWrap = el('div', 'noor-control-panel__picker-options')
    body.append(searchWrap, optionsWrap)
    let draft = uniqueValues(currentValues)

    const modal = sdk.ui.modal({
      title,
      titleMeta,
      width: 'lg',
      content: body,
      footer: [
        sdk.ui.button({
          label: emptyLabel,
          onClick: () => {
            draft = []
            renderOptions()
          },
        }),
        sdk.ui.button({
          label: '应用',
          tone: 'primary',
          onClick: () => {
            onApply([...draft])
            modal.close()
          },
        }),
        sdk.ui.button({ label: '关闭', onClick: () => modal.close() }),
      ],
      onClose: () => { chooserState.modal = null },
    })
    chooserState.modal = modal

    function renderOptions() {
      optionsWrap.innerHTML = ''
      const keyword = chooserState.search
      const fullList = [{ label: emptyLabel, value: '' }, ...(Array.isArray(items) ? items : [])]
      fullList
        .filter(item => !keyword || String(item.label || '').toLowerCase().includes(keyword))
        .forEach(item => {
          optionsWrap.appendChild(sdk.ui.chip({
            label: item.label,
            active: draft.includes(String(item.value || '')),
            className: 'noor-plugin-chip--soft',
            onClick: () => {
              const value = String(item.value || '')
              draft = draft.includes(value)
                ? draft.filter(entry => entry !== value)
                : [...draft, value]
              renderOptions()
            },
          }))
        })
    }

    renderOptions()
  }

  function openSinglePickerModal(title, items, currentValue, onApply, emptyLabel = '全部') {
    if (!sdk.ui?.modal) return
    chooserState.search = ''
    const body = el('div', 'noor-control-panel__picker-list')
    const searchWrap = el('div', 'noor-control-panel__picker-search')
    const searchInput = sdk.ui.input
      ? sdk.ui.input({
          value: '',
          placeholder: `搜索${title}`,
          className: 'noor-control-panel__search-input',
          onInput: value => {
            chooserState.search = String(value || '').trim().toLowerCase()
            renderOptions()
          },
        })
      : null
    if (searchInput) searchWrap.appendChild(searchInput)
    const optionsWrap = el('div', 'noor-control-panel__picker-options')
    body.append(searchWrap, optionsWrap)
    let draft = String(currentValue || '').trim()

    const modal = sdk.ui.modal({
      title,
      width: 'lg',
      content: body,
      footer: [
        sdk.ui.button({
          label: emptyLabel,
          onClick: () => {
            draft = ''
            renderOptions()
          },
        }),
        sdk.ui.button({
          label: '应用',
          tone: 'primary',
          onClick: () => {
            onApply(draft)
            modal.close()
          },
        }),
        sdk.ui.button({ label: '关闭', onClick: () => modal.close() }),
      ],
      onClose: () => { chooserState.modal = null },
    })
    chooserState.modal = modal

    function renderOptions() {
      optionsWrap.innerHTML = ''
      const keyword = chooserState.search
      const fullList = [{ label: emptyLabel, value: '' }, ...(Array.isArray(items) ? items : [])]
      fullList
        .filter(item => !keyword || String(item.label || '').toLowerCase().includes(keyword))
        .forEach(item => {
          const value = String(item.value || '')
          optionsWrap.appendChild(sdk.ui.chip({
            label: item.label,
            active: draft === value,
            className: 'noor-plugin-chip--soft',
            onClick: () => {
              draft = draft === value ? '' : value
              renderOptions()
            },
          }))
        })
    }

    renderOptions()
  }

  function buildPickerButton(title, values, options, onApply, emptyLabel, unitLabel, titleMeta = '') {
    const btn = sdk.ui.button({
      label: pickerMultiLabel(options, values, emptyLabel, unitLabel),
      className: `noor-control-panel__picker-btn ${uniqueValues(values).length ? '' : 'is-empty'}`.trim(),
      onClick: () => openMultiPickerModal(title, options, values, onApply, emptyLabel, titleMeta),
    })
    return btn
  }

  function buildSinglePickerButton(title, value, options, onApply, emptyLabel) {
    const current = String(value || '').trim()
    const btn = sdk.ui.button({
      label: pickerSingleLabel(options, current, emptyLabel),
      className: `noor-control-panel__picker-btn ${current ? '' : 'is-empty'}`.trim(),
      onClick: () => openSinglePickerModal(title, options, current, onApply, emptyLabel),
    })
    return btn
  }

  function sortChipLabel(option) {
    if (state.videosSort !== option.value) return option.label
    return `${option.label} ${state.videosOrder === 'asc' ? '↑' : '↓'}`
  }

  function renderFilterPanel() {
    panelWrap.innerHTML = ''
    const panelFactory = sdk.ui?.filterPanel || sdk.ui?.controlPanel
    if (!panelFactory || !sdk.ui?.chip) return
    const rows = []
    const chip = (label, active, onClick) => sdk.ui.chip({ label, active, className: 'noor-plugin-chip--soft', onClick })
    const select = (value, options, onChange) => sdk.ui?.select
      ? sdk.ui.select({ value, options, className: 'javdb-year-select', onChange })
      : null
    const pushRow = sections => {
      const valid = sections.filter(Boolean)
      if (valid.length) rows.push({ sections: valid })
    }

    if (state.relation) {
      pushRow([
        buildPanelSection('当前', [
          chip(`${state.relation.label} · 清除`, true, () => {
            state.relation = null
            state.relationActorSelectedFilters = []
            state.relationActorSingleFilter = false
            state.relationActorYear = ''
            state.relationActorSort = 'release_desc'
            state.page = 1
            loadData()
          }),
        ]),
      ])
      if (state.relation.relType === 'actor') {
        pushRow([
          buildPanelSection('筛选', [
            chip('全部', state.relationActorSelectedFilters.length === 0, () => {
              state.relationActorSelectedFilters = []
              state.page = 1
              rerenderCurrentList()
            }),
            ...relationActorBadgeFilters.map(([value, label]) => chip(label, state.relationActorSelectedFilters.includes(value), () => {
              state.relationActorSelectedFilters = state.relationActorSelectedFilters.includes(value)
                ? state.relationActorSelectedFilters.filter(x => x !== value)
                : [...state.relationActorSelectedFilters, value]
              state.page = 1
              rerenderCurrentList()
            })),
            chip('单人', state.relationActorSingleFilter, () => {
              state.relationActorSingleFilter = !state.relationActorSingleFilter
              state.page = 1
              rerenderCurrentList()
            }),
          ]),
        ])
        const yearOptions = [{ label: '全部年份', value: '' }, ...actorRelationYears().map(year => ({ label: year, value: year }))]
        const relationYearSelect = select(state.relationActorYear, yearOptions, value => {
          state.relationActorYear = String(value || '')
          state.page = 1
          rerenderCurrentList()
        })
        const relationSortSelect = select(state.relationActorSort, relationActorSortOptions, value => {
          state.relationActorSort = String(value || 'release_desc')
          state.page = 1
          rerenderCurrentList()
        })
        pushRow([
          relationYearSelect ? buildPanelSection('年份', [relationYearSelect]) : null,
          relationSortSelect ? buildPanelSection('排序', [relationSortSelect]) : null,
        ])
      }
    } else if (state.tab === 'latest') {
      pushRow([
        buildPanelSection('类型', latestTypes.map(([value, label]) => chip(label, state.latestType === value, () => {
          state.latestType = value
          state.page = 1
          loadData()
        }))),
      ])
      pushRow([
        buildPanelSection('排序', latestSorts.map(([value, label]) => chip(label, state.latestSort === value, () => {
          state.latestSort = value
          state.page = 1
          loadData()
        }))),
      ])
      pushRow([
        buildPanelSection('筛选', [
          chip('全部', state.latestSelectedFilters.length === 0, () => {
            state.latestSelectedFilters = []
            state.page = 1
            loadData()
          }),
          ...latestFilters.map(([value, label]) => chip(label, state.latestSelectedFilters.includes(value), () => {
            state.latestSelectedFilters = state.latestSelectedFilters.includes(value)
              ? state.latestSelectedFilters.filter(x => x !== value)
              : [...state.latestSelectedFilters, value]
            state.page = 1
            loadData()
          })),
        ]),
      ])
    } else if (state.tab === 'rankings') {
      pushRow([
        buildPanelSection('榜单', rankingModes.map(([value, label]) => chip(label, state.rankingMode === value, () => {
          state.rankingMode = value
          state.page = 1
          loadData()
        }))),
      ])
      if (state.rankingMode !== 'actors') {
        pushRow([
          buildPanelSection('类型', rankingTypes.map(([value, label]) => chip(label, state.rankingType === value, () => {
            state.rankingType = value
            state.page = 1
            loadData()
          }))),
        ])
      }
      if (state.rankingMode === 'top250') {
        const years = []
        const currentYear = new Date().getFullYear()
        for (let y = currentYear; y >= 2000; y--) years.push({ label: String(y), value: String(y) })
        pushRow([
          buildPanelSection('年份', [
            buildSinglePickerButton('年份', state.top250Year, years, value => {
              state.top250Year = String(value || '')
              state.page = 1
              loadData()
            }, '全部年份'),
          ]),
        ])
      }
      if (state.rankingMode !== 'actors') {
        pushRow([
          buildPanelSection('筛选', [
            chip('全部', state.rankingSelectedFilters.length === 0, () => {
              state.rankingSelectedFilters = []
              state.page = 1
              loadData()
            }),
            ...rankingFilters.map(([value, label]) => chip(label, state.rankingSelectedFilters.includes(value), () => {
              state.rankingSelectedFilters = state.rankingSelectedFilters.includes(value)
                ? state.rankingSelectedFilters.filter(x => x !== value)
                : [...state.rankingSelectedFilters, value]
              state.page = 1
              loadData()
            })),
          ]),
        ])
      }
    } else if (state.tab === 'videos') {
      pushRow([
        buildPanelSection('筛选方式', videosFilterOptions.map(([value, label]) => sdk.ui.chip({
            label,
            active: (state.videosFilter || 'all') === value,
            className: 'noor-plugin-chip--soft',
            onClick: () => {
              state.videosFilter = value === 'all' ? '' : value
              state.page = 1
              loadData()
            },
          }))),
      ])
      pushRow([
          buildPanelSection('演员', [
            buildSinglePickerButton('演员', state.videosActorId, state.videoActors, value => {
              state.videosActorId = String(value || '')
              state.page = 1
              loadData()
            }, '全部演员'),
          ]),
          buildPanelSection('类型', [
            buildPickerButton('类型', state.videosCategoryIds, state.videoCategories, values => {
              state.videosCategoryIds = uniqueValues(values)
              state.page = 1
              loadData()
            }, '全部类型', '项', '可多选'),
          ]),
          buildPanelSection('最低评分', videosMinScoreOptions.map(option => sdk.ui.chip({
            label: option.label,
            active: String(state.videosMinScore || '') === String(option.value || ''),
            className: 'noor-plugin-chip--soft',
            onClick: () => {
              state.videosMinScore = String(option.value || '')
              state.page = 1
              loadData()
            },
          }))),
      ])
      pushRow([
          buildPanelSection('排序字段', videosSortOptions.map(option => sdk.ui.chip({
            label: sortChipLabel(option),
            active: String(state.videosSort || '') === String(option.value || ''),
            className: 'noor-plugin-chip--soft',
            onClick: () => {
              if (state.videosSort === String(option.value || 'created')) {
                state.videosOrder = state.videosOrder === 'desc' ? 'asc' : 'desc'
              } else {
                state.videosSort = String(option.value || 'created')
                state.videosOrder = 'desc'
              }
              state.page = 1
              loadData()
            },
          }))),
      ])
    }

    if (!rows.length) return
    panelWrap.appendChild(panelFactory({
      rows,
      collapsible: true,
      collapseKey: state.relation ? `javdb-relation-${state.relation.relType}-filter-panel` : `javdb-${state.tab}-filter-panel`,
      defaultCollapsed: true,
    }))
  }

  function renderFilters() {
    filtersWrap.innerHTML = ''
    renderFilterPanel()
    if (state.tab === 'videos') {
      void ensureVideoCategories()
      void ensureVideoActors()
    }
  }

  function renderLoadingStatus() {
    loadingStatus.innerHTML = ''
    loadingStatus.style.display = 'none'
    if (state.loading) {
      loadingStatus.classList.remove('is-error')
      loadingStatus.style.display = 'flex'
      const message = state.hasLoadedOnce && state.items.length
        ? '正在刷新当前列表…'
        : '正在加载 JAVDB 数据…'
      loadingStatus.appendChild(el('span', 'javdb-loading-status__bar'))
      loadingStatus.appendChild(el('span', 'javdb-loading-status__spinner'))
      loadingStatus.appendChild(el('span', 'javdb-loading-status__text', message))
      return
    }
        state.items = []
        state.total = 0
      }
    }
    if (seq !== loadSeq) return
    state.loading = false
    renderLoadingStatus()
    renderFilters()
    renderGrid()
    renderPager()
        ? 'related_movies'
        : (
          state.tab === 'rankings'
            ? (state.rankingMode === 'actors' ? 'actors' : state.rankingMode === 'top250' ? 'top250' : 'rankings')
            : state.tab
        )
      const payload = {
        page: state.page,
        limit: state.limit,
        ...(state.relation ? { rel_type: state.relation.relType, rel_id: state.relation.relId } : {}),
        ...(state.tab === 'latest' ? { type: state.latestType, filter_by: remoteLatestFilter, filters: [...state.latestSelectedFilters], sort_by: state.latestSort || 'update' } : {}),
        ...(state.tab === 'videos'
        ? {
              ...(state.videosFilter ? { filter: state.videosFilter } : {}),
              sort: state.videosSort,
              order: state.videosOrder,
              ...(state.videosActorId ? { actor_id: state.videosActorId } : {}),
              ...(state.videosMinScore ? { min_score: state.videosMinScore } : {}),
              ...(state.videosCategoryIds.length ? { category_ids: [...state.videosCategoryIds] } : {}),
            }
          : {}),
        ...(state.tab === 'rankings' && ['daily', 'weekly', 'monthly'].includes(state.rankingMode)
          ? { type: state.rankingType, period: state.rankingMode, filters: [...state.rankingSelectedFilters] }
          : {}),
        ...(state.tab === 'rankings' && state.rankingMode === 'top250'
          ? { type_value: state.top250Year || String(state.rankingType), filters: [...state.rankingSelectedFilters] }
          : {}),
        ...(isActorRankingFrame() ? { type: state.rankingType } : {}),
      }
      if (state.relation?.relType === 'actor') {
        payload.page = 1
        payload.limit = 200
        payload.sort_by = 'release'
        payload.order_by = 'desc'
      }
      const res = await sdk.api.post(`/plugins/javdb/actions/${action}`, { payload })
      if (seq !== loadSeq) return
      state.items = res.data.items || []
      state.total = Number(res.data.total || state.items.length)
      state.hasLoadedOnce = true
      if (state.items.length && (state.relation?.relType === 'actor' || (state.tab === 'latest' && remoteLatestFilter !== 'all'))) {
        await enrichWorkItems(state.items)
        if (seq !== loadSeq) return
      }
      await loadSubscriptionStates()
      if (seq !== loadSeq) return
    } catch (e) {
      if (isPluginUnmountError(e)) return
      if (seq !== loadSeq) return
      const message = e.message || '数据加载失败'
    }

    const start = (state.page - 1) * state.limit
    const visible = usesRemotePaging() ? items : items.slice(start, start + state.limit)

    visible.forEach(item => {
      if (isActorRankingFrame()) {
        const actorTitle = item.name_zht || item.name || '-'
        const actorMeta = [item.name, item.other_name].filter(Boolean).join(' · ')
        const actorCard = el('button', 'javdb-actor-card')
        actorCard.type = 'button'
        actorCard.onclick = () => setRelation('actor', item.id, actorTitle)
        const avatar = el('div', 'javdb-actor-avatar')
        if (item.avatar_url) {
          const img = el('img')
          img.src = item.avatar_url
          img.alt = actorTitle
          avatar.appendChild(img)
        }
        actorCard.appendChild(avatar)
        actorCard.appendChild(el('div', 'javdb-actor-name', actorTitle))
        actorCard.appendChild(el('div', 'javdb-actor-meta', actorMeta || ''))
        const badgeRow = el('div', 'javdb-actor-badges')
        if (item.uncensored) badgeRow.appendChild(sdk.ui.badge({ label: '无码', tone: 'info' }))
      sdk.toast?.error?.('订阅中心不可用')
      return
    }
    return sdk.subscription.open({
      code: codeValue,
      title: detailTitle(videoData),
      cover_url: videoData.cover_url || videoData.thumb_url || '',
      fanart_url: videoData.fanart_url || videoData.cover_url || videoData.thumb_url || '',
      sourcePlugin: 'javdb',
      sourceLabel: 'JavDB',
      sourceRoute: window.location.pathname + window.location.search,
      sourceContext: 'javdb-work',
      defaultMode: 'loose',
      requireCracked: false,
      requireSubtitle: false,
      onSuccess: async result => {
        sdk.toast?.success?.(result?.created ? '订阅已创建' : '订阅已存在')
        await loadSubscriptionStates()
        renderGrid()
      },
    })
  }

  function renderGrid() {
    grid.innerHTML = ''
    grid.classList.toggle('javdb-grid--actors', isActorRankingFrame())
    grid.classList.toggle('is-refreshing', state.loading && state.items.length > 0)
    const items = filteredItems()

    if (state.loading && !items.length) {
      renderSkeletonGrid()
      return
    }

    if (!items.length) {
      grid.appendChild(sdk.ui.emptyState({ text: '暂无符合条件的作品' }))
      return
    }

    const start = (state.page - 1) * state.limit
    const visible = usesRemotePaging() ? items : items.slice(start, start + state.limit)

    visible.forEach(item => {
      if (isActorRankingFrame()) {
        const actorTitle = item.name_zht || item.name || '-'
        const actorMeta = [item.name, item.other_name].filter(Boolean).join(' · ')
        const actorCard = el('button', 'javdb-actor-card')
        actorCard.type = 'button'
        actorCard.onclick = () => setRelation('actor', item.id, actorTitle)
        const avatar = el('div', 'javdb-actor-avatar')
        if (item.avatar_url) {
          const img = el('img')
          img.src = item.avatar_url
          img.alt = actorTitle
          avatar.appendChild(img)
        }
        actorCard.appendChild(avatar)
        actorCard.appendChild(el('div', 'javdb-actor-name', actorTitle))
        actorCard.appendChild(el('div', 'javdb-actor-meta', actorMeta || ''))
        const badgeRow = el('div', 'javdb-actor-badges')
        if (item.uncensored) badgeRow.appendChild(sdk.ui.badge({ label: '无码', tone: 'info' }))
        actorCard.appendChild(badgeRow)
        grid.appendChild(actorCard)
        return
      }
      const badges = []
      const magnetText = magnetLabel(item)
      if (magnetText) badges.push(sdk.ui.badge({ label: magnetText, tone: 'info' }))
      if (item.has_cnsub || item.play_subtitle) badges.push(sdk.ui.badge({ label: '中字', tone: 'success' }))
      if (item.is_cracked) badges.push(sdk.ui.badge({ label: '破解', tone: 'danger' }))
      if (item.library?.in_library) badges.push(sdk.ui.badge({ label: '已入库', tone: 'info' }))

      const actionModel = subscriptionActionModel(item)
      const subscribeAction = el('button', `noor-plugin-badge javdb-subscribe-action javdb-subscribe-action--${actionModel.state}`, actionModel.label)
      subscribeAction.type = 'button'
      subscribeAction.disabled = !!actionModel.disabled
      subscribeAction.onclick = event => {
        event.stopPropagation()
        event.preventDefault()
        if (!actionModel.disabled) openSubscription(item)
      }
      const card = sdk.ui.mediaCard({
        title: titleOf(item),
        cover: item.cover_url || item.thumb_url,
        sharp: true,
        meta: [classifyCategory(item), fmtMin(item.duration)].filter(Boolean),
        badges,
        coverOnClick: () => openDetail(item),
        titleOnClick: () => openDetail(item),
        className: 'javdb-card',
      })
      const badgeHost = card.querySelector('.noor-plugin-media-card__badges')
      if (badgeHost) badgeHost.appendChild(subscribeAction)
      grid.appendChild(card)
    })
  }

  function renderPager() {
    pager.innerHTML = ''
    let totalItems = Number(state.total || 0)
    if (state.tab === 'latest' && state.latestSelectedFilters.length && latestRemoteFilter() === 'all') {
      totalItems = filteredItems().length
    }
    if (totalItems <= state.limit) return
    pager.appendChild(sdk.ui.pagination({
      page: state.page,
      totalPages: Math.ceil(totalItems / state.limit),
      onPage: next => {
        state.page = next
        if (usesRemotePaging()) {
          loadData()
          window.scrollTo({ top: 0, behavior: 'smooth' })
          return
        }
        renderGrid()
        renderPager()
        window.scrollTo({ top: 0, behavior: 'smooth' })
      },
    }))
  }

  async function openDetail(item) {
    if (state.activePanel) state.activePanel.close()
    const code = item.number || item.code || item.id
    const panel = sdk.ui.panel({ title: '影片详情', eyebrow: 'JavDB', scroll: true })
    state.activePanel = panel
      const heroBadges = el('div', 'javdb-detail-hero__badges')
      const categoryText = classifyCategory(video)
      if (categoryText) heroBadges.appendChild(sdk.ui.badge({ label: categoryText, tone: 'info' }))
      if (detectCnsub(video)) heroBadges.appendChild(sdk.ui.badge({ label: '中字', tone: 'success' }))
      if (detectCracked(video)) heroBadges.appendChild(sdk.ui.badge({ label: '破解', tone: 'danger' }))
      if (Number(video?.magnets?.length || 0) > 0) heroBadges.appendChild(sdk.ui.badge({ label: `${video.magnets.length} 磁链`, tone: 'info' }))
      heroMeta.appendChild(heroBadges)
      heroHead.appendChild(heroMeta)
      hero.appendChild(heroHead)

      const overview = el('div', 'javdb-detail-overview')
      ;[
        ['上映日期', formatReleaseDate(video?.date || video?.release_date)],
        ['时长', fmtMin(video?.duration)],
        ['评分', numericScore(video?.score) ? String(video.score) : ''],
        ['来源', String(video?.source || video?.site || 'JavDB').trim()],
      ].filter(([, value]) => value).forEach(([label, value]) => {
        const card = el('div', 'javdb-overview-card')
        card.appendChild(el('span', 'javdb-overview-card__label', label))
        card.appendChild(el('strong', 'javdb-overview-card__value', value))
        overview.appendChild(card)
      })
      if (overview.childNodes.length) hero.appendChild(overview)
      content.appendChild(hero)

      const detailSection = el('section', 'javdb-detail-section')
      const detailHead = el('div', 'javdb-detail-section__head')
      detailHead.appendChild(el('span', 'javdb-detail-section__title', '作品信息'))
      detailSection.appendChild(detailHead)

      const meta = el('div', 'javdb-detail-meta')
      const appendMetaRow = (label, source, relType) => {
        if (!source) return
        const list = (Array.isArray(source) ? source : [source]).filter(Boolean)
        if (!list.length) return
        const row = el('div', 'javdb-meta-row')
        row.appendChild(el('span', 'javdb-meta-label', label))
        const badges = el('div', 'javdb-meta-badges')
        list.forEach(entry => {
          const name = entry?.name || entry?.label || String(entry || '')
          const id = entry?.id || entry?.external_id || name
          badges.appendChild(sdk.ui.badge({
            label: name,
            tone: relType === 'category' ? undefined : 'info',
            onClick: () => {
              panel.close()
              setRelation(relType, id, name)
            },
          }))
        })
        row.appendChild(badges)
        meta.appendChild(row)
      }

      appendMetaRow('演员', video.actors, 'actor')
      appendMetaRow('系列', video.series, 'series')
      appendMetaRow('导演', video.director, 'director')
      appendMetaRow('制作商', video.maker, 'maker')
      appendMetaRow('发行商', video.publisher, 'publisher')
      appendMetaRow('类型', video.categories, 'category')
      if (meta.childNodes.length) {
        detailSection.appendChild(meta)
        content.appendChild(detailSection)
      }

      const fallbackResources = (Array.isArray(video.magnets) ? video.magnets : []).map((magnet, index) => ({
        id: `javdb:fallback:${index}`,
        provider: 'javdb',
        provider_label: 'JavDB',
        title: magnet.name || detailTitle(video),
        subtitle: [magnet.size || '', magnet.date || '', magnet.site || 'JavDB'].filter(Boolean).join(' · '),
        url: magnet.magnet || '',
        tags: Array.isArray(magnet.tags) ? magnet.tags : [],
        features: {
          has_subtitle: textHasKeywords(magnet.tags || magnet.name || '', ['中字', '字幕', '中文', '中文字幕', 'chs', 'cht']),
          is_cracked: textHasKeywords(magnet.tags || magnet.name || '', ['破解', '破解版', '无码破解', 'uncensored leak']),
          is_private_tracker: false,
        },
        requirements: String(magnet.magnet || '').startsWith('magnet:?') ? { accepts_public_magnet: true } : {},
        compatible_downloaders: [],
        preferred_downloader: null,
      }))
      const sortResources = list => list.slice().sort((a, b) => {
          const providerDiff = resourceProviderOrder(a) - resourceProviderOrder(b)
          if (providerDiff) return providerDiff
          const subA = String(a?.subtitle || '')
          const subB = String(b?.subtitle || '')
          return subA.localeCompare(subB)
        })
      let resources = sortResources(fallbackResources)

