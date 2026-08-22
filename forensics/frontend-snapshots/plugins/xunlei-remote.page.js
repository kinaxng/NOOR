export async function mount(el, sdk = {}) {
  const pluginId = sdk.pluginId || 'xunlei-remote'
  const api = (path, init) => sdk.api?.plugin ? sdk.api.plugin(path, init) : fetch(`/api/plugins/${pluginId}${path}`, init)
  const toast = (type, msg) => sdk.toast?.[type]?.(msg)
  const state = {
    loading: false,
    error: '',
    tasks: [],
    device: null,
    about: null,
    config: null,
    filter: 'active',
    query: '',
    page: 1,
    pageSize: 10,
    actioning: new Set(),
    timer: null,
    destroyed: false,
    renderedTabsKey: '',
    tableSignature: '',
  }

  el.innerHTML = `
    <div class="xunlei-remote-page">
      <div class="xunlei-remote-toolbar">
        <div data-role="tabs"></div>
        <div class="xunlei-remote-actions">
          <span data-role="device" class="xunlei-remote-badge">未连接</span>
          <button data-role="refresh" class="xunlei-remote-btn xunlei-remote-btn--primary">刷新</button>
        </div>
      </div>
      <div class="xunlei-remote-stats" data-role="stats"></div>
      <div class="xunlei-remote-search"><span>搜索</span><input data-role="search" placeholder="任务名 / 路径 / 链接"></div>
      <div data-role="state" class="xunlei-remote-state" style="display:none"></div>
      <div class="xunlei-remote-table-card">
        <div class="xunlei-remote-table-wrap">
          <table class="xunlei-remote-table">
            <thead><tr><th>名称</th><th>状态</th><th>进度</th><th>速度</th><th>大小</th><th>时间</th><th class="xunlei-remote-right">操作</th></tr></thead>
            <tbody data-role="tbody"></tbody>
          </table>
        </div>
      </div>
      <div data-role="pager" class="xunlei-remote-pager"></div>
    </div>
  `

  const $ = role => el.querySelector(`[data-role="${role}"]`)
  const tabsHost = $('tabs')
  const device = $('device')
  const refresh = $('refresh')
  const stats = $('stats')
  const search = $('search')
  const stateBox = $('state')
  const tbody = $('tbody')
  const pager = $('pager')

  const esc = s => String(s ?? '').replace(/[&<>'"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[c]))
  const fmtBytes = n => { n = Number(n || 0); if (!n) return '0 B'; const u = ['B', 'KB', 'MB', 'GB', 'TB']; let i = 0; while (n >= 1024 && i < u.length - 1) { n /= 1024; i++ } return `${n.toFixed(i >= 3 ? 2 : 1)} ${u[i]}` }
  const fmtSpeed = n => Number(n || 0) ? `${fmtBytes(n)}/s` : '0 B/s'
  const fmtTime = s => { if (!s) return '-'; const d = new Date(s); return Number.isNaN(d.getTime()) ? s : `${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}` }
  const pct = n => `${Math.round(Number(n || 0) * 1000) / 10}%`
  const phaseText = p => ({ PHASE_TYPE_PENDING: '等待中', PHASE_TYPE_RUNNING: '下载中', PHASE_TYPE_PAUSED: '暂停', PHASE_TYPE_COMPLETE: '完成', PHASE_TYPE_ERROR: '错误' }[p] || p || '-')
  const phaseTone = p => p === 'PHASE_TYPE_COMPLETE' ? 'success' : p === 'PHASE_TYPE_ERROR' ? 'error' : p === 'PHASE_TYPE_PAUSED' ? 'muted' : p === 'PHASE_TYPE_RUNNING' ? 'info' : 'warning'

  function currentItems() {
    const q = state.query.trim().toLowerCase()
    return state.tasks.filter(t => {
      if (q && !`${t.name} ${t.savepath} ${t.url}`.toLowerCase().includes(q)) return false
      if (state.filter === 'all') return true
      if (state.filter === 'active') return ['PHASE_TYPE_PENDING', 'PHASE_TYPE_RUNNING', 'PHASE_TYPE_PAUSED', 'PHASE_TYPE_ERROR'].includes(t.phase)
      if (state.filter === 'done') return t.phase === 'PHASE_TYPE_COMPLETE'
      if (state.filter === 'running') return ['PHASE_TYPE_PENDING', 'PHASE_TYPE_RUNNING'].includes(t.phase)
      if (state.filter === 'paused') return t.phase === 'PHASE_TYPE_PAUSED'
      if (state.filter === 'error') return t.phase === 'PHASE_TYPE_ERROR'
      return true
    })
  }

  function renderTabs(force = false) {
    const tabs = [
      { key: 'active', label: '进行中' },
      { key: 'all', label: '全部' },
      { key: 'running', label: '下载中' },
      { key: 'done', label: '已完成' },
      { key: 'paused', label: '暂停' },
      { key: 'error', label: '错误' },
    ]
    const key = state.filter
    if (!force && state.renderedTabsKey === key && tabsHost.childNodes.length) return
    const oldDispose = tabsHost.__noorDispose
    if (typeof oldDispose === 'function') oldDispose()
    tabsHost.__noorDispose = null
    tabsHost.innerHTML = ''
    state.renderedTabsKey = key
    const onChange = next => {
      if (state.filter === next) return
      state.filter = next
      state.page = 1
      state.tableSignature = ''
      renderTabs(true)
      render()
    }
    if (sdk.ui?.tabs) {
      const ui = sdk.ui.tabs({ value: state.filter, tabs, onChange })
      tabsHost.__noorDispose = ui.dispose
      tabsHost.appendChild(ui)
      return
    }
    tabsHost.innerHTML = `<div class="xunlei-remote-tabs">${tabs.map(t => `<button class="${t.key === state.filter ? 'is-active' : ''}" data-tab="${t.key}">${t.label}</button>`).join('')}</div>`
    for (const b of tabsHost.querySelectorAll('[data-tab]')) b.onclick = () => onChange(b.dataset.tab)
  }

  function renderStats() {
    const active = state.tasks.filter(t => ['PHASE_TYPE_PENDING', 'PHASE_TYPE_RUNNING', 'PHASE_TYPE_PAUSED', 'PHASE_TYPE_ERROR'].includes(t.phase)).length
    const running = state.tasks.filter(t => t.phase === 'PHASE_TYPE_RUNNING').length
    const done = state.tasks.filter(t => t.phase === 'PHASE_TYPE_COMPLETE').length
    const speed = state.tasks.reduce((s, t) => s + Number(t.speed || 0), 0)
    const quota = state.about?.quota
    stats.innerHTML = `
      <div class="xunlei-remote-stat"><span>任务</span><strong>${state.tasks.length}</strong></div>
      <div class="xunlei-remote-stat"><span>进行中</span><strong>${active}</strong></div>
      <div class="xunlei-remote-stat"><span>下载中</span><strong>${running}</strong></div>
      <div class="xunlei-remote-stat"><span>已完成</span><strong>${done}</strong></div>
      <div class="xunlei-remote-stat"><span>速度</span><strong>${fmtSpeed(speed)}</strong></div>
      ${quota ? `<div class="xunlei-remote-stat"><span>云盘用量</span><strong>${fmtBytes(quota.usage)}</strong></div>` : ''}
    `
  }

  function visibleItems() {
    const items = currentItems()
    const pages = Math.max(1, Math.ceil(items.length / state.pageSize))
    if (state.page > pages) state.page = pages
    if (state.page < 1) state.page = 1
    return { items, pages, visible: items.slice((state.page - 1) * state.pageSize, state.page * state.pageSize) }
  }

  function rowHtml(t) {
    return `<tr data-id="${esc(t.id)}"><td><div class="xunlei-remote-name">${esc(t.name)}</div><div class="xunlei-remote-sub">${esc(t.savepath || t.url || '')}</div></td><td data-cell="phase"><span class="xunlei-remote-status xunlei-remote-status--${phaseTone(t.phase)}">${phaseText(t.phase)}</span></td><td data-cell="progress"><div class="xunlei-remote-progress"><i style="width:${Math.max(0, Math.min(100, Number(t.progress || 0) * 100))}%"></i></div><small>${pct(t.progress)}</small></td><td data-cell="speed">${fmtSpeed(t.speed)}</td><td>${esc(t.size_formatted || fmtBytes(t.size))}</td><td>${fmtTime(t.created_time)}</td><td class="xunlei-remote-right"><div class="xunlei-remote-row-actions">${t.phase === 'PHASE_TYPE_PAUSED' ? `<button data-act="resume_task" data-id="${esc(t.id)}">▶</button>` : `<button data-act="pause_task" data-id="${esc(t.id)}">⏸</button>`}<button class="is-danger" data-act="delete_tasks" data-id="${esc(t.id)}">删</button></div></td></tr>`
  }

  function bindRowActions(root = tbody) {
    for (const b of root.querySelectorAll('[data-act]')) b.onclick = e => { e.stopPropagation(); operate(b.dataset.act, b.dataset.id) }
  }

  function patchRows(visible) {
    for (const t of visible) {
      const row = tbody.querySelector(`tr[data-id="${CSS.escape(String(t.id))}"]`)
      if (!row) return false
      const phase = row.querySelector('[data-cell="phase"]')
      const progress = row.querySelector('[data-cell="progress"]')
      const speed = row.querySelector('[data-cell="speed"]')
      if (phase) phase.innerHTML = `<span class="xunlei-remote-status xunlei-remote-status--${phaseTone(t.phase)}">${phaseText(t.phase)}</span>`
      if (progress) progress.innerHTML = `<div class="xunlei-remote-progress"><i style="width:${Math.max(0, Math.min(100, Number(t.progress || 0) * 100))}%"></i></div><small>${pct(t.progress)}</small>`
      if (speed) speed.textContent = fmtSpeed(t.speed)
      const actions = row.querySelector('.xunlei-remote-row-actions')
      if (actions) {
        actions.innerHTML = `${t.phase === 'PHASE_TYPE_PAUSED' ? `<button data-act="resume_task" data-id="${esc(t.id)}">▶</button>` : `<button data-act="pause_task" data-id="${esc(t.id)}">⏸</button>`}<button class="is-danger" data-act="delete_tasks" data-id="${esc(t.id)}">删</button>`
        bindRowActions(actions)
      }
    }
    return true
  }

  function renderPager(pages) {
    pager.innerHTML = ''
    if (sdk.ui?.pagination) {
      const ui = sdk.ui.pagination({ page: state.page, totalPages: pages, onChange: p => { state.page = p; state.tableSignature = ''; renderTable() } })
      ui.style.justifyContent = 'center'
      pager.appendChild(ui)
    } else {
      pager.innerHTML = `<button ${state.page <= 1 ? 'disabled' : ''}>上一页</button><span>${state.page}/${pages}</span><button ${state.page >= pages ? 'disabled' : ''}>下一页</button>`
    }
  }

  function renderTable() {
    const { visible, pages } = visibleItems()
    const signature = `${state.filter}|${state.query}|${state.page}|${pages}|${visible.map(t => t.id).join(',')}`
    if (signature === state.tableSignature && patchRows(visible)) return
    state.tableSignature = signature
    tbody.innerHTML = visible.map(rowHtml).join('')
    bindRowActions()
    renderPager(pages)
  }

  function render() {
    if (state.destroyed) return
    renderTabs()
    renderStats()
    device.textContent = state.device?.user?.name ? `已连接 · ${state.device.user.name}` : '未连接'
    refresh.disabled = state.loading
    refresh.textContent = state.loading ? '刷新中' : '刷新'
    stateBox.style.display = state.error || (!state.loading && !currentItems().length) ? 'flex' : 'none'
    stateBox.className = 'xunlei-remote-state' + (state.error ? ' is-error' : '')
    stateBox.textContent = state.error || '暂无任务'
    renderTable()
  }

  async function load(options = {}) {
    const silent = !!options.silent
    if (!silent) {
      state.loading = true
      state.error = ''
      render()
    }
    try {
      const [dev, tasks, about, cfg] = await Promise.all([
        api('/actions/device_info', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ payload: {} }) }).then(r => r.json()),
        api('/actions/tasks', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ payload: { phase: 'all', limit: 200 } }) }).then(r => r.json()),
        api('/actions/about', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ payload: {} }) }).then(r => r.json()).catch(() => null),
        api('/actions/device_config', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ payload: {} }) }).then(r => r.json()).catch(() => null),
      ])
      if (dev.ok === false) throw new Error(dev.detail || dev.message || '设备连接失败')
      if (tasks.ok === false) throw new Error(tasks.detail || tasks.message || '任务读取失败')
      state.error = ''
      state.device = dev.info || dev
      state.tasks = Array.isArray(tasks.tasks) ? tasks.tasks : []
      state.about = about?.about || null
      state.config = cfg?.config || null
    } catch (e) {
      if (!silent) state.error = e.message || '加载失败'
    } finally {
      state.loading = false
      render()
    }
  }

  async function operate(action, id) {
    if (!id || state.actioning.has(id)) return
    state.actioning.add(id)
    try {
      const ok = action === 'delete_tasks'
        ? await (sdk.ui?.confirm ? sdk.ui.confirm({ title: '删除任务', message: '只删除迅雷任务，不删除已下载文件。', confirmText: '删除', danger: true }) : Promise.resolve(confirm('删除任务？')))
        : true
      if (!ok) return
      const r = await api(`/actions/${action}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ payload: { id, ids: [id] } }) })
      const data = await r.json().catch(() => ({}))
      if (!r.ok || data.ok === false) throw new Error(data.detail || data.message || '操作失败')
      toast('success', '操作已提交')
      state.tableSignature = ''
      await load({ silent: true })
    } catch (e) {
      toast('error', e.message || '操作失败')
    } finally {
      state.actioning.delete(id)
    }
  }

  refresh.onclick = () => load()
  search.oninput = e => { state.query = e.target.value; state.page = 1; state.tableSignature = ''; render() }
  await load()
  state.timer = setInterval(() => { if (!state.destroyed && !state.loading) load({ silent: true }) }, 10000)
  return () => {
    state.destroyed = true
    if (state.timer) clearInterval(state.timer)
    const oldDispose = tabsHost.__noorDispose
    if (typeof oldDispose === 'function') oldDispose()
    el.innerHTML = ''
  }
}
