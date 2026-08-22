function el(tag, className = '', text = '') {
  const node = document.createElement(tag)
  if (className) node.className = className
  if (text) node.textContent = text
  return node
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>'"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[c]))
}

function fmtSizeMb(value) {
  const mb = Number(value || 0)
  if (!Number.isFinite(mb) || mb <= 0) return ''
  if (mb >= 1024) return `${(mb / 1024).toFixed(1)}GB`
  return `${Math.round(mb)}MB`
}

function fmtBytes(value) {
  const bytes = Number(value || 0)
  if (!Number.isFinite(bytes) || bytes <= 0) return ''
  return fmtSizeMb(bytes / 1024 / 1024)
}

function badge(label, tone = 'neutral') {
  const b = el('span', `av-rec-badge av-rec-badge--${tone}`, label)
  return b
}

function scoreTone(score) {
  if (score >= 80) return 'hot'
  if (score >= 60) return 'good'
  return 'neutral'
}

export async function mount(root, sdk) {
  const state = {
    mode: 'all',
    loading: false,
    error: '',
    data: null,
  }

  root.innerHTML = ''
  const page = el('div', 'av-rec-page')
  const topbar = el('div', 'av-rec-topbar')
  const title = el('div', 'av-rec-title')
  title.innerHTML = '<strong>AV 推荐中心</strong><span>根据媒体库偏好、JavDB 候选和资源可用性生成推荐</span>'
  const actions = el('div', 'av-rec-actions')
  const modeWrap = el('div', 'av-rec-modes')
  const refreshBtn = sdk.ui?.button ? sdk.ui.button({ label: '刷新推荐', tone: 'primary', onClick: () => load(true) }) : el('button', 'av-rec-btn', '刷新推荐')
  if (!sdk.ui?.button) refreshBtn.onclick = () => load(true)
  actions.append(modeWrap, refreshBtn)
  topbar.append(title, actions)
  const profile = el('div', 'av-rec-profile')
  const notice = el('div', 'av-rec-notice')
  const grid = el('div', 'av-rec-grid')
  page.append(topbar, profile, notice, grid)
  root.appendChild(page)

  function renderModes() {
    modeWrap.innerHTML = ''
    const modes = [
      ['all', '全部'],
      ['subscribe', '订阅推荐'],
      ['upgrade', '洗版推荐'],
    ]
    for (const [value, label] of modes) {
      const btn = el('button', 'av-rec-mode' + (state.mode === value ? ' is-active' : ''), label)
      btn.onclick = () => {
        if (state.mode === value) return
        state.mode = value
        load(false)
      }
      modeWrap.appendChild(btn)
    }
  }

  function renderProfile() {
    const data = state.data || {}
    const p = data.profile || {}
    const stats = data.stats || {}
    profile.innerHTML = ''
    const cards = [
      ['媒体库', p.media_count || 0, '已分析作品'],
      ['番号', p.code_count || 0, '可识别番号'],
      ['候选', stats.candidates || 0, '本轮扫描'],
      ['订阅', stats.subscribe || 0, '未入库推荐'],
      ['洗版', stats.upgrade || 0, '已入库升级'],
    ]
    for (const [name, value, desc] of cards) {
      const card = el('div', 'av-rec-stat')
      card.innerHTML = `<span>${escapeHtml(name)}</span><strong>${escapeHtml(value)}</strong><em>${escapeHtml(desc)}</em>`
      profile.appendChild(card)
    }
    const prefs = el('div', 'av-rec-prefs')
    const groups = [
      ['演员', p.top_actors || []],
      ['类型', p.top_genres || []],
      ['标签', p.top_tags || []],
    ]
    for (const [label, items] of groups) {
      const group = el('div', 'av-rec-pref-group')
      group.appendChild(el('span', '', label))
      const chips = el('div')
      for (const item of items.slice(0, 8)) chips.appendChild(badge(`${item.name} ${item.count}`, 'soft'))
      if (!items.length) chips.appendChild(badge('暂无', 'muted'))
      group.appendChild(chips)
      prefs.appendChild(group)
    }
    profile.appendChild(prefs)
  }

  function renderNotice() {
    notice.innerHTML = ''
    if (state.loading) {
      notice.className = 'av-rec-notice is-loading'
      notice.textContent = '正在读取媒体库偏好与 JavDB 候选…'
      return
    }
    if (state.error) {
      notice.className = 'av-rec-notice is-error'
      notice.textContent = state.error
      return
    }
    const warnings = state.data?.warnings || []
    if (warnings.length) {
      notice.className = 'av-rec-notice is-warning'
      notice.textContent = warnings[0]
      return
    }
    notice.className = 'av-rec-notice'
    notice.textContent = ''
  }

  function skeleton() {
    grid.innerHTML = ''
    for (let i = 0; i < 8; i++) {
      const card = el('div', 'av-rec-card av-rec-skeleton')
      card.innerHTML = '<div></div><section><b></b><p></p><p></p></section>'
      grid.appendChild(card)
    }
  }

  async function feedback(item, kind) {
    try {
      await sdk.api.post('/plugins/av-recommend/actions/feedback', {
        payload: {
          code: item.code,
          kind,
          actors: item.actors || [],
          categories: item.categories || [],
        },
      })
      sdk.toast?.success(kind === 'ignore' ? '已忽略' : kind === 'like' ? '已标记喜欢' : '已标记不感兴趣')
      await load(true)
    } catch (e) {
      sdk.toast?.error(e?.response?.data?.detail || e?.message || '操作失败')
    }
  }

  function openDislikePicker(item) {
    const mask = el('div', 'av-rec-feedback-mask')
    const modal = el('div', 'av-rec-feedback-modal')
    mask.appendChild(modal)
    const tags = [
      ...(item.actors || []).map(name => ({ type: 'actor', label: name })),
      ...(item.categories || []).map(name => ({ type: 'category', label: name })),
    ].filter(x => x.label)
    const selected = new Set()
    modal.innerHTML = `
      <div class="av-rec-feedback-head">
        <strong>不感兴趣的点</strong>
        <button type="button" data-action="close">×</button>
      </div>
      <div class="av-rec-feedback-body">
        <p>不选标签则只隐藏这部作品；勾选标签后，后续相似推荐会降权。</p>
        <div class="av-rec-feedback-tags"></div>
      </div>
      <div class="av-rec-feedback-actions">
        <button type="button" data-action="cancel">取消</button>
        <button type="button" data-action="save" class="is-primary">确认</button>
      </div>
    `
    const close = () => mask.remove()
    mask.onclick = event => { if (event.target === mask) close() }
    modal.querySelector('[data-action="close"]').onclick = close
    modal.querySelector('[data-action="cancel"]').onclick = close
    const tagHost = modal.querySelector('.av-rec-feedback-tags')
    const seen = new Set()
    for (const tag of tags) {
      const key = `${tag.type}:${tag.label}`
      if (seen.has(key)) continue
      seen.add(key)
      const btn = el('button', `av-rec-feedback-tag av-rec-feedback-tag--${tag.type}`)
      btn.type = 'button'
      btn.textContent = tag.label
      btn.onclick = () => {
        if (selected.has(key)) selected.delete(key)
        else selected.add(key)
        btn.classList.toggle('is-active', selected.has(key))
      }
      tagHost.appendChild(btn)
    }
    if (!seen.size) tagHost.appendChild(el('span', 'av-rec-feedback-empty', '这部作品没有可用演员/类型标签'))
    modal.querySelector('[data-action="save"]').onclick = async () => {
      const actors = []
      const categories = []
      for (const key of selected) {
        const [type, ...rest] = String(key).split(':')
        const label = rest.join(':')
        if (type === 'actor') actors.push(label)
        else if (type === 'category') categories.push(label)
      }
      close()
      await feedback({ ...item, actors, categories }, 'dislike')
    }
    document.body.appendChild(mask)
  }

  function openJavDB(item) {
    const code = encodeURIComponent(item.code || '')
    if (code) window.location.href = `/plugins/javdb?code=${code}`
  }

  async function openSubscription(item) {
    try {
      await sdk.subscription?.open({
        code: item.code,
        title: item.title || item.display_title || item.code,
        cover_url: item.cover_url || item.fanart_url || '',
        fanart_url: item.fanart_url || item.cover_url || '',
        sourcePlugin: 'av-recommend',
        sourceLabel: '推荐中心',
        sourceContext: item.type === 'upgrade' ? 'recommend-upgrade' : 'recommend-subscribe',
        defaultMode: 'loose',
        requireCracked: !!item.is_cracked,
        requireSubtitle: !!item.has_cnsub,
        onSuccess: () => sdk.toast?.success(item.type === 'upgrade' ? '已加入洗版' : '已加入订阅'),
      })
    } catch (e) {
      sdk.toast?.error(e?.message || '订阅失败')
    }
  }

  function renderItems() {
    if (state.loading && !state.data) return skeleton()
    grid.innerHTML = ''
    const items = state.data?.items || []
    if (!items.length) {
      const empty = el('div', 'av-rec-empty')
      empty.innerHTML = '<strong>暂无推荐</strong><span>可以先重建 AV 图谱/Knowledge Core，或确认 JavDB 插件已启用。</span>'
      grid.appendChild(empty)
      return
    }
    for (const item of items) {
      const card = el('article', 'av-rec-card')
      const image = el('button', 'av-rec-cover')
      image.type = 'button'
      image.onclick = () => openJavDB(item)
      if (item.fanart_url || item.cover_url) image.innerHTML = `<img src="${escapeHtml(item.fanart_url || item.cover_url)}" loading="lazy" alt="">`
      else image.textContent = item.code || 'NO IMAGE'
      const body = el('section', 'av-rec-body')
      const head = el('div', 'av-rec-card-head')
      const title = el('button', 'av-rec-card-title')
      title.type = 'button'
      title.onclick = () => openJavDB(item)
      title.innerHTML = `<strong>${escapeHtml(item.code)}</strong><span>${escapeHtml(item.title || '')}</span>`
      const score = el('div', `av-rec-score av-rec-score--${scoreTone(item.score)}`)
      score.innerHTML = `<strong>${escapeHtml(item.score)}</strong><span>推荐分</span>`
      head.append(title, score)
      const meta = el('div', 'av-rec-meta')
      if (item.release_date) meta.appendChild(badge(item.release_date, 'muted'))
      meta.appendChild(badge(item.type === 'upgrade' ? '洗版' : '订阅', item.type === 'upgrade' ? 'warn' : 'info'))
      if (item.in_library) meta.appendChild(badge('已入库', 'good'))
      if (item.magnets_count) meta.appendChild(badge(`${item.magnets_count} 磁链`, 'good'))
      const resourceSummary = item.resource_summary || {}
      if (resourceSummary.total) meta.appendChild(badge(`${resourceSummary.total} 资源`, 'info'))
      if (item.has_cnsub) meta.appendChild(badge('中字', 'good'))
      if (item.is_cracked) meta.appendChild(badge('破解', 'hot'))
      const size = fmtSizeMb(item.best_resource_size_mb) || fmtBytes(resourceSummary.best_size_bytes)
      if (size) meta.appendChild(badge(size, 'soft'))
      const people = el('div', 'av-rec-tags')
      if (item.personalized_score) people.appendChild(badge(`偏好 ${Math.round(item.personalized_score)}`, 'hot'))
      if (item.confidence) people.appendChild(badge(`置信 ${Math.round(item.confidence)}`, 'good'))
      if (item.match_level === 'strong') people.appendChild(badge('强匹配', 'hot'))
      else if (item.match_level === 'medium') people.appendChild(badge('中匹配', 'good'))
      else if (item.match_level === 'weak') people.appendChild(badge('弱匹配', 'soft'))
      for (const source of (resourceSummary.providers || []).slice(0, 3)) people.appendChild(badge(`${source.name}×${source.count}`, 'info'))
      for (const name of (item.actors || []).slice(0, 4)) people.appendChild(badge(name, 'soft'))
      for (const name of (item.categories || []).slice(0, 5)) people.appendChild(badge(name, 'muted'))
      const breakdown = item.score_breakdown || {}
      const scoreParts = el('div', 'av-rec-score-parts')
      const scorePartValues = [
        ['偏好', breakdown.preference],
        ['资源', breakdown.resources],
        ['质量', breakdown.quality],
        ['降权', breakdown.penalty ? `-${Math.round(breakdown.penalty)}` : '0'],
      ]
      for (const [label, value] of scorePartValues) {
        const part = el('span')
        part.innerHTML = `<em>${escapeHtml(label)}</em><strong>${escapeHtml(value == null || value === '' ? 0 : Math.round(Number(value) || 0))}</strong>`
        scoreParts.appendChild(part)
      }
      const reasons = el('ul', 'av-rec-reasons')
      for (const reason of item.reasons || []) {
        const li = document.createElement('li')
        li.textContent = reason
        reasons.appendChild(li)
      }
      const buttons = el('div', 'av-rec-card-actions')
      const subBtn = el('button', 'av-rec-primary', item.type === 'upgrade' ? '洗版' : '订阅')
      subBtn.onclick = () => openSubscription(item)
      const viewBtn = el('button', '', 'JavDB')
      viewBtn.onclick = () => openJavDB(item)
      const likeBtn = el('button', '', '喜欢')
      likeBtn.onclick = () => feedback(item, 'like')
      const dislikeBtn = el('button', '', '不感兴趣')
      dislikeBtn.onclick = () => openDislikePicker(item)
      const ignoreBtn = el('button', '', '忽略')
      ignoreBtn.onclick = () => feedback(item, 'ignore')
      buttons.append(subBtn, viewBtn, likeBtn, dislikeBtn, ignoreBtn)
      body.append(head, meta, people, scoreParts, reasons, buttons)
      card.append(image, body)
      grid.appendChild(card)
    }
  }

  function render() {
    renderModes()
    renderProfile()
    renderNotice()
    renderItems()
  }

  async function load(refresh = false) {
    state.loading = true
    state.error = ''
    render()
    try {
      const resp = await sdk.api.post('/plugins/av-recommend/actions/recommendations', {
        payload: { mode: state.mode, limit: 60, refresh },
      })
      state.data = resp.data
    } catch (e) {
      state.error = e?.response?.data?.detail || e?.message || '推荐加载失败'
    } finally {
      state.loading = false
      render()
    }
  }

  await load(false)
}

