function el(tag, cls = '', text = '') { const n = document.createElement(tag); if (cls) n.className = cls; if (text) n.textContent = text; return n }
function fmtDate(v) { return String(v || '').slice(0, 10) }
function fmtMin(v) { const n = Number(v || 0); return n ? `${n} 分钟` : '' }
function titleOf(item) {
  const code = String(item?.number || item?.code || '').trim()
  const title = String(item?.title || item?.origin_title || '').trim()
  return code ? `[${code}] ${title}` : title
}
function titleCandidates(item) {
  const code = String(item?.number || item?.code || '').trim()
  const main = String(item?.title || '').trim()
  const smart = String(item?.display_title || item?.smart_title || (code ? `[${code}] ${main}` : main)).trim()
  return [{ key: 'smart', label: '智能优选', value: smart, hint: '优先使用番号+中文标题。' }, { key: 'main', label: '主标题', value: main, hint: '作品原始主标题。' }, { key: 'code', label: '编号', value: code, hint: '仅使用番号。' }].filter(opt => opt.value)
}

export async function mount(root, sdk) {
  const state = { 
    tab: 'latest', 
    latestFilter: 'all',
    relation: null, 
    page: 1, 
    limit: 48, 
    total: 0, 
    items: [], 
    loading: false, 
    activePanel: null 
  }
  
  let disposed = false; 
  let tabControl = null;
  root.innerHTML = ''
  
  const container = el('div', 'javdb-page')
  const header = el('div', 'javdb-header-wrap')
  const tabsWrap = el('div', 'javdb-tabs-wrap')
  const filtersBar = el('div', 'javdb-filters-bar')
  const grid = el('div', 'javdb-grid')
  const pagerWrap = el('div', 'javdb-pager')
  
  header.append(tabsWrap, filtersBar)
  container.append(header, grid, pagerWrap)
  root.appendChild(container)

  const tabDefs = [
    { value: 'latest', label: '最近更新' },
    { value: 'recommend', label: '推荐' },
    { value: 'rankings', label: '榜单' },
    { value: 'videos', label: '影库' }
  ]
  
  const latestFilters = [
    ['all', '全部'], ['magnets', '有磁链'], ['cnsub', '中字'], 
    ['cracked', '破解'], ['playable', '可播放'], ['library', '已入库'], ['not_library', '未入库']
  ]

  function setTab(val) { 
    state.tab = val
    state.page = 1
    state.relation = null
    state.latestFilter = 'all'
    loadData() 
  }
  
  function setRelation(relType, id, label) { 
    state.relation = { relType, id, label }
    state.page = 1
    loadData() 
  }

  function renderFilters() {
    filtersBar.innerHTML = ''
    if (state.relation) {
      const chip = sdk.ui.chip({ 
        label: `${state.relation.label} (清除)`, 
        active: true, 
        onClick: () => { state.relation = null; loadData() } 
      })
      filtersBar.appendChild(chip)
      return
    }
    
    if (state.tab === 'latest') {
      latestFilters.forEach(([val, label]) => {
        const chip = sdk.ui.chip({ 
          label, 
          active: state.latestFilter === val, 
          onClick: () => { state.latestFilter = val; state.page = 1; loadData() } 
        })
        filtersBar.appendChild(chip)
      })
    }
  }

  async function loadData() {
    state.loading = true
    renderFilters()
    renderGrid()
    try {
      const action = state.relation ? 'related_movies' : state.tab
      const payload = { 
        page: state.page, 
        limit: state.limit,
        ...(state.relation ? { rel_type: state.relation.relType, rel_id: state.relation.id } : {}),
        ...(state.tab === 'latest' ? { filter_by: state.latestFilter } : {})
      }
      const res = await sdk.api.post(`/plugins/javdb/actions/${action}`, { payload })
      state.items = res.data.items || []
      state.total = Number(res.data.total || state.items.length)
    } catch (e) { sdk.toast.error(e.message || '数据加载失败') }
    state.loading = false
    renderGrid()
    renderPager()
  }

  function renderGrid() {
    grid.innerHTML = ''
    if (state.loading && !state.items.length) {
      for (let i = 0; i < 12; i++) grid.appendChild(el('div', 'javdb-card javdb-skeleton'))
      return
    }
    
    if (!state.items.length) {
      grid.appendChild(sdk.ui.emptyState({ text: '暂无符合条件的作品' }))
      return
    }

    state.items.forEach(m => {
      const badges = []
      if (m.has_cnsub || m.play_subtitle) badges.push(sdk.ui.badge({ label: '中字', tone: 'success' }))
      if (m.is_cracked) badges.push(sdk.ui.badge({ label: '破解', tone: 'danger' }))
      if (m.library?.in_library) badges.push(sdk.ui.badge({ label: '已入库', tone: 'info' }))

      const card = sdk.ui.mediaCard({
        title: titleOf(m),
        cover: m.cover_url || m.thumb_url,
        sharp: true,
        meta: [m.number, fmtMin(m.duration)].filter(Boolean),
        badges,
        onClick: () => openDetail(m),
        className: 'javdb-card'
      })
      grid.appendChild(card)
    })
  }

  function renderPager() {
    pagerWrap.innerHTML = ''
    if (state.total <= state.limit) return
    pagerWrap.appendChild(sdk.ui.pagination({
      page: state.page,
      totalPages: Math.ceil(state.total / state.limit),
      onPage: (n) => { 
        state.page = n
        loadData()
        window.scrollTo({ top: 0, behavior: 'smooth' })
      }
    }))
  }

  async function openDetail(movie) {
    const code = movie.number || movie.code || movie.id
    const panelInstance = sdk.ui.panel({ title: code, eyebrow: '影片详情', scroll: true })
    state.activePanel = panelInstance
    const panelBody = panelInstance.body
    panelBody.appendChild(sdk.ui.loadingState({ text: '正在调取详情数据...' }))

    try {
      const res = await sdk.api.post('/plugins/javdb/actions/video', { payload: { code } })
      const v = res.data.data
      panelBody.innerHTML = ''
      const content = el('div', 'javdb-detail')
      
      // Unified Gallery Slider
      const gallery = el('div', 'javdb-detail-gallery')
      const images = [v.cover_url, ...(v.previews || [])].filter(Boolean)
      images.forEach(src => {
        const img = el('img', 'javdb-gallery-img')
        img.src = src
        img.onclick = () => sdk.ui.previewImage(src, images)
        gallery.appendChild(img)
      })
      content.appendChild(gallery)

      // Meta Rows with Filter Interaction
      const metaContainer = el('div', 'javdb-detail-meta')
      const addMetaRow = (label, items, type) => {
        if (!items || (Array.isArray(items) && !items.length)) return
        const itemList = Array.isArray(items) ? items : [items]
        const row = el('div', 'javdb-meta-row')
        row.append(el('span', 'javdb-meta-label', label))
        const badges = el('div', 'javdb-meta-badges')
        itemList.forEach(it => {
          const name = it.name || it.label || it
          const id = it.id || it.external_id || name
          badges.appendChild(sdk.ui.badge({ 
            label: name, 
            tone: 'info', 
            onClick: () => { 
              panelInstance.close()
              setRelation(type, id, name) 
            } 
          }))
        })
        row.appendChild(badges)
        metaContainer.appendChild(row)
      }
      
      addMetaRow('演员', v.actors, 'actor')
      addMetaRow('系列', v.series, 'series')
      addMetaRow('导演', v.director, 'director')
      addMetaRow('制作商', v.maker, 'maker')
      addMetaRow('发行商', v.publisher, 'publisher')
      addMetaRow('类型', v.categories, 'category')
      content.appendChild(metaContainer)

      // Magnets
      content.append(el('div', 'javdb-section-title', '下载资源'))
      const magList = el('div', 'javdb-magnets')
      if (v.magnets && v.magnets.length) {
        v.magnets.forEach(m => {
          const row = el('div', 'javdb-magnet-row')
          const info = el('div', 'javdb-magnet-info')
          info.innerHTML = `
            <div class="javdb-magnet-name">${m.name || '未知磁链'}</div>
            <div class="javdb-magnet-meta">${m.size} · ${m.date} · ${m.tags?.join(' / ') || 'JavDB'}</div>
          `
          const pushBtn = sdk.ui.submitButton({ 
            idleLabel: '推送', 
            successLabel: '已加入', 
            onClick: async () => {
              const opts = await sdk.api.post('/plugins/javdb/actions/download_options', { payload: {} })
              const { downloader_binding, default_downloader } = opts.data
              const ids = Array.isArray(downloader_binding) ? downloader_binding : []
              if (!ids.length) { sdk.toast.error('未绑定下载器'); throw new Error('No bindings') }
              
              return sdk.downloads.open({ 
                downloaderId: (default_downloader && default_downloader !== 'none') ? default_downloader : ids[0], 
                downloaderIds: ids, 
                url: m.magnet, 
                title: titleOf(v), 
                rename: titleCandidates(v)[0].value, 
                titleOptions: titleCandidates(v) 
              })
            }
          })
          row.append(info, pushBtn)
          magList.appendChild(row)
        })
      } else {
        magList.appendChild(el('div', 'javdb-no-data', '暂无磁链资源'))
      }
      content.appendChild(magList)
      
      panelBody.appendChild(content)
    } catch (e) { 
      sdk.toast.error(e.message || '加载详情失败')
      panelInstance.close() 
    }
  }

  // Initialize Tabs
  if (!tabControl) { 
    tabControl = sdk.ui.tabs({ 
      tabs: tabDefs, 
      value: state.tab, 
      onChange: setTab 
    })
    tabsWrap.appendChild(tabControl) 
  }
  
  loadData()
  
  return () => { 
    disposed = true
    state.activePanel?.close() 
  }
}
