function el(tag, className = '', text = '') {
  const node = document.createElement(tag)
  if (className) node.className = className
  if (text) node.textContent = text
  return node
}

function typeLabel(type) {
  return {
    media_item: '作品',
    torrent: '种子',
    video_code: '番号',
    actor: '演员',
    studio: '片商',
    label: '厂牌',
    series: '系列',
    director: '导演',
    genre: '类型',
    file_version: '版本',
    subtitle: '字幕',
    task: '任务',
  }[type] || type
}

function relationLabel(type) {
  return {
    HAS_CODE: '番号',
    HAS_ACTOR: '演员',
    HAS_STUDIO: '片商',
    HAS_LABEL: '厂牌',
    IN_SERIES: '系列',
    HAS_DIRECTOR: '导演',
    HAS_GENRE: '类型',
    HAS_VERSION: '版本',
    HAS_SUBTITLE: '字幕',
    HAS_TASK: '任务',
    HAS_TORRENT_CANDIDATE: '可下载',
  }[type] || type
}

function contextualRelationLabel(edge, entity, other) {
  if (!edge || !entity || !other) return relationLabel(edge?.relation_type)
  const currentIsTarget = edge.target_entity_id === entity.id
  const currentIsSource = edge.source_entity_id === entity.id
  if (currentIsTarget && other.type === 'media_item') return '作品'
  if (currentIsSource && edge.relation_type === 'HAS_TORRENT_CANDIDATE') return '候选'
  if (currentIsSource && other.type === 'media_item') return '作品'
  return relationLabel(edge.relation_type)
}

function scoreText(scores) {
  const score = (scores || []).find(item => item.type === 'library_quality')
  return score ? `${score.value}/100` : '暂无'
}

function formatBytes(value) {
  const bytes = Number(value || 0)
  if (!Number.isFinite(bytes) || bytes <= 0) return ''
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let size = bytes
  let idx = 0
  while (size >= 1024 && idx < units.length - 1) {
    size /= 1024
    idx += 1
  }
  return `${size.toFixed(idx === 0 ? 0 : 1)} ${units[idx]}`
}


function discountLabel(value) {
  const raw = String(value || '').trim()
  if (!raw) return ''
  const upper = raw.toUpperCase()
  if (upper === 'FREE') return '免费'
  if (upper === 'DOUBLE_FREE' || upper === 'FREE_2X' || upper === 'TWO_X_FREE') return '2X 免费'
  const percent = upper.match(/^PERCENT[_-]?(\d+)$/)
  if (percent) return `${percent[1]}%`
  return raw.replace(/_/g, ' ')
}

function torrentBadges(entity) {
  const data = entity?.data || {}
  const badges = []
  const labels = Array.isArray(data.labels) ? data.labels.filter(Boolean) : []
  for (const label of labels.slice(0, 3)) badges.push({ label, tone: /中字|中文|字幕/i.test(label) ? 'good' : 'neutral' })
  const discount = discountLabel(data.discount)
  if (discount) badges.push({ label: discount, tone: /免费/i.test(discount) ? 'good' : 'info' })
  if (data.download_available || data.download_token_available) badges.push({ label: '可推送', tone: 'info' })
  return badges
}

function torrentMeta(entity) {
  const data = entity?.data || {}
  const parts = []
  if (data.code) parts.push(data.code)
  const labels = Array.isArray(data.labels) ? data.labels.filter(Boolean) : []
  if (labels.length) parts.push(labels.slice(0, 2).join('/'))
  const size = formatBytes(data.size_bytes)
  if (size) parts.push(size)
  if (data.seeders) parts.push(`${data.seeders} 做种`)
  if (data.times_completed) parts.push(`${data.times_completed} 完成`)
  if (data.discount) parts.push(discountLabel(data.discount))
  if (data.download_available || data.download_token_available) parts.push('可推送')
  else if (data.link) parts.push('可查看来源')
  return parts.join(' · ')
}

function candidateScore(entity, edge = null) {
  const edgeScore = Number(edge?.data?.candidate_score)
  if (Number.isFinite(edgeScore) && edgeScore > 0) return edgeScore
  const data = entity?.data || {}
  const labels = Array.isArray(data.labels) ? data.labels.join(' ') : ''
  const hasChinese = /中字|中文|字幕/i.test(labels) || /中字|中文/.test(String(entity?.label || ''))
  const seeders = Number(data.seeders || 0)
  const completed = Number(data.times_completed || 0)
  const sizeGb = Number(data.size_bytes || 0) / 1024 / 1024 / 1024
  const discount = String(data.discount || '')
  const freeBoost = /FREE/.test(discount) ? 80 : /PERCENT_50/.test(discount) ? 30 : /PERCENT_70/.test(discount) ? 15 : 0
  return (hasChinese ? 1000 : 0)
    + Math.min(seeders, 300) * 2
    + Math.min(completed, 5000) / 20
    + Math.min(sizeGb, 30)
    + freeBoost
}

function sourceLink(entity) {
  const link = String(entity?.data?.link || '')
  return link.startsWith('http://') || link.startsWith('https://') ? link : ''
}

function edgeCandidateText(edge) {
  const score = Number(edge?.data?.candidate_score || 0)
  const reasons = Array.isArray(edge?.data?.candidate_reasons) ? edge.data.candidate_reasons.filter(Boolean) : []
  const parts = []
  if (score) parts.push(`匹配 ${score}`)
  if (reasons.length) parts.push(reasons.slice(0, 3).join(' / '))
  return parts.join(' · ')
}


function graphColor(type) {
  return {
    media_item: '#3b82f6',
    torrent: '#22c55e',
    video_code: '#f59e0b',
    actor: '#ec4899',
    studio: '#8b5cf6',
    series: '#06b6d4',
    genre: '#64748b',
    subtitle: '#10b981',
    task: '#f97316',
    file_version: '#94a3b8',
  }[type] || '#64748b'
}

function svgEl(tag, attrs = {}) {
  const node = document.createElementNS('http://www.w3.org/2000/svg', tag)
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, String(value))
  return node
}

