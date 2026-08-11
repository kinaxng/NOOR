function h(tag, cls = '', text = '') {
  const el = document.createElement(tag)
  if (cls) el.className = cls
  if (text) el.textContent = text
  return el
}
function fmtDate(value) {
  if (!value) return '未检测'
  return String(value).replace('T', ' ').slice(0, 16)
}
function fmtSize(bytes) {
  const n = Number(bytes || 0)
  if (!n) return ''
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let v = n, i = 0
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i += 1 }
  return `${v.toFixed(i ? 1 : 0)} ${units[i]}`
}
function esc(value) {
  return String(value ?? '').replace(/[&<>'"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]))
}
function badge(label, tone = 'info') {
  const b = h('span', `sub-badge sub-badge--${tone}`, label)
  return b
}

export async function mount(root, sdk = {}) {
  const pluginId = sdk.pluginId || 'subscription-core'
  const state = {
    loading: true,
    checking: false,
    error: '',
    stats: {},
    items: [],
    events: [],
    formOpen: false,
    form: { code: '', title: '', mode: 'loose', require_cracked: false, require_subtitle: false },
  }
  const apiPost = async (action, payload = {}) => {
    if (sdk.api?.post) return (await sdk.api.post(`/plugins/${pluginId}/actions/${action}`, { payload })).data
    return fetch(`/api/plugins/${pluginId}/actions/${action}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ payload }) }).then(r => r.json())
  }

  root.innerHTML = `
    <div class="sub-page">
      <div data-role="topbar"></div>
      <div data-role="notice"></div>
      <div data-role="form"></div>
      <div class="sub-layout">
        <section data-role="items" class="sub-list"></section>
        <aside data-role="events" class="sub-events"></aside>
      </div>
    </div>
  `
  const $ = role => root.querySelector(`[data-role="${role}"]`)

  function notify(type, message) {
    if (!message) return
    const fn = type === 'error' ? 'error' : type === 'success' ? 'success' : 'info'
    sdk.toast?.[fn]?.(message)
  }

  function renderTopbar() {
    const host = $('topbar')
    host.innerHTML = ''
    const stats = [
      badge(`全部 ${state.stats.total || 0}`, 'primary'),
      badge(`订阅 ${state.stats.subscribe || 0}`, 'info'),
      badge(`洗版 ${state.stats.upgrade || 0}`, 'warning'),
      badge(`已匹配 ${state.stats.matched || 0}`, 'success'),
    ]
    const createBtn = sdk.ui?.button ? sdk.ui.button({ label: '新建订阅', tone: 'primary', onClick: () => { state.formOpen = !state.formOpen; render() } }) : h('button', '', '新建订阅')
    if (!sdk.ui?.button) createBtn.onclick = () => { state.formOpen = !state.formOpen; render() }
    const checkBtn = sdk.ui?.button ? sdk.ui.button({ label: state.checking ? '检测中…' : '手动检测', disabled: state.checking, onClick: checkAll }) : h('button', '', state.checking ? '检测中…' : '手动检测')
    if (!sdk.ui?.button) checkBtn.onclick = checkAll
    const bar = sdk.ui?.topBar ? sdk.ui.topBar({ tabs: stats, actions: [createBtn, checkBtn] }) : null
    if (bar) host.appendChild(bar.el || bar)
    else {
      const wrap = h('div', 'noor-plugin-topbar')
      const left = h('div', 'noor-plugin-topbar__tabs')
      stats.forEach(x => left.appendChild(x))
      const right = h('div', 'noor-plugin-topbar__actions')
      right.append(createBtn, checkBtn)
      wrap.append(left, right)
      host.appendChild(wrap)
    }
  }

  function renderNotice() {
    const host = $('notice')
    host.innerHTML = ''
    if (state.error) host.append(sdk.ui?.notice ? sdk.ui.notice({ text: state.error, tone: 'error' }) : h('div', 'sub-notice is-error', state.error))
  }

  function renderForm() {
    const host = $('form')
    host.innerHTML = ''
    if (!state.formOpen) return
    const panel = h('section', 'sub-panel sub-form')
    panel.innerHTML = `
      <div class="sub-panel__head"><strong>新建订阅 / 洗版</strong><span>媒体库已有则自动归类为洗版，否则为订阅。</span></div>
      <div class="sub-form-grid">
        <label><span>番号</span><input data-field="code" placeholder="DASS-927" value="${esc(state.form.code)}"></label>
        <label><span>标题</span><input data-field="title" placeholder="可选" value="${esc(state.form.title)}"></label>
        <label><span>模式</span><select data-field="mode"><option value="loose">宽松订阅</option><option value="strict">严格订阅</option></select></label>
        <div class="sub-checks">
          <label><input data-field="require_cracked" type="checkbox" ${state.form.require_cracked ? 'checked' : ''}> 破解</label>
          <label><input data-field="require_subtitle" type="checkbox" ${state.form.require_subtitle ? 'checked' : ''}> 中字</label>
        </div>
      </div>
      <div class="sub-form-actions"><button data-action="save" type="button">保存订阅</button></div>
    `
    panel.querySelector('[data-field="mode"]').value = state.form.mode
    panel.querySelectorAll('[data-field]').forEach(input => {
      input.oninput = input.onchange = () => {
        const key = input.dataset.field
        state.form[key] = input.type === 'checkbox' ? input.checked : input.value
      }
    })
    panel.querySelector('[data-action="save"]').onclick = createSubscription
    host.appendChild(panel)
  }

  function itemBadges(item) {
    const out = []
    out.push(badge(item.type === 'upgrade' ? '洗版' : '订阅', item.type === 'upgrade' ? 'warning' : 'primary'))
    out.push(badge(item.mode === 'strict' ? '严格' : '宽松', 'info'))
    if (item.require_cracked) out.push(badge('破解', 'warning'))
    if (item.require_subtitle) out.push(badge('中字', 'success'))
    if (item.status === 'matched') out.push(badge('已匹配', 'success'))
    else if (item.status === 'active') out.push(badge('监控中', 'info'))
    return out
  }

  function renderItems() {
    const host = $('items')
    host.innerHTML = ''
    if (state.loading) {
      host.append(h('div', 'sub-empty', '加载订阅中…'))
      return
    }
    if (!state.items.length) {
      host.append(h('div', 'sub-empty', '暂无订阅。可以从 JavDB 作品页接入，或在这里手动新建番号订阅。'))
      return
    }
    for (const item of state.items) {
      const card = h('article', 'sub-card')
      const best = item.best_resource || null
      card.innerHTML = `
        <div class="sub-card__main">
          <div class="sub-card__title"><strong>${esc(item.code)}</strong><span>${esc(item.title || '')}</span></div>
          <div class="sub-card__badges"></div>
          <div class="sub-card__meta">上次检测：${fmtDate(item.last_checked_at)}${item.current_file_path ? ` · 当前：${esc(item.current_file_path)}` : ''}</div>
          ${best ? `<div class="sub-best"><strong>最佳候选</strong><span>${esc(best.provider_label || best.provider)} · ${esc(best.title || '')} · ${fmtSize(best.size_bytes)} · ${best.score || 0} 分</span></div>` : '<div class="sub-best is-empty">暂无匹配资源</div>'}
        </div>
        <div class="sub-card__actions"><button data-action="check" type="button">检测</button><button data-action="delete" type="button">删除</button></div>
      `
      const bHost = card.querySelector('.sub-card__badges')
      itemBadges(item).forEach(x => bHost.appendChild(x))
      card.querySelector('[data-action="check"]').onclick = () => checkOne(item.id)
      card.querySelector('[data-action="delete"]').onclick = () => deleteOne(item.id)
      host.appendChild(card)
    }
  }

  function renderEvents() {
    const host = $('events')
    host.innerHTML = '<div class="sub-events__head">最近事件</div>'
    if (!state.events.length) {
      host.append(h('div', 'sub-events__empty', '暂无事件'))
      return
    }
    for (const ev of state.events.slice(0, 20)) {
      const row = h('div', `sub-event is-${ev.level || 'info'}`)
      row.innerHTML = `<span>${fmtDate(ev.created_at)}</span><strong>${esc(ev.message || '')}</strong>`
      host.appendChild(row)
    }
  }

  function render() {
    renderTopbar()
    renderNotice()
    renderForm()
    renderItems()
    renderEvents()
  }

  async function load() {
    state.loading = true
    state.error = ''
    render()
    try {
      const data = await apiPost('overview')
      state.stats = data.stats || {}
      state.items = data.items || []
      state.events = data.events || []
    } catch (e) {
      state.error = e?.message || '读取订阅失败'
    } finally {
      state.loading = false
      render()
    }
  }

  async function createSubscription() {
    try {
      const data = await apiPost('create', state.form)
      state.formOpen = false
      state.form = { code: '', title: '', mode: 'loose', require_cracked: false, require_subtitle: false }
      notify('success', data.created ? '订阅已创建' : '订阅已存在')
      await load()
    } catch (e) {
      notify('error', e?.message || '创建失败')
    }
  }

  async function checkAll() {
    state.checking = true
    renderTopbar()
    try {
      await apiPost('check_once')
      notify('success', '检测完成')
      await load()
    } catch (e) {
      notify('error', e?.message || '检测失败')
    } finally {
      state.checking = false
      renderTopbar()
    }
  }

  async function checkOne(id) {
    try {
      await apiPost('check_once', { id })
      notify('success', '检测完成')
      await load()
    } catch (e) {
      notify('error', e?.message || '检测失败')
    }
  }

  async function deleteOne(id) {
    try {
      await apiPost('delete', { id })
      notify('success', '订阅已删除')
      await load()
    } catch (e) {
      notify('error', e?.message || '删除失败')
    }
  }

  await load()
  return () => {}
}
