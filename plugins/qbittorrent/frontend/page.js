export async function mount(el, sdk = {}) {
  const pluginId = sdk.pluginId || 'qbittorrent'
  const api = (path, init) => sdk.api?.plugin ? sdk.api.plugin(path, init) : fetch(`/api/plugins/${pluginId}${path}`, init)
  const toast = (type, msg) => sdk.toast?.[type]?.(msg)
  const state = {
    loading: false,
    error: '',
    version: '',
    apiMode: '',
    authMode: '',
    transfer: {},
    showNoorOnly: false,
    noorTag: 'noor',
    minFileSizeMb: 0,
    categories: {},
    settingsOpen: false,
    categoryEditor: { open: false, mode: 'create', original: '', name: '', savePath: '', deleting: '' },
    torrents: [],
    filter: 'all',
    category: '',
    query: '',
    sortKey: 'added_on',
    sortDir: 'desc',
    selected: '',
    detail: null,
    detailOpen: false,
    confirmDeleteHash: '',
    actioning: new Set(),
    filteringNoor: false,
    destroyed: false,
    refreshTimer: null,
  }

  el.innerHTML = `
    <div class="qb-page">
      <div class="qb-toolbar">
        <div class="qb-filter-tabs">
          <button data-filter="all" class="qb-filter-tab is-active">全部</button>
          <button data-filter="downloading" class="qb-filter-tab">下载中</button>
          <button data-filter="seeding" class="qb-filter-tab">做种</button>
          <button data-filter="completed" class="qb-filter-tab">已完成</button>
          <button data-filter="paused" class="qb-filter-tab">暂停</button>
          <button data-filter="errored" class="qb-filter-tab">错误</button>
        </div>
        <div class="qb-actions">
          <span data-role="version" class="qb-badge" style="display:none"></span>
          <span data-role="scope" class="qb-badge"></span>
          <button data-role="smallFilter" class="qb-badge qb-badge-btn" title="对 NOOR 推送到 qB 的任务跳过小于阈值的非字幕文件。点击可立即对当前任务执行一次过滤。" style="display:none"></button>
          <span data-role="connection" class="qb-connection"><i></i><span>未连接</span></span>
          <button data-role="settings" class="qb-icon-btn" title="设置分类路径">设置</button>
          <button data-role="refresh" class="qb-btn qb-btn--primary">刷新</button>
        </div>
      </div>
      <div class="qb-overview-row">
        <div class="qb-summary" data-role="summary"></div>
        <div class="qb-task-tools">
          <input data-role="search" class="qb-search" placeholder="搜索任务名称 / 分类 / 保存路径">
          <select data-role="category" class="qb-select"><option value="">全部分类</option></select>
        </div>
      </div>
      <div data-role="state" class="qb-state" style="display:none"></div>
      <div class="qb-table-card">
        <div class="qb-table-wrap">
          <table class="qb-table">
            <thead><tr>
              <th><button data-sort="name">名称 <span></span></button></th>
              <th><button data-sort="state">状态 <span></span></button></th>
              <th><button data-sort="progress">进度 <span></span></button></th>
              <th><button data-sort="speed">速度 <span></span></button></th>
              <th><button data-sort="size">大小 <span></span></button></th>
              <th><button data-sort="ratio">分享率 <span></span></button></th>
              <th class="qb-right">操作</th>
            </tr></thead>
            <tbody data-role="tbody"></tbody>
          </table>
        </div>
      </div>
      <div data-role="detail" class="qb-detail" style="display:none"></div>
      <div data-role="confirm" class="qb-modal-root"></div>
    </div>
  `

  const $ = role => el.querySelector(`[data-role="${role}"]`)
  const tbody = $('tbody'), stateBox = $('state'), summary = $('summary'), version = $('version'), scope = $('scope'), smallFilter = $('smallFilter'), connection = $('connection'), settings = $('settings'), refresh = $('refresh'), search = $('search'), category = $('category'), detail = $('detail'), confirmRoot = $('confirm')
  const filterButtons = Array.from(el.querySelectorAll('[data-filter]'))
  const sortButtons = Array.from(el.querySelectorAll('[data-sort]'))
  const esc = s => String(s ?? '').replace(/[&<>'"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[c]))
  const fmtBytes = n => { n = Number(n || 0); if (!n) return '0 B'; const u = ['B','KB','MB','GB','TB']; let i=0; while(n>=1024&&i<u.length-1){n/=1024;i++} return `${n.toFixed(i>=3?2:1)} ${u[i]}` }
  const fmtSpeed = n => Number(n || 0) ? `${fmtBytes(n)}/s` : '0 B/s'
  const fmtEta = n => { n = Number(n || 0); if (n < 0 || n >= 8640000) return '∞'; const h=Math.floor(n/3600), m=Math.floor((n%3600)/60); return h ? `${h}h ${m}m` : `${m}m` }
  const pct = n => `${Math.round(Number(n || 0) * 1000) / 10}%`
  const stateText = s => ({ downloading:'下载中', stalledDL:'等待下载', uploading:'做种', stalledUP:'等待做种', pausedDL:'暂停', pausedUP:'暂停', stoppedDL:'停止', stoppedUP:'停止', error:'错误', missingFiles:'文件缺失', queuedDL:'排队', queuedUP:'排队', checkingDL:'校验中', checkingUP:'校验中', checkingResumeData:'校验中', metaDL:'获取元数据', forcedDL:'强制下载', forcedUP:'强制做种', moving:'移动中' }[s] || s || '-')
  const stateTone = s => /error|missing/i.test(s) ? 'error' : /paused|stopped/i.test(s) ? 'muted' : /upload|stalledUP|forcedUP/i.test(s) ? 'success' : /check|queue|meta|moving/i.test(s) ? 'warning' : 'info'
  const priorityText = p => Number(p || 0) === 0 ? '已跳过' : Number(p || 0) >= 7 ? '最高' : Number(p || 0) >= 6 ? '高' : Number(p || 0) >= 1 ? '下载' : '默认'
  const hasTag = (torrent, tag) => String(torrent?.tags || '').split(',').map(x => x.trim().toLowerCase()).includes(String(tag || '').toLowerCase())

  function matchesFilter(t) {
    const s = String(t.state || '')
    if (state.filter === 'all') return true
    if (state.filter === 'downloading') return ['downloading','stalledDL','queuedDL','forcedDL','metaDL'].includes(s)
    if (state.filter === 'seeding') return ['uploading','stalledUP','queuedUP','forcedUP'].includes(s)
    if (state.filter === 'completed') return Number(t.progress || 0) >= 1
    if (state.filter === 'paused') return /paused|stopped/i.test(s)
    if (state.filter === 'errored') return /error|missing/i.test(s)
    return true
  }

  function sortValue(t, key) {
    if (key === 'name') return String(t.name || '').toLowerCase()
    if (key === 'state') return stateText(t.state)
    if (key === 'progress') return Number(t.progress || 0)
    if (key === 'speed') return Number(t.dlspeed || 0) + Number(t.upspeed || 0)
    if (key === 'size') return Number(t.size || 0)
    if (key === 'ratio') return Number(t.ratio || 0)
    return Number(t.added_on || 0)
  }

  function currentItems() {
    const q = state.query.trim().toLowerCase()
    const items = state.torrents.filter(t => {
      if (state.showNoorOnly && state.noorTag && !hasTag(t, state.noorTag)) return false
      if (state.category && t.category !== state.category) return false
      if (!matchesFilter(t)) return false
      if (!q) return true
      return `${t.name} ${t.category} ${t.save_path}`.toLowerCase().includes(q)
    })
    const dir = state.sortDir === 'asc' ? 1 : -1
    return items.sort((a,b) => {
      const av = sortValue(a, state.sortKey)
      const bv = sortValue(b, state.sortKey)
      if (typeof av === 'string' || typeof bv === 'string') return String(av).localeCompare(String(bv), 'zh-CN') * dir
      return ((av > bv) - (av < bv)) * dir
    })
  }

  function renderSummary() {
    const tr = state.transfer || {}
    const items = state.torrents
    const active = items.filter(t => Number(t.dlspeed || 0) > 0 || Number(t.upspeed || 0) > 0).length
    summary.innerHTML = `
      <div class="qb-stat"><span>任务</span><strong>${items.length}</strong></div>
      <div class="qb-stat"><span>活动</span><strong>${active}</strong></div>
      <div class="qb-stat"><span>下载</span><strong>${fmtSpeed(tr.dl_info_speed)}</strong></div>
      <div class="qb-stat"><span>上传</span><strong>${fmtSpeed(tr.up_info_speed)}</strong></div>
    `
  }

  function renderCategories() {
    const prev = category.value
    category.innerHTML = '<option value="">全部分类</option>'
    const keys = Object.keys(state.categories || {}).sort((a,b)=>a.localeCompare(b,'zh-CN'))
    for (const key of keys) {
      const opt = document.createElement('option')
      opt.value = key; opt.textContent = key || '未分类'
      category.appendChild(opt)
    }
    category.value = keys.includes(prev) ? prev : state.category
  }

  function renderChrome() {
    for (const btn of filterButtons) btn.classList.toggle('is-active', btn.dataset.filter === state.filter)
    for (const btn of sortButtons) {
      const active = btn.dataset.sort === state.sortKey
      btn.classList.toggle('is-active', active)
      btn.querySelector('span').textContent = active ? (state.sortDir === 'asc' ? '↑' : '↓') : '↕'
    }
    if (state.version) {
      version.style.display='inline-flex'
      version.textContent = [state.version, state.apiMode, state.authMode].filter(Boolean).join(' · ')
    } else version.style.display='none'
    scope.textContent = state.showNoorOnly ? `范围：${state.noorTag}` : '范围：全部'
    if (Number(state.minFileSizeMb || 0) > 0) {
      smallFilter.style.display = 'inline-flex'
      smallFilter.disabled = state.filteringNoor
      smallFilter.textContent = state.filteringNoor ? '过滤中' : `过滤：${state.minFileSizeMb}MB`
    } else smallFilter.style.display = 'none'
    const connected = !state.error && String(state.transfer?.connection_status || '').toLowerCase() !== 'disconnected'
    connection.classList.toggle('is-online', connected)
    connection.classList.toggle('is-offline', !connected)
    connection.querySelector('span').textContent = connected ? '已连接' : '未连接'
  }

  function renderState(items) {
    const show = state.loading || state.error || !items.length
    stateBox.style.display = show ? 'flex' : 'none'
    stateBox.className = 'qb-state' + (state.error ? ' is-error' : '')
    stateBox.innerHTML = state.loading ? '<span class="qb-spinner"></span><span>加载 qBittorrent...</span>' : state.error ? `<span>${esc(state.error)}</span>` : '<span>暂无符合条件的下载任务</span>'
  }

  function renderRows(items) {
    tbody.innerHTML = ''
    for (const t of items) {
      const tr = document.createElement('tr')
      tr.className = 'qb-row' + (state.selected === t.hash ? ' is-selected' : '')
      tr.innerHTML = `
        <td><div class="qb-name">${esc(t.name)}</div><div class="qb-sub">${esc(t.category || '未分类')} · ${esc(t.save_path || '-')}</div></td>
        <td><span class="qb-state-badge qb-state-badge--${stateTone(t.state)}">${esc(stateText(t.state))}</span></td>
        <td><div class="qb-progress"><span style="width:${Math.max(0, Math.min(100, t.progress * 100))}%"></span></div><div class="qb-sub">${pct(t.progress)} · ETA ${fmtEta(t.eta)}</div></td>
        <td><div class="qb-speed">↓ ${fmtSpeed(t.dlspeed)}</div><div class="qb-sub">↑ ${fmtSpeed(t.upspeed)}</div></td>
        <td><div>${fmtBytes(t.size)}</div><div class="qb-sub">剩余 ${fmtBytes(t.amount_left)}</div></td>
        <td>${Number(t.ratio || 0).toFixed(2)}</td>
        <td class="qb-right"><div class="qb-row-actions"><button data-act="resume">开始</button><button data-act="pause">暂停</button><button data-act="recheck">校验</button><button data-act="delete" class="is-danger">删除</button></div></td>
      `
      tr.onclick = e => { if (e.target.closest('button')) return; openDetail(t.hash) }
      for (const b of tr.querySelectorAll('button')) b.onclick = e => { e.stopPropagation(); runAction(b.dataset.act, t.hash) }
      tbody.appendChild(tr)
    }
  }

  function renderDetail() {
    if (!state.detailOpen || !state.detail) { detail.style.display = 'none'; detail.innerHTML = ''; return }
    const d = state.detail
    const props = d.properties || {}
    const files = Array.isArray(d.files) ? d.files : []
    const skipped = files.filter(f => Number(f.priority || 0) === 0).length
    const downloading = files.length - skipped
    const visibleFiles = files.slice(0,120)
    const currentHash = state.selected || props.hash || ''
    detail.style.display = 'block'
    detail.innerHTML = `
      <div class="qb-detail-head">
        <div><h3>${esc(props.name || '任务详情')}</h3><p>${esc(props.save_path || '')}</p></div>
        <div class="qb-detail-actions">
          ${Number(state.minFileSizeMb || 0) > 0 ? `<button data-role="filterThis" class="qb-btn">过滤此任务小文件</button>` : ''}
          <button data-role="closeDetail" class="qb-btn">关闭</button>
        </div>
      </div>
      <div class="qb-detail-grid">
        <div>总大小 <strong>${fmtBytes(props.total_size)}</strong></div>
        <div>已下载 <strong>${fmtBytes(props.total_downloaded)}</strong></div>
        <div>分享率 <strong>${Number(props.share_ratio || 0).toFixed(2)}</strong></div>
        <div>文件 <strong>${downloading} 下载 / ${skipped} 跳过</strong>${Number(state.minFileSizeMb || 0) > 0 ? `<small>阈值 ${esc(state.minFileSizeMb)} MB，字幕保留</small>` : ''}</div>
      </div>
      <div class="qb-files">${visibleFiles.map(f=>{
        const p = Number(f.priority || 0)
        const isSkipped = p === 0
        return `<div class="qb-file ${isSkipped ? 'is-skipped' : ''}"><div><span>${esc(f.name)}</span><small>${pct(f.progress || 0)} · ${esc(priorityText(p))}</small></div><em>${fmtBytes(f.size)}</em></div>`
      }).join('') || '<div class="qb-file">暂无文件信息</div>'}</div>
      ${files.length > visibleFiles.length ? `<div class="qb-file-note">仅显示前 ${visibleFiles.length} 个文件，共 ${files.length} 个。</div>` : ''}
    `
    detail.querySelector('[data-role="closeDetail"]').onclick = () => { state.detailOpen = false; render() }
    const filterThis = detail.querySelector('[data-role="filterThis"]')
    if (filterThis) filterThis.onclick = () => applyFilter(currentHash)
  }

  function categoryList() {
    return Object.entries(state.categories || {}).map(([key, value]) => {
      const v = value && typeof value === 'object' ? value : {}
      return { name: String(v.name || key), savePath: String(v.savePath || v.save_path || '') }
    }).sort((a,b)=>a.name.localeCompare(b.name,'zh-CN'))
  }

  function categoryManagerHtml() {
    const items = categoryList()
    return `
      <div class="qb-category-toolbar"><button data-role="newCategory" class="qb-btn qb-btn--primary">新建分类</button></div>
      <div class="qb-category-list">
        ${items.length ? '<div class="qb-category-head"><span>分类</span><span>保存路径</span><span>操作</span></div>' : ''}
        ${items.map(c => {
          const hasPath = Boolean(c.savePath)
          return `<div class="qb-category-row"><div class="qb-category-name">${esc(c.name)}</div><div class="qb-category-path ${hasPath ? '' : 'is-empty'}">${esc(c.savePath || '未绑定路径')}</div><div class="qb-category-actions"><button data-act="edit" data-name="${esc(c.name)}" data-path="${esc(c.savePath)}">编辑</button><button data-act="delete" data-name="${esc(c.name)}" class="is-danger">删除</button></div></div>`
        }).join('') || '<div class="qb-state">暂无分类</div>'}
      </div>`
  }

  function bindCategoryManager(root) {
    root.querySelector('[data-role="newCategory"]')?.addEventListener('click', () => openCategoryEditor('create'))
    for (const b of root.querySelectorAll('[data-act="edit"]')) b.onclick = () => openCategoryEditor('edit', b.dataset.name || '', b.dataset.path || '')
    for (const b of root.querySelectorAll('[data-act="delete"]')) b.onclick = () => { state.categoryEditor.deleting = b.dataset.name || ''; render() }
  }

  function openCategoryEditor(mode, name = '', savePath = '') {
    state.categoryEditor = { open: true, mode, original: name, name, savePath, deleting: '' }
    render()
  }

  function renderCategoryEditor() {
    const ce = state.categoryEditor
    if (ce.deleting) {
      confirmRoot.innerHTML = `<div class="qb-modal-mask"><div class="qb-modal"><h3>删除分类</h3><p>只删除 qB 分类，不删除下载任务和文件。</p><div class="qb-modal-name">${esc(ce.deleting)}</div><div class="qb-modal-actions"><button data-role="cancel" class="qb-btn">取消</button><button data-role="ok" class="qb-btn qb-btn--danger">删除</button></div></div></div>`
      confirmRoot.querySelector('[data-role="cancel"]').onclick = () => { ce.deleting = ''; render() }
      confirmRoot.querySelector('[data-role="ok"]').onclick = () => removeCategory(ce.deleting)
      return true
    }
    if (!ce.open) return false
    confirmRoot.innerHTML = `<div class="qb-modal-mask"><div class="qb-modal qb-modal--category"><h3>${ce.mode === 'edit' ? '编辑分类路径' : '新建分类'}</h3><label class="qb-modal-field"><span>分类名称</span><input data-role="catName" class="qb-input" value="${esc(ce.name)}" ${ce.mode === 'edit' ? 'readonly' : ''}></label><label class="qb-modal-field"><span>保存路径</span><input data-role="catPath" class="qb-input" value="${esc(ce.savePath)}" placeholder="/downloads/av"></label><div class="qb-modal-actions"><button data-role="cancel" class="qb-btn">取消</button><button data-role="ok" class="qb-btn qb-btn--primary">保存</button></div></div></div>`
    const name = confirmRoot.querySelector('[data-role="catName"]')
    const path = confirmRoot.querySelector('[data-role="catPath"]')
    name.oninput = e => { ce.name = e.target.value }
    path.oninput = e => { ce.savePath = e.target.value }
    confirmRoot.querySelector('[data-role="cancel"]').onclick = () => { ce.open = false; render() }
    confirmRoot.querySelector('[data-role="ok"]').onclick = () => saveCategory()
    return true
  }

  function renderSettings() {
    if (!state.settingsOpen) return false
    confirmRoot.innerHTML = `<div class="qb-modal-mask"><div class="qb-modal qb-modal--settings"><div class="qb-modal-title"><h3>qB 设置</h3><button data-role="closeSettings" class="qb-icon-btn">关闭</button></div><div class="qb-setting-section"><h4>分类路径</h4>${categoryManagerHtml()}</div></div></div>`
    confirmRoot.querySelector('[data-role="closeSettings"]').onclick = () => { state.settingsOpen = false; render() }
    bindCategoryManager(confirmRoot)
    return true
  }

  function renderConfirm() {
    confirmRoot.innerHTML = ''
    if (renderCategoryEditor()) return
    if (renderSettings()) return
    if (!state.confirmDeleteHash) return
    const torrent = state.torrents.find(t => t.hash === state.confirmDeleteHash)
    confirmRoot.innerHTML = `<div class="qb-modal-mask"><div class="qb-modal"><h3>移除下载任务</h3><p>将从 qBittorrent 中移除任务，不删除已下载文件。</p><div class="qb-modal-name">${esc(torrent?.name || state.confirmDeleteHash)}</div><div class="qb-modal-actions"><button data-role="cancel" class="qb-btn">取消</button><button data-role="ok" class="qb-btn qb-btn--danger">移除任务</button></div></div></div>`
    confirmRoot.querySelector('[data-role="cancel"]').onclick = () => { state.confirmDeleteHash = ''; render() }
    confirmRoot.querySelector('[data-role="ok"]').onclick = () => {
      const hash = state.confirmDeleteHash
      state.confirmDeleteHash = ''
      runAction('delete', hash, true)
    }
  }

  function render() {
    if (state.destroyed) return
    renderSummary(); renderCategories(); renderChrome()
    const items = currentItems()
    renderState(items); renderRows(items); renderDetail(); renderConfirm()
  }

  async function call(action, payload = {}) {
    const r = await api(`/actions/${action}`, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ payload }) })
    const data = await r.json().catch(() => ({}))
    if (!r.ok) throw new Error(data.detail || `${action} failed`)
    if (data?.ok === false) throw new Error(data.message || data.detail || `${action} failed`)
    return data
  }

  async function load(options = {}) {
    const silent = !!options.silent
    if (!silent) { state.loading = true; state.error = ''; render() }
    try {
      const data = await call('overview')
      state.version = data.version ? `qB ${data.version}` : ''
      state.apiMode = data.api_mode === 'start_stop' ? 'start/stop' : data.api_mode === 'pause_resume' ? 'pause/resume' : ''
      state.authMode = data.auth_mode === 'api_key' ? 'API Key' : data.auth_mode === 'cookie' ? 'Cookie' : ''
      state.transfer = data.transfer || {}
      state.showNoorOnly = !!data.show_noor_only
      state.noorTag = data.noor_tag || 'noor'
      state.minFileSizeMb = data.min_file_size_mb || 0
      state.categories = data.categories || {}
      state.torrents = data.torrents || []
      state.error = ''
    } catch (e) {
      state.error = e.message || 'qBittorrent 加载失败'
      state.torrents = []
    } finally {
      state.loading = false; render()
    }
  }

  async function saveCategory() {
    const ce = state.categoryEditor
    const name = ce.name.trim()
    if (!name) { toast('error', '分类名称不能为空'); return }
    try {
      await call(ce.mode === 'edit' ? 'edit_category' : 'create_category', { name, save_path: ce.savePath.trim() })
      toast('success', '分类已保存')
      ce.open = false
      state.settingsOpen = true
      await load()
    } catch (e) {
      toast('error', e.message || '分类保存失败')
    } finally { render() }
  }

  async function removeCategory(name) {
    try {
      await call('remove_categories', { categories: [name] })
      toast('success', '分类已删除')
      state.categoryEditor.deleting = ''
      state.settingsOpen = true
      await load()
    } catch (e) {
      toast('error', e.message || '分类删除失败')
    } finally { render() }
  }

  async function runAction(action, hash, confirmed = false) {
    if (state.actioning.has(`${action}:${hash}`)) return
    if (action === 'delete' && !confirmed) { state.confirmDeleteHash = hash; render(); return }
    state.actioning.add(`${action}:${hash}`)
    try {
      await call(action, { hash, deleteFiles: false })
      toast('success', '操作已提交')
      await load()
    } catch (e) {
      toast('error', e.message || '操作失败')
    } finally {
      state.actioning.delete(`${action}:${hash}`)
    }
  }

  async function openDetail(hash) {
    state.selected = hash; state.detailOpen = true; render()
    try {
      state.detail = await call('properties', { hash })
    } catch (e) {
      toast('error', e.message || '详情加载失败')
      state.detailOpen = false
    } finally { render() }
  }

  async function applyFilter(hash = '') {
    if (state.filteringNoor) return
    state.filteringNoor = true; render()
    try {
      const data = await call('apply_noor_filter', hash ? { hash } : {})
      toast('success', `过滤完成：已跳过 ${data.changed || 0} 个小文件`)
      if (hash) await openDetail(hash)
      else await load()
    } catch (e) {
      toast('error', e.message || '过滤失败')
    } finally {
      state.filteringNoor = false; render()
    }
  }

  refresh.onclick = () => load()
  smallFilter.onclick = () => applyFilter()
  settings.onclick = () => { state.settingsOpen = true; render() }
  search.oninput = e => { state.query = e.target.value; render() }
  category.onchange = e => { state.category = e.target.value; render() }
  for (const btn of filterButtons) btn.onclick = () => { state.filter = btn.dataset.filter; render() }
  for (const btn of sortButtons) btn.onclick = () => {
    const key = btn.dataset.sort
    if (state.sortKey === key) state.sortDir = state.sortDir === 'asc' ? 'desc' : 'asc'
    else { state.sortKey = key; state.sortDir = key === 'name' ? 'asc' : 'desc' }
    render()
  }
  await load()
  state.refreshTimer = setInterval(() => { if (!state.destroyed && !state.settingsOpen && !state.categoryEditor.open && !state.categoryEditor.deleting) load({ silent: true }) }, 8000)
  return () => { state.destroyed = true; if (state.refreshTimer) clearInterval(state.refreshTimer); el.innerHTML = '' }
}