export async function mount(root, sdk) {
  let state = {
    downloadDialog: { open: false, item: null, name: '', savepath: '', category: '', options: null },
    query: '',
    type: '',
    filter: '',
    results: [],
    actionables: { missing: [], high: [], multi: [] },
    actionStates: [],
    clusters: [],
    graph: null,
    graphLoading: false,
    graphDepth: 1,
    graphTypeFilter: new Set(['media_item', 'torrent', 'video_code', 'actor', 'studio', 'series', 'subtitle', 'file_version']),
    memberFilter: 'all',
    selected: null,
    detail: null,
    stats: null,
    rebuild: null,
    loading: false,
    pushing: new Set(),
    pushProgress: {},
  }
  let disposed = false

  root.innerHTML = ''
  const page = el('div', 'av-graph')
  const topbar = el('div', 'av-graph__topbar')
  const search = sdk.ui.input({ placeholder: '搜索番号、演员、片商、系列...', className: 'av-graph__search' })
  const typeSelect = sdk.ui.select({
    value: '',
    options: [
      { label: '全部', value: '' },
      { label: '作品', value: 'media_item' },
      { label: '种子', value: 'torrent' },
      { label: '番号', value: 'video_code' },
      { label: '演员', value: 'actor' },
      { label: '片商', value: 'studio' },
      { label: '系列', value: 'series' },
      { label: '字幕', value: 'subtitle' },
    ],
    onChange: value => {
      state.type = value
      loadSearch()
    },
  })
  const filterSelect = sdk.ui.select({
    value: '',
    options: [
      { label: '全部状态', value: '' },
      { label: '有下载候选', value: 'has_torrent_candidate' },
      { label: '有洞察', value: 'has_anomaly' },
      { label: '缺字幕', value: 'missing_subtitle' },
      { label: '缺字幕可下载', value: 'missing_subtitle_with_candidate' },
    ],
    onChange: value => {
      state.filter = value
      state.selected = null
      state.detail = null

    },
  })
  const smartFilterBtn = sdk.ui.button({
    label: '缺字幕可下载',
    onClick: () => {
      state.type = 'media_item'
      state.filter = 'missing_subtitle_with_candidate'
      state.selected = null
      state.detail = null
      typeSelect.value = state.type
      filterSelect.value = state.filter
      loadSearch()
    }
  })

  const rebuildBtn = sdk.ui.submitButton({
    label: '重建索引',
    idleLabel: '重建索引',
    successLabel: '已重建',
    errorLabel: '失败',
    onClick: async () => {
      rebuildBtn.__setState('running', 8, '提交中')
      try {
        const response = await sdk.api.post('/knowledge/rebuild', {})
        const runId = response.data?.run_id
        rebuildBtn.__setState('running', 12, response.data?.accepted === false ? '重建中' : '已提交')
        await pollRebuildStatus(runId)
      } catch (error) {
        rebuildBtn.__setState('error', 100, '重建失败')
        sdk.toast.error(error?.response?.data?.detail || error?.message || '重建失败')
      }
    },
  })
  const rebuildStatus = el('div', 'av-graph__rebuild-status')
  topbar.append(search, typeSelect, filterSelect, smartFilterBtn, rebuildBtn, rebuildStatus)

  const statsRow = el('div', 'av-graph__stats')
  const graphPanel = el('div', 'av-graph__graph-panel')
  const clusterPanel = el('div', 'av-graph__clusters')
  const actionRow = el('div', 'av-graph__actionables')
  const layout = el('div', 'av-graph__layout')
  const list = el('div', 'av-graph__list')
  const detail = el('div', 'av-graph__detail')
  layout.append(list, detail)
  page.append(topbar, statsRow, graphPanel, clusterPanel, actionRow, layout)
  root.appendChild(page)

  let timer = 0
  search.oninput = () => {
    state.query = search.value
    clearTimeout(timer)
    timer = setTimeout(loadSearch, 220)
  }

  function renderStats() {
    statsRow.innerHTML = ''
    const stats = state.stats || {}
    const entities = stats.entities || {}
    const pendingCount = new Set([
      ...(state.actionables.missing || []).map(item => item.media?.id).filter(Boolean),
      ...(state.actionables.high || []).map(item => item.media?.id).filter(Boolean),
      ...(state.actionables.multi || []).map(item => item.media?.id).filter(Boolean),
    ]).size
    const actionStats = stats.actions || {}
    const processedCount = Number(actionStats.download_pushed?.done || 0) + Number(actionStats.actionable_hidden?.hidden || 0)
    const cells = [
      ['作品', entities.media_item || 0],
      ['种子', entities.torrent || 0],
      ['可下载', (stats.edges || {}).HAS_TORRENT_CANDIDATE || 0],
      ['待处理', pendingCount],
      ['已处理', processedCount],
    ]
    for (const [label, value] of cells) {
      const card = el('div', 'av-graph__stat')
      card.append(el('span', 'av-graph__stat-label', label), el('strong', 'av-graph__stat-value', String(value)))
      statsRow.appendChild(card)
    }
  }

  function renderRebuildStatus() {
    const run = state.rebuild?.run
    if (!run) {
      rebuildStatus.textContent = ''
      rebuildStatus.className = 'av-graph__rebuild-status'
      return
    }
    const stats = run.stats || {}
    const phase = {
      queued: '排队中',
      preparing: '准备中',
      'media-library': '媒体库',
      jobs: '任务历史',
      finalizing: '收尾',
      completed: '已完成',
      failed: '失败',
    }[stats.phase || run.status] || run.status
    rebuildStatus.textContent = `${phase}${Number.isFinite(stats.percent) ? ` · ${stats.percent}%` : ''}`
    rebuildStatus.className = `av-graph__rebuild-status av-graph__rebuild-status--${run.status}`
  }



  function renderGraph() {
    graphPanel.innerHTML = ''
    const head = el('div', 'av-graph__graph-head')
    const titleBox = el('div')
    titleBox.append(
      el('div', 'av-graph__graph-title', '关系网络'),
      el('div', 'av-graph__graph-subtitle', '以当前节点为中心展示关系，点击节点继续探索'),
    )
    const controls = el('div', 'av-graph__graph-controls')
    const depthOne = el('button', `av-graph__graph-chip${state.graphDepth === 1 ? ' is-active' : ''}`, '一跳')
    const depthTwo = el('button', `av-graph__graph-chip${state.graphDepth === 2 ? ' is-active' : ''}`, '二跳')
    depthOne.type = 'button'
    depthTwo.type = 'button'
    depthOne.onclick = () => {
      if (state.graphDepth === 1) return
      state.graphDepth = 1
      loadGraph(state.selected)
    }
    depthTwo.onclick = () => {
      if (state.graphDepth === 2) return
      state.graphDepth = 2
      loadGraph(state.selected)
    }
    controls.append(depthOne, depthTwo)
    head.append(
      titleBox,
      controls,
    )
    graphPanel.appendChild(head)
    if (state.graphLoading) {
      graphPanel.append(sdk.ui.skeletonCard({ className: 'av-graph__graph-skeleton' }))
      return
    }
    const graph = state.graph
    const rawNodes = graph?.entities || []
    const rawEdges = graph?.edges || []
    if (!rawNodes.length) {
      graphPanel.append(sdk.ui.emptyState({ text: '选择作品、演员、片商或种子后查看关系网络' }))
      return
    }
    const centerId = graph.center?.id || rawNodes[0]?.id
    const allowedTypes = state.graphTypeFilter
    const nodes = rawNodes.filter(node => node.id === centerId || allowedTypes.has(node.type))
    const visibleIds = new Set(nodes.map(node => node.id))
    const edges = rawEdges.filter(edge => visibleIds.has(edge.source_entity_id) && visibleIds.has(edge.target_entity_id))

    const filterRow = el('div', 'av-graph__graph-filters')
    const filterTypes = ['media_item', 'torrent', 'video_code', 'actor', 'studio', 'series', 'genre', 'subtitle', 'file_version', 'task']
    for (const type of filterTypes) {
      const chip = el('button', `av-graph__graph-type${allowedTypes.has(type) ? ' is-active' : ''}`, typeLabel(type))
      chip.type = 'button'
      const dot = el('i')
      dot.style.background = graphColor(type)
      chip.prepend(dot)
      chip.onclick = () => {
        const next = new Set(state.graphTypeFilter)
        if (next.has(type)) next.delete(type)
        else next.add(type)
        state.graphTypeFilter = next
        renderGraph()
      }
      filterRow.appendChild(chip)
    }
    graphPanel.appendChild(filterRow)
    const analysis = el('div', 'av-graph__graph-analysis')
    const nodeTypes = new Set(nodes.map(node => node.type))
    const candidateEdges = edges.filter(edge => edge.relation_type === 'HAS_TORRENT_CANDIDATE').length
    const subtitles = nodes.filter(node => node.type === 'subtitle').length
    const torrents = nodes.filter(node => node.type === 'torrent').length
    const actors = nodes.filter(node => node.type === 'actor').length
    const studios = nodes.filter(node => node.type === 'studio').length
    const centerLabel = graph.center ? `${typeLabel(graph.center.type)} · ${graph.center.label || graph.center.key}` : '未选中'
    const summaryItems = [
      ['中心', centerLabel],
      ['节点', `${nodes.length} / ${rawNodes.length}`],
      ['关系', `${edges.length} / ${rawEdges.length}`],
      ['类型', `${nodeTypes.size}`],
      ['候选', `${candidateEdges || torrents}`],
      ['字幕', `${subtitles}`],
      ['演员/片商', `${actors}/${studios}`],
    ]
    for (const [label, value] of summaryItems) {
      const item = el('span', 'av-graph__graph-analysis-item')
      item.append(el('em', '', label), document.createTextNode(String(value)))
      analysis.appendChild(item)
    }
    graphPanel.appendChild(analysis)
    if (!nodes.length) {
      graphPanel.append(sdk.ui.emptyState({ text: '当前筛选没有可显示节点' }))
      return
    }

    const width = 960
    const height = 420
    const cx = width / 2
    const cy = height / 2
    const center = nodes.find(node => node.id === centerId) || nodes[0]
    const others = nodes.filter(node => node.id !== center.id).slice(0, 34)
    const positions = new Map([[center.id, { x: cx, y: cy }]])
    const buckets = new Map()
    for (const node of others) {
      const list = buckets.get(node.type) || []
      list.push(node)
      buckets.set(node.type, list)
    }
    const ordered = Array.from(buckets.entries()).flatMap(([, list]) => list)
    ordered.forEach((node, index) => {
      const angle = (Math.PI * 2 * index) / Math.max(ordered.length, 1) - Math.PI / 2
      const ring = 130 + (index % 3) * 42
      positions.set(node.id, { x: cx + Math.cos(angle) * ring, y: cy + Math.sin(angle) * ring })
    })

    const svg = svgEl('svg', { viewBox: `0 0 ${width} ${height}`, class: 'av-graph__svg', role: 'img' })
    const edgeLayer = svgEl('g', { class: 'av-graph__svg-edges' })
    const nodeLayer = svgEl('g', { class: 'av-graph__svg-nodes' })
    svg.append(edgeLayer, nodeLayer)

    for (const edge of edges) {
      const a = positions.get(edge.source_entity_id)
      const b = positions.get(edge.target_entity_id)
      if (!a || !b) continue
      const line = svgEl('line', { x1: a.x, y1: a.y, x2: b.x, y2: b.y, class: 'av-graph__svg-edge' })
      edgeLayer.appendChild(line)
      const mx = (a.x + b.x) / 2
      const my = (a.y + b.y) / 2
      const text = svgEl('text', { x: mx, y: my - 4, class: 'av-graph__svg-edge-label' })
      text.textContent = relationLabel(edge.relation_type)
      edgeLayer.appendChild(text)
    }

    for (const node of nodes.filter(node => positions.has(node.id))) {
      const pos = positions.get(node.id)
      const g = svgEl('g', { class: `av-graph__svg-node${node.id === center.id ? ' is-center' : ''}` })
      g.style.cursor = 'pointer'
      g.addEventListener('click', () => selectEntity(node))
      const color = graphColor(node.type)
      g.appendChild(svgEl('circle', { cx: pos.x, cy: pos.y, r: node.id === center.id ? 25 : 17, fill: color }))
      const label = String(node.label || node.key || '').slice(0, node.id === center.id ? 24 : 16)
      const text = svgEl('text', { x: pos.x, y: pos.y + (node.id === center.id ? 43 : 34), class: 'av-graph__svg-node-label' })
      text.textContent = label
      g.appendChild(text)
      const typeText = svgEl('text', { x: pos.x, y: pos.y + 4, class: 'av-graph__svg-node-type' })
      typeText.textContent = typeLabel(node.type)
      g.appendChild(typeText)
      nodeLayer.appendChild(g)
    }

    const legend = el('div', 'av-graph__graph-legend')
    for (const type of ['media_item', 'actor', 'studio', 'series', 'torrent', 'subtitle', 'task']) {
      const item = el('span', 'av-graph__legend-item')
      const dot = el('i')
      dot.style.background = graphColor(type)
      item.append(dot, document.createTextNode(typeLabel(type)))
      legend.appendChild(item)
    }
    graphPanel.append(svg, legend)
  }

  async function hideActionable(media, torrent) {
    if (!media?.id) return
    try {
      await sdk.api.post('/knowledge/actionables/mark', {
        entity_id: media.id,
        action_type: 'actionable_hidden',
        status: 'hidden',
        data: { torrent_id: torrent?.id, torrent_key: torrent?.key, reason: 'manual_hide' },
      })
      if (state.selected?.id === media.id) {
        state.selected = null
        state.detail = null
      }
      await loadActionables()
      render()
    } catch (error) {
      sdk.toast.error(error?.response?.data?.detail || error?.message || '忽略失败')
    }
  }

  function renderActionCard(item) {
    const media = item.media
    const torrent = item.torrent
    const edge = item.edge
    const card = el('div', 'av-graph__action-card')
    const title = el('button', 'av-graph__action-media', media.label)
    title.type = 'button'
    title.onclick = () => selectEntity(media)
    const meta = el('div', 'av-graph__action-meta', edgeCandidateText(edge) || torrentMeta(torrent) || '候选可用')
    const torrentLine = el('div', 'av-graph__action-torrent', torrent.label)
    const actions = el('div', 'av-graph__action-actions')
    actions.appendChild(sdk.ui.button({ label: '查看', onClick: () => selectEntity(media) }))
    actions.appendChild(sdk.ui.button({ label: '忽略', onClick: () => hideActionable(media, torrent) }))
    if (torrent.source === 'mteam-plugin' && extractTorrentId(torrent)) {
      actions.appendChild(sdk.ui.button({ label: '推送', tone: 'primary', onClick: () => openDownloadDialog(torrent, media) }))
    }
    card.append(title, meta, torrentLine, actions)
    return card
  }

  function renderActionLane(title, subtitle, items, seen) {
    const picked = []
    for (const item of items || []) {
      const id = item.media?.id
      if (!id || seen.has(id)) continue
      seen.add(id)
      picked.push(item)
      if (picked.length >= 3) break
    }
    if (!picked.length) return null
    const lane = el('div', 'av-graph__action-lane')
    const head = el('div', 'av-graph__action-head')
    head.append(el('div', 'av-graph__action-title', title), el('div', 'av-graph__action-subtitle', subtitle))
    const grid = el('div', 'av-graph__action-grid')
    for (const item of picked) grid.appendChild(renderActionCard(item))
    lane.append(head, grid)
    return lane
  }


  async function restoreActionState(item) {
    const action = item?.action
    const entity = item?.entity
    if (!action?.entity_id || !action?.action_type) return
    try {
      await sdk.api.post('/knowledge/actionables/mark', {
        entity_id: action.entity_id,
        action_type: action.action_type,
        status: 'restored',
        data: { ...(action.data || {}), restored_at: new Date().toISOString() },
      })
      await loadActionables()
      if (entity?.id) await selectEntity(entity, false)
      render()
    } catch (error) {
      sdk.toast.error(error?.response?.data?.detail || error?.message || '恢复失败')
    }
  }

  function actionTypeLabel(type) {
    return {
      download_pushed: '已推送',
      actionable_hidden: '已忽略',
    }[type] || type
  }

  function renderActionStates() {
    const items = state.actionStates || []
    if (!items.length) return null
    const box = el('div', 'av-graph__processed')
    const head = el('div', 'av-graph__processed-head')
    head.append(el('div', 'av-graph__processed-title', '已处理'), el('div', 'av-graph__processed-subtitle', '最近移出看板的项目，可恢复'))
    const listBox = el('div', 'av-graph__processed-list')
    for (const item of items.slice(0, 6)) {
      const row = el('div', 'av-graph__processed-row')
      row.append(
        el('span', 'av-graph__processed-badge', actionTypeLabel(item.action?.action_type)),
        el('span', 'av-graph__processed-label', item.entity?.label || item.action?.entity_id || ''),
        sdk.ui.button({ label: '恢复', onClick: () => restoreActionState(item) }),
      )
      listBox.appendChild(row)
    }
    box.append(head, listBox)
    return box
  }

  function renderActionables() {
    actionRow.innerHTML = ''
    const seen = new Set()
    const lanes = [
      renderActionLane('待处理 · 缺字幕可下载', '缺本地字幕，但已有可推送候选', state.actionables.missing, seen),
      renderActionLane('高质量候选', '按候选评分排序，可直接补片', state.actionables.high, seen),
      renderActionLane('多版本缺字幕', '版本较多且缺字幕，优先整理', state.actionables.multi, seen),
    ].filter(Boolean)
    const processed = renderActionStates()
    if (!lanes.length && !processed) return
    for (const lane of lanes) actionRow.appendChild(lane)
    if (processed) actionRow.appendChild(processed)
  }

  function renderClusters() {
    clusterPanel.innerHTML = ''
    const items = state.clusters || []
    if (!items.length) return
    const head = el('div', 'av-graph__cluster-panel-head')
    head.append(
      el('div', 'av-graph__cluster-panel-title', '关系聚类'),
      el('div', 'av-graph__cluster-panel-subtitle', '按演员、片商、番号聚合，优先显示缺字幕和可补资源群'),
    )
    const grid = el('div', 'av-graph__cluster-panel-grid')
    for (const item of items.slice(0, 6)) {
      const preferredFilter = Number(item.actionable_count || 0) > 0
        ? 'actionable'
        : Number(item.missing_subtitle_count || 0) > 0
          ? 'missing'
          : 'all'
      const card = el('button', `av-graph__cluster-card${preferredFilter === 'actionable' ? ' is-actionable' : ''}`)
      card.type = 'button'
      card.onclick = () => item.target && selectEntity(item.target, true, { memberFilter: preferredFilter })
      const top = el('div', 'av-graph__cluster-card-top')
      top.append(
        el('span', 'av-graph__cluster-relation', relationLabel(item.relation_type)),
        el('strong', '', item.target?.label || item.target?.key || ''),
      )
      const metrics = el('div', 'av-graph__cluster-card-metrics')
      metrics.append(
        el('span', '', `${item.media_count || 0} 作品`),
        el('span', '', `${item.missing_subtitle_count || 0} 缺字幕`),
        el('span', '', `${item.candidate_count || 0} 有候选`),
        el('span', Number(item.actionable_count || 0) > 0 ? 'is-good' : '', `${item.actionable_count || 0} 缺字幕可补`),
      )
      const samples = el('div', 'av-graph__cluster-card-samples')
      for (const media of (item.media || []).slice(0, 2)) {
        samples.appendChild(el('span', '', media.label || media.key || ''))
      }
      card.append(top, metrics, samples)
      grid.appendChild(card)
    }
    clusterPanel.append(head, grid)
  }

  function renderList() {
    list.innerHTML = ''
    if (state.loading) {
      list.append(sdk.ui.skeletonCard({ className: 'av-graph__skeleton' }))
      return
    }
    if (!state.results.length) {
      list.append(sdk.ui.emptyState({ text: '暂无图谱数据，先重建索引' }))
      return
    }
    for (const item of state.results) {
      const card = el('button', 'av-graph__result')
      card.type = 'button'
      if (state.selected?.id === item.id) card.classList.add('is-active')
      const meta = el('div', 'av-graph__result-meta')
      meta.append(el('span', 'av-graph__badge', typeLabel(item.type)), el('span', 'av-graph__key', item.key))
      card.append(el('div', 'av-graph__result-title', item.label), meta)
      card.onclick = () => selectEntity(item)
      list.appendChild(card)
    }
  }

  let dlOptionsCache = {}
  let activeDownloadModal = null

  function extractTorrentId(entity) {
    if (entity.source === 'mteam-plugin' && entity.key?.startsWith('mteam:')) {
      return parseInt(entity.key.split('mteam:')[1] || 0, 10)
    }
    return 0
  }

  async function openDownloadDialog(torrent, media = null) {
    const tid = extractTorrentId(torrent)
    if (!tid) return
    const k = torrent.id

    try {
      const linkRes = await sdk.api.post('/plugins/mteam-plugin/actions/torrent_download_link', { payload: { torrent_id: tid } })
      const linkData = linkRes.data
      if (!linkData.ok || !linkData.url) throw new Error(linkData.message || '无法获取下载链接')
      const downloaderId = linkData.downloader_binding || 'none'
      if (downloaderId === 'none') throw new Error('M-Team 未绑定下载器')

      let opts = dlOptionsCache[downloaderId]
      if (!opts) {
        const optRes = await sdk.api.post(`/plugins/${downloaderId}/actions/download_options`, { payload: {} })
        opts = optRes.data
        dlOptionsCache[downloaderId] = opts
      }

      state.downloadDialog = {
        open: true,
        item: torrent,
        media: media,
        tid: tid,
        url: linkData.url,
        downloaderId: downloaderId,
        name: torrent.label,
        savepath: opts.default_savepath || '',
        category: opts.default_category || '',
        options: opts,
        submitting: false,
        submitPct: 0,
        submitStatus: 'idle',
        error: '',
      }
      renderDownloadDialog()
    } catch (e) {
      sdk.toast.error(e?.response?.data?.detail || e?.message || '获取推送选项失败')
    }
  }

  function closeDownloadDialog() {
    state.downloadDialog.open = false
    if (activeDownloadModal) {
      try { activeDownloadModal.el?.remove() } catch {}
      activeDownloadModal = null
    }
  }

  async function submitDownloadDialog() {
    const d = state.downloadDialog
    if (d.submitting) return
    d.submitting = true
    d.submitPct = 8
    d.submitStatus = 'running'
    d.error = ''
    renderDownloadDialog()

    const submitPayload = {
      url: d.url,
      urls: d.url,
      title: d.item.label,
      name: d.name,
      rename: '',
      savepath: d.savepath,
      category: d.category,
      source_plugin: 'mteam-plugin',
      file_indices: d.options?.file_indices || 'auto',
    }

    const k = d.item.id
    state.pushing.add(k)
    state.pushProgress[k] = { status: 'running', pct: 8 }
    const timer = setInterval(() => {
      const p = state.pushProgress[k]
      if (!p || p.status !== 'running') return
      p.pct = Math.min(92, Number(p.pct || 0) + 7)
      d.submitPct = p.pct
      renderDownloadDialog()
    }, 180)

    try {
      const dlRes = await sdk.api.post(`/plugins/${d.downloaderId}/downloads`, { payload: submitPayload })
      if (!dlRes.data?.ok) throw new Error(dlRes.data?.message || '推送失败')
      state.pushProgress[k] = { status: 'success', pct: 100 }
      if (d.media?.id) {
        try {
          await sdk.api.post('/knowledge/actionables/mark', {
            entity_id: d.media.id,
            action_type: 'download_pushed',
            status: 'done',
            data: {
              torrent_id: d.item?.id,
              torrent_key: d.item?.key,
              downloader: d.downloaderId,
              result: dlRes.data,
            },
          })
          await loadActionables()
        } catch (markError) {}
      }
      d.submitPct = 100
      d.submitStatus = 'success'
      renderDownloadDialog()
      setTimeout(closeDownloadDialog, 1500)
    } catch (e) {
      d.error = e?.response?.data?.detail || e?.message || '推送失败'
      d.submitPct = 100
      d.submitStatus = 'error'
      state.pushProgress[k] = { status: 'error', pct: 100 }
      renderDownloadDialog()
    } finally {
      clearInterval(timer)
      state.pushing.delete(k)
      render()
    }
  }

  function renderDownloadDialog() {
    const d = state.downloadDialog
    if (!d.open) {
      if (activeDownloadModal) { try { activeDownloadModal.el?.remove() } catch {}; activeDownloadModal = null }
      return
    }

    const content = []

    const summary = el('div', 'av-graph__download-summary')
    summary.append(
      el('div', 'av-graph__download-title', d.item?.label || '下载任务'),
      el('div', 'av-graph__download-meta', torrentMeta(d.item) || `下载器 ${d.downloaderId}`),
    )
    content.push(summary)

    const nameField = sdk.ui.field({
      label: '下载任务名',
      control: sdk.ui.input({
        value: d.name,
        onInput: v => { d.name = v },
      })
    })
    content.push(nameField)

    if (d.options?.supports_savepath) {
      const savepathField = sdk.ui.field({
        label: '下载路径',
        control: sdk.ui.input({
          value: d.savepath,
          onInput: v => { d.savepath = v },
        })
      })
      content.push(savepathField)
    }

    if (d.options?.supports_categories && d.options?.categories?.length) {
      const categoryField = sdk.ui.field({
        label: '下载分类',
        control: sdk.ui.select({
          value: d.category,
          options: [{ label: '无分类', value: '' }].concat(d.options.categories.map(c => ({ label: c.name, value: c.name }))),
          onChange: v => {
            d.category = v
            const cat = d.options.categories.find(c => c.name === v)
            if (cat && cat.save_path) d.savepath = cat.save_path
            renderDownloadDialog()
          },
        })
      })
      content.push(categoryField)
    }

    if (d.error) {
      content.push(sdk.ui.notice({ tone: 'error', text: d.error }))
    }

    const cancelBtn = sdk.ui.button({ label: '取消', onClick: closeDownloadDialog })
    const submitBtn = sdk.ui.submitButton({
      label: '推送到下载器',
      onClick: submitDownloadDialog
    })
    submitBtn.__setState(d.submitStatus, d.submitPct)

    if (activeDownloadModal) {
      activeDownloadModal.body.innerHTML = ''
      content.forEach(node => activeDownloadModal.body.appendChild(node))
      const footer = activeDownloadModal.el.querySelector('.noor-plugin-modal__actions')
      if (footer) {
        footer.innerHTML = ''
        footer.append(cancelBtn, submitBtn)
      }
    } else {
      activeDownloadModal = sdk.ui.modal({
        title: '推送确认',
        closeOnMask: false,
        onClose: closeDownloadDialog,
        content: content,
        footer: [cancelBtn, submitBtn],
      })
    }
  }
  function renderDetail() {
    detail.innerHTML = ''
    if (!state.selected) {
      detail.append(sdk.ui.emptyState({ text: '选择一个节点查看关系' }))
      return
    }
    const payload = state.detail
    if (!payload) {
      detail.append(sdk.ui.skeletonCard({ className: 'av-graph__skeleton' }))
      return
    }
    const entity = payload.entity
    const head = el('div', 'av-graph__detail-head')
    head.append(el('span', 'av-graph__badge', typeLabel(entity.type)), el('h2', 'av-graph__title', entity.label))
    detail.appendChild(head)

    const summary = el('div', 'av-graph__summary')
    summary.append(
      el('span', 'av-graph__summary-item', `评分 ${scoreText(payload.scores)}`),
      el('span', 'av-graph__summary-item', `来源 ${entity.source}`),
      el('span', 'av-graph__summary-item', `置信度 ${entity.confidence}`),
    )
    detail.appendChild(summary)

    const insights = payload.insights || {}
    const resource = insights.resource || {}
    const insightBox = el('div', 'av-graph__insights')
    const insightCards = [
      ['资源质量', resource.quality == null ? '暂无' : `${resource.quality}/100`],
      ['字幕', `${resource.subtitle_count || 0}`],
      ['版本', `${resource.version_count || 0}`],
      ['候选', `${resource.torrent_candidate_count || 0}`],
      ['最佳匹配', resource.best_candidate_score ? String(resource.best_candidate_score) : '暂无'],
    ]
    for (const [label, value] of insightCards) {
      const card = el('div', 'av-graph__insight-card')
      card.append(el('span', '', label), el('strong', '', value))
      insightBox.appendChild(card)
    }
    detail.appendChild(insightBox)

    if ((insights.recommendations || []).length || (insights.warnings || []).length) {
      const box = el('div', 'av-graph__section av-graph__section--analysis')
      box.appendChild(el('h3', 'av-graph__section-title', '分析建议'))
      for (const message of (insights.recommendations || []).slice(0, 5)) {
        box.appendChild(el('div', 'av-graph__analysis-line is-good', message))
      }
      for (const message of (insights.warnings || []).slice(0, 5)) {
        box.appendChild(el('div', 'av-graph__analysis-line is-warn', message))
      }
      detail.appendChild(box)
    }

    if ((insights.shared_groups || []).length) {
      const box = el('div', 'av-graph__section')
      box.appendChild(el('h3', 'av-graph__section-title', '关系聚类'))
      for (const group of insights.shared_groups.slice(0, 4)) {
        const row = el('div', 'av-graph__cluster')
        const target = el('button', 'av-graph__cluster-target')
        target.type = 'button'
        target.append(
          el('span', 'av-graph__cluster-relation', relationLabel(group.relation_type)),
          el('strong', '', group.target?.label || group.target?.key || ''),
        )
        target.onclick = () => group.target && selectEntity(group.target)
        const meta = el('div', 'av-graph__cluster-meta', `${(group.media || []).length} 个同类作品${group.missing_subtitle_count ? ` · ${group.missing_subtitle_count} 个缺字幕` : ''}`)
        const samples = el('div', 'av-graph__cluster-samples')
        for (const media of (group.media || []).slice(0, 3)) {
          const mediaBtn = el('button', 'av-graph__cluster-sample', media.label)
          mediaBtn.type = 'button'
          mediaBtn.onclick = () => selectEntity(media)
          samples.appendChild(mediaBtn)
        }
        row.append(target, meta, samples)
        box.appendChild(row)
      }
      detail.appendChild(box)
    }

    if ((insights.cluster_members || []).length) {
      const members = insights.cluster_members || []
      const counts = {
        all: members.length,
        missing: members.filter(item => item.missing_subtitle).length,
        candidate: members.filter(item => Number(item.candidate_count || 0) > 0).length,
        actionable: members.filter(item => item.missing_subtitle && Number(item.candidate_count || 0) > 0).length,
        subtitled: members.filter(item => Number(item.subtitle_count || 0) > 0).length,
      }
      const current = state.memberFilter || 'all'
      const filtered = members.filter(item => {
        if (current === 'missing') return item.missing_subtitle
        if (current === 'candidate') return Number(item.candidate_count || 0) > 0
        if (current === 'actionable') return item.missing_subtitle && Number(item.candidate_count || 0) > 0
        if (current === 'subtitled') return Number(item.subtitle_count || 0) > 0
        return true
      })
      const box = el('div', 'av-graph__section av-graph__member-section')
      const titleRow = el('div', 'av-graph__member-head')
      titleRow.append(
        el('h3', 'av-graph__section-title', '聚类作品'),
        el('div', 'av-graph__member-total', `${filtered.length} / ${members.length}`),
      )
      const filters = el('div', 'av-graph__member-filters')
      const filterDefs = [
        ['all', `全部 ${counts.all}`],
        ['missing', `缺字幕 ${counts.missing}`],

        ['actionable', `缺字幕可补 ${counts.actionable}`],
        ['subtitled', `有字幕 ${counts.subtitled}`],
      ]
      for (const [value, label] of filterDefs) {
        const btn = el('button', `av-graph__member-filter${current === value ? ' is-active' : ''}`, label)
        btn.type = 'button'
        btn.onclick = () => {
          state.memberFilter = value
          renderDetail()
        }
        filters.appendChild(btn)
      }
      const listBox = el('div', 'av-graph__member-list')
      const visibleMembers = filtered.slice(0, 40)
      for (const item of visibleMembers) {
        const media = item.entity
        const row = el('button', 'av-graph__member-row')
        row.type = 'button'
        row.onclick = () => selectEntity(media)
        const name = el('div', 'av-graph__member-name', media.label || media.key || '')
        const meta = el('div', 'av-graph__member-meta')
        if (item.quality != null) meta.appendChild(el('span', '', `${item.quality}/100`))
        if (item.missing_subtitle) meta.appendChild(el('span', 'is-warn', '缺字幕'))
        if (Number(item.candidate_count || 0) > 0) meta.appendChild(el('span', 'is-good', `${item.candidate_count} 候选`))
        if (Number(item.subtitle_count || 0) > 0) meta.appendChild(el('span', '', `${item.subtitle_count} 字幕`))
        row.append(name, meta)
        listBox.appendChild(row)
      }
      if (!visibleMembers.length) {
        listBox.appendChild(el('div', 'av-graph__member-empty', '当前筛选下没有作品'))
      }
      if (filtered.length > visibleMembers.length) {
        listBox.appendChild(el('div', 'av-graph__member-more', `仅显示前 ${visibleMembers.length} 个，继续筛选可缩小范围`))
      }
      box.append(titleRow, filters, listBox)
      detail.appendChild(box)
    }

    if (entity.type === 'torrent' && sourceLink(entity)) {
      const sourceBox = el('div', 'av-graph__source')
      const sourceText = el('div', 'av-graph__source-text')
      sourceText.append(
        el('strong', '', '来源详情'),
        el('span', '', entity.data?.download_available ? '该种子带直接下载信息' : '当前 Knowledge Core 仅记录官方详情页，未保存直接下载链接'),
      )
      const link = el('a', 'av-graph__source-link', '打开 M-Team')
      link.href = sourceLink(entity)
      link.target = '_blank'
      link.rel = 'noreferrer'
      const actions = el('div', 'av-graph__source-actions')
      actions.appendChild(link)
      if (entity.source === 'mteam-plugin' && extractTorrentId(entity)) {
        const k = entity.id
        const ps = state.pushProgress[k] || { status: state.pushing.has(k) ? 'running' : 'idle', pct: 0 }
        const push = el('button', `av-graph__candidate-push is-${ps.status}`)
        push.type = 'button'
        push.textContent = ps.status === 'success' ? '已推送' : ps.status === 'error' ? '重试' : ps.status === 'running' ? '推送中' : '推送'
        push.disabled = ps.status === 'success' || ps.status === 'running'
        push.onclick = () => openDownloadDialog(entity, null)
        actions.appendChild(push)
      }
      sourceBox.append(sourceText, actions)
      detail.appendChild(sourceBox)
    }

    if ((payload.anomalies || []).length) {
      const box = el('div', 'av-graph__section')
      box.appendChild(el('h3', 'av-graph__section-title', '洞察'))
      for (const anomaly of payload.anomalies) {
        box.appendChild(el('div', 'av-graph__line', anomaly.message))
      }
      detail.appendChild(box)
    }

    const related = el('div', 'av-graph__section')
    related.appendChild(el('h3', 'av-graph__section-title', '关联'))
    const entities = new Map((payload.neighbors?.entities || []).map(item => [item.id, item]))
    const edges = (payload.neighbors?.edges || []).filter(edge => edge.source_entity_id === entity.id || edge.target_entity_id === entity.id)

    const candidates = edges
      .filter(edge => edge.relation_type === 'HAS_TORRENT_CANDIDATE')
      .map(edge => ({ edge, torrent: entities.get(edge.source_entity_id === entity.id ? edge.target_entity_id : edge.source_entity_id) }))
      .filter(item => item.torrent && item.torrent.type === 'torrent')
      .sort((a, b) => candidateScore(b.torrent, b.edge) - candidateScore(a.torrent, a.edge) || String(a.torrent.label || '').localeCompare(String(b.torrent.label || '')))

    if (entity.type === 'media_item' && candidates.length) {
      const box = el('div', 'av-graph__section av-graph__section--primary')
      box.appendChild(el('h3', 'av-graph__section-title', `可下载候选 · ${candidates.length}`))
      for (const candidate of candidates.slice(0, 8)) {
        const torrent = candidate.torrent
        const candidateText = edgeCandidateText(candidate.edge)
        const card = el('div', 'av-graph__candidate')
        const main = el('button', 'av-graph__candidate-main')
        main.type = 'button'
        const title = el('div', 'av-graph__candidate-title', torrent.label)
        const meta = el('div', 'av-graph__candidate-meta', torrentMeta(torrent) || `来源 ${torrent.source}`)
        const badgeRow = el('div', 'av-graph__candidate-badges')
        for (const badge of torrentBadges(torrent)) {
          const node = el('span', `av-graph__mini-badge is-${badge.tone}`, badge.label)
          badgeRow.appendChild(node)
        }
        const hint = el('div', 'av-graph__candidate-hint', candidateText || '通过共享番号自动关联，点击查看种子节点')
        main.append(title, meta)
        if (badgeRow.childNodes.length) main.appendChild(badgeRow)
        main.appendChild(hint)
        main.onclick = () => selectEntity(torrent)
        card.appendChild(main)
        if (sourceLink(torrent)) {
          const link = el('a', 'av-graph__candidate-link', '来源')
          link.href = sourceLink(torrent)
          link.target = '_blank'
          link.rel = 'noreferrer'
          card.appendChild(link)
        }
        if (torrent.source === 'mteam-plugin' && extractTorrentId(torrent)) {
          const k = torrent.id
          const ps = state.pushProgress[k] || { status: state.pushing.has(k) ? 'running' : 'idle', pct: 0 }
          const pBtn = el('button', `av-graph__candidate-push is-${ps.status}`)
          pBtn.type = 'button'
          pBtn.textContent = ps.status === 'success' ? '已推送' : ps.status === 'error' ? '重试' : ps.status === 'running' ? '推送中' : '推送'
          pBtn.disabled = ps.status === 'success' || ps.status === 'running'
          pBtn.onclick = (e) => { e.stopPropagation(); openDownloadDialog(torrent, entity) }
          card.appendChild(pBtn)
        }
        box.appendChild(card)
      }
      detail.appendChild(box)
    }

    if (!edges.length) {
      related.appendChild(el('div', 'av-graph__muted', '暂无关联'))
    }
    for (const edge of edges.slice(0, 80)) {
      const otherId = edge.source_entity_id === entity.id ? edge.target_entity_id : edge.source_entity_id
      const other = entities.get(otherId)
      if (!other || other.id === entity.id) continue
      const row = el('button', 'av-graph__relation')
      row.type = 'button'
      if (edge.relation_type === 'HAS_TORRENT_CANDIDATE') row.classList.add('is-candidate')
      row.append(el('span', 'av-graph__relation-type', contextualRelationLabel(edge, entity, other)), el('span', 'av-graph__relation-label', other.label))
      row.onclick = () => selectEntity(other)
      related.appendChild(row)
    }
    detail.appendChild(related)
  }

  function render() {
    renderRebuildStatus()
    renderStats()
    renderGraph()
    renderClusters()
    renderActionables()
    renderList()
    renderDetail()
  }

  async function loadStats() {
    const response = await sdk.api.get('/knowledge/stats')
    state.stats = response.data
  }


  async function loadGraph(entity = null) {
    state.graphLoading = true
    renderGraph()
    try {
      const params = { depth: state.graphDepth, limit: state.graphDepth === 2 ? 140 : 80 }
      if (entity?.id) params.entity_id = entity.id
      else if (state.query) params.q = state.query
      const response = await sdk.api.get('/knowledge/graph/explore', { params })
      state.graph = response.data
    } catch (error) {
      state.graph = null
    } finally {
      state.graphLoading = false
      renderGraph()
    }
  }

  async function loadActionables() {
    try {
      const [missing, high, multi, states] = await Promise.all([
        sdk.api.get('/knowledge/actionables', { params: { kind: 'missing_subtitle_with_candidate', limit: 3 } }),
        sdk.api.get('/knowledge/actionables', { params: { kind: 'high_quality_candidates', limit: 9 } }),
        sdk.api.get('/knowledge/actionables', { params: { kind: 'multi_version_missing_subtitle', limit: 9 } }),
        sdk.api.get('/knowledge/actionables/states', { params: { status: 'done,hidden', limit: 6 } }),
      ])
      state.actionables = {
        missing: missing.data.items || [],
        high: high.data.items || [],
        multi: multi.data.items || [],
      }
      state.actionStates = states.data.items || []
    } catch (error) {
      state.actionables = { missing: [], high: [], multi: [] }
      state.actionStates = []
    }
  }

  async function loadClusters() {
    try {
      const response = await sdk.api.get('/knowledge/graph/clusters', { params: { limit: 12 } })
      state.clusters = response.data.items || []
    } catch (error) {
      state.clusters = []
    }
  }

  async function loadRebuildStatus() {
    const response = await sdk.api.get('/knowledge/rebuild/status')
    state.rebuild = response.data
    renderRebuildStatus()
    return response.data
  }

  async function pollRebuildStatus(runId) {
    for (let i = 0; i < 900 && !disposed; i += 1) {
      const status = await loadRebuildStatus()
      const run = status?.run
      const stats = run?.stats || {}
      if (run?.status === 'failed') {
        rebuildBtn.__setState('error', 100, '重建失败')
        sdk.toast.error(run.message || '重建失败')
        return
      }
      if (run?.status === 'completed' && (!runId || run.id === runId)) {
        rebuildBtn.__setState('success', 100, '已重建')
        sdk.toast.success('AV 图谱索引已重建')
        await loadActionables()
        await loadAll()
        return
      }
      rebuildBtn.__setState('running', stats.percent || 35, stats.phase === 'jobs' ? '任务历史' : '重建中')
      await new Promise(resolve => setTimeout(resolve, 1200))
    }
  }

  async function loadSearch() {
    state.loading = true
    renderList()
    try {
      const response = await sdk.api.get('/knowledge/search', { params: { q: state.query, entity_type: state.type || undefined, filter_kind: state.filter || undefined, limit: 40 } })
      state.results = response.data.items || []
      if (!state.selected && state.results.length) await selectEntity(state.results[0], false)
    } catch (error) {
      sdk.toast.error(error?.response?.data?.detail || error?.message || '搜索失败')
    } finally {
      state.loading = false
      render()
    }
  }

  async function selectEntity(entity, shouldRender = true, options = {}) {
    state.selected = entity
    state.detail = null
    state.memberFilter = options.memberFilter || 'all'
    if (shouldRender) render()
    loadGraph(entity)
    try {
      const response = await sdk.api.get(`/knowledge/entities/${entity.id}`)
      state.detail = response.data
    } catch (error) {
      sdk.toast.error(error?.response?.data?.detail || error?.message || '详情加载失败')
    }
    render()
  }

  async function loadAll() {
    if (disposed) return
    await Promise.all([loadStats(), loadRebuildStatus(), loadActionables(), loadClusters(), loadSearch()])
    render()
  }

  await loadAll()
  return () => {
    disposed = true
    clearTimeout(timer)
    root.innerHTML = ''
  }
}

