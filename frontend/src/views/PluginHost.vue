<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import api from '../api'
import { useToast } from '../composables/useToast'
import { useConfirm } from '../composables/useConfirm'

const route = useRoute()
const toast = useToast()
const confirm = useConfirm()
const host = ref<HTMLElement | null>(null)
const loading = ref(false)
const error = ref('')
const pluginId = computed(() => String(route.params.pluginId || ''))
let dispose: null | (() => void) = null
let styleEl: HTMLLinkElement | null = null

function clearMounted() {
  if (dispose) {
    try { dispose() } catch {}
    dispose = null
  }
  if (styleEl) {
    styleEl.remove()
    styleEl = null
  }
  if (host.value) host.value.innerHTML = ''
}

function makeButton(options: any = {}) {
  const btn = document.createElement('button')
  btn.type = 'button'
  btn.className = ['noor-plugin-btn', options.tone === 'primary' ? 'noor-plugin-btn--primary' : '', options.tone === 'danger' ? 'noor-plugin-btn--danger' : '', options.className || ''].filter(Boolean).join(' ')
  btn.textContent = options.label || ''
  if (options.title) btn.title = options.title
  if (options.disabled) btn.disabled = true
  if (options.onClick) btn.onclick = options.onClick
  return btn
}

function makeInput(options: any = {}) {
  const input = document.createElement('input')
  input.className = ['noor-plugin-input', options.className || ''].filter(Boolean).join(' ')
  input.value = options.value ?? ''
  input.placeholder = options.placeholder || ''
  input.readOnly = !!options.readonly
  input.oninput = () => options.onInput?.(input.value)
  return input
}

function makeSelect(options: any = {}) {
  const select = document.createElement('select')
  select.className = ['noor-plugin-input', 'noor-plugin-select', options.className || ''].filter(Boolean).join(' ')
  for (const item of options.options || []) {
    const opt = document.createElement('option')
    opt.value = String(item.value ?? '')
    opt.textContent = String(item.label ?? item.value ?? '')
    select.appendChild(opt)
  }
  select.value = options.value ?? ''
  select.onchange = () => options.onChange?.(select.value)
  return select
}

function makeField(options: any = {}) {
  const field = document.createElement('label')
  field.className = ['noor-plugin-field', options.className || ''].filter(Boolean).join(' ')
  const label = document.createElement('span')
  label.className = 'noor-plugin-field__label'
  label.textContent = options.label || ''
  field.appendChild(label)
  if (options.control) field.appendChild(options.control)
  if (options.hint) {
    const hint = document.createElement('small')
    hint.className = 'noor-plugin-field__hint'
    hint.textContent = options.hint
    field.appendChild(hint)
  }
  return field
}

function makeModal(options: any = {}) {
  const mask = document.createElement('div')
  mask.className = 'noor-plugin-modal-mask'
  const panel = document.createElement('div')
  panel.className = `noor-plugin-modal noor-plugin-modal--${options.width || 'md'}`
  const head = document.createElement('div')
  head.className = 'noor-plugin-modal__head'
  const title = document.createElement('div')
  title.className = 'noor-plugin-modal__title'
  title.textContent = options.title || ''
  const closeBtn = makeButton({ label: '×', title: '关闭', className: 'noor-plugin-modal__close' })
  head.append(title, closeBtn)
  const body = document.createElement('div')
  body.className = 'noor-plugin-modal__body'
  if (Array.isArray(options.content)) options.content.forEach((x: Node) => body.appendChild(x))
  else if (options.content) body.appendChild(options.content)
  panel.append(head, body)
  const footer = document.createElement('div')
  footer.className = 'noor-plugin-modal__actions'
  if (Array.isArray(options.footer)) options.footer.forEach((x: Node) => footer.appendChild(x))
  else if (options.footer) footer.appendChild(options.footer)
  if (footer.childNodes.length) panel.appendChild(footer)
  mask.appendChild(panel)
  const close = () => { mask.remove(); options.onClose?.() }
  closeBtn.onclick = close
  mask.onclick = event => { if (event.target === mask && options.closeOnMask !== false) close() }
  document.body.appendChild(mask)
  return { el: mask, body, close }
}

function makePanel(options: any = {}) {
  const mask = document.createElement('div')
  mask.className = 'noor-plugin-panel-mask'
  const panel = document.createElement('div')
  panel.className = ['noor-plugin-panel', options.className || ''].filter(Boolean).join(' ')
  const scroll = document.createElement('div')
  scroll.className = 'noor-plugin-panel__scroll'
  const head = document.createElement('div')
  head.className = 'detail-panel-topbar noor-plugin-panel__head'
  const meta = document.createElement('div')
  meta.className = 'detail-panel-topbar__meta noor-plugin-panel__meta'
  if (options.eyebrow) {
    const eyebrow = document.createElement('span')
    eyebrow.className = 'detail-panel-topbar__eyebrow noor-plugin-panel__eyebrow'
    eyebrow.textContent = options.eyebrow
    meta.appendChild(eyebrow)
  }
  const title = document.createElement('div')
  title.className = 'noor-plugin-panel__title'
  title.textContent = options.title || ''
  meta.appendChild(title)
  const closeBtn = document.createElement('button')
  closeBtn.type = 'button'
  closeBtn.className = 'detail-panel-topbar__close noor-plugin-panel__close'
  closeBtn.title = '关闭'
  closeBtn.setAttribute('aria-label', '关闭')
  closeBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>`
  head.append(meta, closeBtn)
  const body = document.createElement('div')
  body.className = 'noor-plugin-panel__body'
  if (Array.isArray(options.content)) options.content.forEach((x: Node) => body.appendChild(x))
  else if (options.content) body.appendChild(options.content)
  scroll.append(head, body)
  panel.appendChild(scroll)
  mask.appendChild(panel)
  const close = () => { mask.remove(); options.onClose?.() }
  closeBtn.onclick = close
  mask.onclick = event => { if (event.target === mask && options.closeOnMask !== false) close() }
  document.body.appendChild(mask)
  return { el: mask, body, close, panel }
}

function makeTabs(options: any = {}) {
  const wrap = document.createElement('div') as HTMLDivElement & { dispose?: () => void; __noorDispose?: () => void }
  wrap.className = 'noor-plugin-tabs'
  const marker = document.createElement('span')
  marker.className = 'noor-plugin-tabs__marker'
  wrap.appendChild(marker)

  const buttons: HTMLButtonElement[] = []
  const getTabValue = (tab: any) => String(tab?.value ?? tab?.key ?? '')
  const initialTabs = Array.isArray(options.tabs) ? options.tabs : []
  const initialValue = String(options.value ?? '') || getTabValue(initialTabs[0])
  options.value = initialValue
  let raf = 0

  const refresh = () => {
    if (!wrap.isConnected) return
    const activeValue = String(options.value ?? '')
    buttons.forEach(button => button.classList.toggle('is-active', button.dataset.value === activeValue))
    const active = buttons.find(b => b.dataset.value === activeValue) || buttons[0]
    if (!active) return
    marker.style.width = `${active.offsetWidth}px`
    marker.style.transform = `translateX(${active.offsetLeft}px)`
  }

  const scheduleRefresh = () => {
    if (raf) cancelAnimationFrame(raf)
    raf = requestAnimationFrame(() => { raf = 0; refresh() })
  }

  for (const tab of initialTabs) {
    const value = getTabValue(tab)
    const btn = document.createElement('button')
    btn.type = 'button'
    btn.textContent = tab.label ?? value
    btn.dataset.value = value
    btn.className = 'noor-plugin-tabs__item'
    btn.onclick = (event) => {
      event.preventDefault()
      event.stopPropagation()
      if (String(options.value ?? '') === value) return
      options.value = value
      refresh()
      options.onChange?.(value)
      scheduleRefresh()
    }
    buttons.push(btn)
    wrap.appendChild(btn)
  }

  scheduleRefresh()
  requestAnimationFrame(() => {
    refresh()
    wrap.classList.add('noor-plugin-tabs--ready')
  })
  window.addEventListener('resize', scheduleRefresh)
  const setValue = (value: string) => {
    options.value = String(value)
    refresh()
  }
  const dispose = () => {
    if (raf) cancelAnimationFrame(raf)
    window.removeEventListener('resize', scheduleRefresh)
  }
  wrap.dispose = dispose
  wrap.__noorDispose = dispose
  ;(wrap as any).__noorSetValue = setValue
  return wrap
}

function makePagination(options: any = {}) {
  const wrap = document.createElement('div')
  wrap.className = 'noor-pagination noor-plugin-pagination'
  const page = Number(options.page || 1)
  const total = Math.max(1, Number(options.totalPages || 1))
  const go = (target: number) => {
    const next = Math.min(Math.max(1, target), total)
    if (next !== page) options.onPage?.(next)
  }
  const mk = (label: string, target: number, disabled = false, active = false) => {
    const btn = document.createElement('button')
    btn.type = 'button'
    btn.className = `noor-pagination__btn${active ? ' noor-pagination__page is-active' : ''}`
    btn.textContent = label
    btn.disabled = disabled
    btn.onclick = () => !disabled && go(target)
    return btn
  }
  wrap.append(mk('上一页', page - 1, page <= 1))
  const siblingCount = Math.max(1, Number(options.siblingCount ?? 2))
  const start = Math.max(1, page - siblingCount)
  const end = Math.min(total, page + siblingCount)
  for (let p = start; p <= end; p++) wrap.append(mk(String(p), p, false, p === page))
  wrap.append(mk('下一页', page + 1, page >= total))
  const onKeydown = (event: KeyboardEvent) => {
    if (options.keyboard === false) return
    const target = event.target as HTMLElement | null
    if (target && ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)) return
    if (event.key === 'PageUp') { event.preventDefault(); go(page - 1) }
    else if (event.key === 'PageDown') { event.preventDefault(); go(page + 1) }
    else if (event.key === 'Home') { event.preventDefault(); go(1) }
    else if (event.key === 'End') { event.preventDefault(); go(total) }
  }
  window.addEventListener('keydown', onKeydown)
  ;(wrap as any).__noorDispose = () => window.removeEventListener('keydown', onKeydown)
  return wrap
}

function makeSubmitButton(options: any = {}) {
  const btn = makeButton({ label: '', tone: 'primary', className: ['noor-submit-btn', options.className || ''].filter(Boolean).join(' ') })
  const bar = document.createElement('i')
  bar.className = 'noor-submit-btn__bar'
  const text = document.createElement('span')
  text.className = 'noor-submit-btn__text'
  btn.append(bar, text)
  const normalize = (state: string) => state === 'submitting' ? 'running' : (state || 'idle')
  const labelFor = (state: string, progress = 0, label = '') => {
    if (label) return label
    if (state === 'success') return options.successLabel || '已完成'
    if (state === 'error') return options.errorLabel || '失败'
    if (state === 'running') return options.submittingLabel || options.runningLabel || (progress > 0 ? `${Math.round(progress)}%` : '提交中')
    return options.idleLabel || options.label || '提交'
  }
  const setState = (state: string, progress = 0, label = '') => {
    const next = normalize(state)
    const pct = Math.max(0, Math.min(100, Number(progress || 0)))
    btn.dataset.state = next
    btn.classList.toggle('is-running', next === 'running')
    btn.classList.toggle('is-success', next === 'success')
    btn.classList.toggle('is-error', next === 'error')
    btn.style.setProperty('--submit-progress', `${pct}%`)
    text.textContent = labelFor(next, pct, label)
    if (options.disableWhileRunning !== false && next === 'running') btn.disabled = true
    else if (next === 'success' && options.disableOnSuccess !== false) btn.disabled = true
    else btn.disabled = !!options.disabled
  }
  btn.onclick = event => {
    if (btn.disabled) return
    options.onClick?.(event)
  }
  ;(btn as any).__setState = setState
  setState(options.status || 'idle', Number(options.progress || 0), options.labelOverride || '')
  return btn
}

function appendChildren(parent: HTMLElement, children?: any) {
  if (!children) return parent
  const list = Array.isArray(children) ? children : [children]
  for (const child of list) {
    if (!child) continue
    if (child instanceof Node) parent.appendChild(child)
    else parent.appendChild(document.createTextNode(String(child)))
  }
  return parent
}

function makeTopBar(options: any = {}) {
  const bar = document.createElement('div')
  bar.className = ['noor-plugin-topbar', options.className || ''].filter(Boolean).join(' ')
  const tabs = document.createElement('div')
  tabs.className = 'noor-plugin-topbar__tabs'
  const actions = document.createElement('div')
  actions.className = 'noor-plugin-topbar__actions'
  appendChildren(tabs, options.tabs || options.left)
  appendChildren(actions, options.actions || options.right)
  bar.append(tabs, actions)
  return { el: bar, tabs, actions }
}

function makeActionRow(options: any = {}) {
  const row = document.createElement('div')
  row.className = ['noor-plugin-action-row', options.className || ''].filter(Boolean).join(' ')
  appendChildren(row, options.children || options.items)
  return row
}

function makeStatCard(options: any = {}) {
  const card = document.createElement(options.onClick ? 'button' : 'div') as HTMLElement
  card.className = ['noor-plugin-stat-card', options.tone ? `noor-plugin-stat-card--${options.tone}` : '', options.className || ''].filter(Boolean).join(' ')
  if (options.onClick) {
    ;(card as HTMLButtonElement).type = 'button'
    ;(card as HTMLButtonElement).onclick = options.onClick
  }
  const label = document.createElement('span')
  label.className = 'noor-plugin-stat-card__label'
  label.textContent = options.label || ''
  const value = document.createElement('strong')
  value.className = 'noor-plugin-stat-card__value'
  value.textContent = String(options.value ?? '-')
  card.append(label, value)
  if (options.hint) {
    const hint = document.createElement('small')
    hint.className = 'noor-plugin-stat-card__hint'
    hint.textContent = String(options.hint)
    card.appendChild(hint)
  }
  return card
}

function makeStatGrid(options: any = {}) {
  const grid = document.createElement('div')
  grid.className = ['noor-plugin-stat-grid', options.className || ''].filter(Boolean).join(' ')
  const items = Array.isArray(options.items) ? options.items : []
  for (const item of items) grid.appendChild(makeStatCard(item))
  return grid
}

function makeMediaCard(options: any = {}) {
  const card = document.createElement(options.onClick ? 'button' : options.href ? 'a' : 'div') as HTMLElement
  card.className = ['noor-plugin-media-card', options.sharp ? 'noor-plugin-media-card--sharp' : '', options.className || ''].filter(Boolean).join(' ')
  if (options.href) {
    ;(card as HTMLAnchorElement).href = options.href
    ;(card as HTMLAnchorElement).target = options.target || '_self'
  }
  if (options.onClick) {
    ;(card as HTMLButtonElement).type = 'button'
    ;(card as HTMLButtonElement).onclick = options.onClick
  }
  const cover = document.createElement('div')
  cover.className = ['noor-plugin-media-card__cover', options.coverOnClick ? 'is-clickable' : ''].filter(Boolean).join(' ')
  if (options.coverOnClick) cover.onclick = (e) => { e.stopPropagation(); options.coverOnClick() }
  if (options.image || options.cover || options.coverUrl) {
    const img = document.createElement('img')
    img.src = options.image || options.cover || options.coverUrl
    img.loading = options.loading || 'lazy'
    cover.appendChild(img)
  } else {
    const ph = document.createElement('div')
    ph.className = 'noor-plugin-media-card__placeholder'
    ph.textContent = options.placeholder || 'NO IMAGE'
    cover.appendChild(ph)
  }
  const body = document.createElement('div')
  body.className = 'noor-plugin-media-card__body'
  const title = document.createElement('div')
  title.className = ['noor-plugin-media-card__title', options.titleOnClick ? 'is-clickable' : ''].filter(Boolean).join(' ')
  title.textContent = options.title || ''
  if (options.titleOnClick) title.onclick = (e) => { e.stopPropagation(); options.titleOnClick() }
  body.appendChild(title)
  if (options.meta) {
    const meta = document.createElement('div')
    meta.className = 'noor-plugin-media-card__meta'
    const metaItems = Array.isArray(options.meta) ? options.meta : [options.meta]
    for (const text of metaItems.filter(Boolean)) {
      const span = document.createElement('span')
      span.textContent = String(text)
      meta.appendChild(span)
    }
    body.appendChild(meta)
  }
  if (options.badges) {
    const badges = document.createElement('div')
    badges.className = 'noor-plugin-media-card__badges'
    appendChildren(badges, options.badges)
    body.appendChild(badges)
  }
  if (options.actions) {
    const actions = document.createElement('div')
    actions.className = 'noor-plugin-media-card__actions'
    appendChildren(actions, options.actions)
    body.appendChild(actions)
  }
  card.append(cover, body)
  return card
}

function makeLoadingState(options: any = {}) {
  const d = document.createElement('div')
  d.className = ['noor-plugin-state', 'noor-plugin-state--loading', options.className || ''].filter(Boolean).join(' ')
  const spinner = document.createElement('span')
  spinner.className = 'noor-plugin-spinner'
  const text = document.createElement('span')
  text.textContent = options.text || '加载中…'
  d.append(spinner, text)
  return d
}

function lastSavepathKey(downloaderId: string) {
  return `noor:last-download-savepath:${downloaderId || 'default'}`
}

function readLastSavepath(downloaderId: string) {
  try { return localStorage.getItem(lastSavepathKey(downloaderId)) || '' } catch { return '' }
}

function writeLastSavepath(downloaderId: string, value: string) {
  try {
    if (value) localStorage.setItem(lastSavepathKey(downloaderId), value)
  } catch {}
}

function escapeHtml(value: any) {
  return String(value ?? '').replace(/[&<>'"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[c]!))
}

function renderResourcePreview(resourceState: any) {
  const d = document.createElement('div')
  d.className = 'noor-downloader-preview'
  if (!resourceState.options?.supports_resource_preview) return d
  if (resourceState.loading) {
    d.innerHTML = '<div class="noor-downloader-preview__head"><span>资源预览</span><em>读取中...</em></div>'
    return d
  }
  if (resourceState.error) {
    d.innerHTML = `<div class="noor-downloader-preview__head"><span>资源预览</span><em class="is-error">${escapeHtml(resourceState.error)}</em></div>`
    return d
  }
  const files = Array.isArray(resourceState.data?.files) ? resourceState.data.files : []
  if (!files.length) {
    d.innerHTML = '<div class="noor-downloader-preview__head"><span>资源预览</span><em>暂无文件信息</em></div>'
    return d
  }
  const visible = files.slice(0, 6)
  d.innerHTML = `<div class="noor-downloader-preview__head"><span>资源预览</span><em>${escapeHtml(resourceState.data?.total_size_formatted || '')} · ${files.length} 个文件</em></div>
  <div class="noor-downloader-preview__files">${visible.map((file: any) => `<div class="noor-downloader-preview__file"><span>${escapeHtml(file.name || file.full_path || '')}</span><em>${escapeHtml(file.size_formatted || '')}</em></div>`).join('')}${files.length > visible.length ? `<div class="noor-downloader-preview__more">还有 ${files.length - visible.length} 个文件</div>` : ''}</div>`
  return d
}

function createDownloaderDialogContext(sourcePluginId: string) {
  let progressTimer: number | null = null

  async function postJson(url: string, payload: any) {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ payload }),
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok || data?.ok === false) throw new Error(data?.detail || data?.message || '请求失败')
    return data
  }

  async function open(options: any = {}) {
    const allowBatchUrls = !!options.allowBatchUrls
    const showDownloaderField = options.showDownloaderField !== false
    const previewEnabled = options.preview !== false
    const maxUrls = Number(options.maxUrls || 0)
    const submitIdleLabel = String(options.submitIdleLabel || (allowBatchUrls ? '创建任务' : '推送下载'))
    const submitSuccessLabel = String(options.submitSuccessLabel || (allowBatchUrls ? '创建成功' : '推送成功'))
    const submitErrorLabel = String(options.submitErrorLabel || (allowBatchUrls ? '创建失败' : '推送失败'))
    const submitPartialLabel = String(options.submitPartialLabel || '部分失败')
    const state: any = {
      downloaderId: String(options.downloaderId || '').trim(),
      title: String(options.title || ''),
      name: String(options.name || options.rename || options.title || ''),
      rename: String(options.rename || options.name || options.title || ''),
      titleOptions: Array.isArray(options.titleOptions) ? options.titleOptions.filter(Boolean) : [],
      titleMode: String(options.titleMode || ''),
      url: String(options.url || options.magnet || options.urls || ''),
      urlsText: String(options.urlsText || options.urls || options.url || options.magnet || ''),
      itemTitle: String(options.itemTitle || options.title || ''),
      fileIndices: 'auto',
      savepath: '',
      selectedPath: '',
      category: '',
      minFileSizeMb: '',
      options: null,
      error: '',
      loading: true,
      previewLoading: false,
      previewError: '',
      previewData: null,
      submitStatus: 'idle',
      submitProgress: 0,
      submitting: false,
      submitButton: null as any,
    }

    if (!state.downloaderId) throw new Error('未绑定下载器')
    if (!allowBatchUrls && !state.url) throw new Error('缺少下载链接')
    if (!state.titleMode && state.titleOptions.length) state.titleMode = String(state.titleOptions[0]?.key || '')

    const modal = makeModal({
      title: String(options.modalTitle || (allowBatchUrls ? '新建下载任务' : '推送下载')),
      width: 'md',
      closeOnMask: false,
      onClose: () => {
        if (state.submitting) return
        if (progressTimer) window.clearInterval(progressTimer)
      },
    })

    async function loadOptions() {
      state.loading = true
      state.error = ''
      render()
      try {
        const infoRes = await api.get(`/plugins/${state.downloaderId}/config`).then(r => r.data).catch(() => null)
        const dlOptions = await postJson(`/api/plugins/${state.downloaderId}/actions/download_options`, {})
        state.options = dlOptions
        state.downloaderName = infoRes?.plugin?.name || dlOptions.downloader || state.downloaderId
        state.fileIndices = String(dlOptions.file_indices || state.fileIndices || 'auto')
        state.category = String(dlOptions.default_category || '')
        state.savepath = readLastSavepath(state.downloaderId) || String(dlOptions.default_savepath || '')
        state.selectedPath = state.savepath
        if (dlOptions.small_file_filter && typeof dlOptions.small_file_filter === 'object') {
          const raw = dlOptions.small_file_filter.default_mb
          state.minFileSizeMb = raw === undefined || raw === null || raw === '' ? '' : String(raw)
        }
        const found = (dlOptions.categories || []).find((item: any) => item.name === state.category)
        if (found?.save_path && !state.savepath) state.savepath = String(found.save_path)
        if (!state.savepath) {
          const firstPath = Array.isArray(dlOptions.paths) ? dlOptions.paths.find((item: any) => item?.path)?.path : ''
          if (firstPath) {
            state.savepath = String(firstPath)
            state.selectedPath = state.savepath
          }
        }
        if (previewEnabled && dlOptions.supports_resource_preview && !allowBatchUrls && state.url) await loadPreview()
      } catch (e: any) {
        state.error = e?.message || '下载器配置读取失败'
        state.options = { categories: [] }
      } finally {
        state.loading = false
        render()
      }
    }

    async function loadPreview() {
      if (!state.options?.supports_resource_preview) return
      state.previewLoading = true
      state.previewError = ''
      state.previewData = null
      render()
      try {
        const previewUrl = String(state.url || state.urlsText || '').split(/\r?\n/).map((item: string) => item.trim()).filter(Boolean)[0] || ''
        if (!previewUrl) return
        state.previewData = await postJson(`/api/plugins/${state.downloaderId}/actions/resource_info`, { url: previewUrl, magnet: previewUrl })
      } catch (e: any) {
        state.previewError = e?.message || '资源预览失败'
      } finally {
        state.previewLoading = false
        render()
      }
    }

    async function submit() {
      if (state.submitting) return
      state.submitting = true
      state.submitStatus = 'running'
      state.submitProgress = 8
      state.error = ''
      state.submitButton?.__setState?.('running', 8, '8%')
      render()
      progressTimer = window.setInterval(() => {
        if (!state.submitting || state.submitStatus !== 'running') return
        state.submitProgress = Math.min(92, Number(state.submitProgress || 0) + 8)
        state.submitButton?.__setState?.('running', state.submitProgress, `${Math.round(state.submitProgress)}%`)
      }, 180)
      try {
        const urlList = String(allowBatchUrls ? state.urlsText : (state.url || state.urlsText || ''))
          .split(/\r?\n/)
          .map((item: string) => item.trim())
          .filter(Boolean)
        if (!urlList.length) throw new Error('请填写下载链接')
        if (maxUrls > 0 && urlList.length > maxUrls) throw new Error(`单次最多添加 ${maxUrls} 条链接`)
        const firstUrl = urlList[0] || ''
        const payload = {
          url: firstUrl,
          urls: allowBatchUrls ? urlList.join('\n') : firstUrl,
          magnet: firstUrl,
          title: state.title,
          name: state.name,
          rename: state.options?.supports_rename ? state.rename : '',
          savepath: state.options?.supports_savepath ? state.savepath : '',
          category: state.options?.supports_categories ? state.category : '',
          file_indices: state.options?.supports_file_indices ? state.fileIndices : undefined,
          min_file_size_mb: state.options?.supports_small_file_filter ? state.minFileSizeMb : undefined,
          source_plugin: sourcePluginId,
        }
        const result = await postJson(`/api/plugins/${state.downloaderId}/downloads`, payload)
        writeLastSavepath(state.downloaderId, state.savepath || '')
        const partialFailure = Number(result?.failure_count || 0) > 0
        state.submitStatus = partialFailure ? 'error' : 'success'
        state.submitProgress = 100
        if (partialFailure) {
          state.error = String(result?.message || `${result?.failure_count || 0} 条任务失败`)
          state.submitButton?.__setState?.('error', 100, submitPartialLabel)
        } else {
          state.submitButton?.__setState?.('success', 100, submitSuccessLabel)
        }
        render()
        return result
      } catch (e: any) {
        state.error = e?.message || '推送失败'
        state.submitStatus = 'error'
        state.submitProgress = 100
        state.submitButton?.__setState?.('error', 100, '推送失败')
        render()
        throw e
      } finally {
        state.submitting = false
        if (progressTimer) {
          window.clearInterval(progressTimer)
          progressTimer = null
        }
      }
    }

    function render() {
      const body = modal.body
      body.innerHTML = ''
      if (state.error) body.appendChild(Object.assign(document.createElement('div'), { className: 'noor-plugin-notice noor-plugin-notice--error', textContent: state.error }))
      const form = document.createElement('div')
      form.className = 'noor-downloader-form'

      if (showDownloaderField) {
        const downloaderInput = makeInput({ value: state.downloaderName || state.downloaderId, readonly: true })
        form.appendChild(makeField({ label: '下载器', control: downloaderInput }))
      }

      if (allowBatchUrls) {
        const urlsInput = document.createElement('textarea')
        urlsInput.className = 'noor-plugin-input noor-downloader-textarea'
        urlsInput.rows = Number(options.urlRows || 6)
        urlsInput.placeholder = String(options.urlPlaceholder || '每行一个 magnet / BT URL / 普通 URL')
        urlsInput.value = state.urlsText
        urlsInput.oninput = () => { state.urlsText = urlsInput.value }
        form.appendChild(makeField({
          label: options.urlLabel || '下载链接',
          hint: maxUrls > 0 ? `支持批量添加：每行一条，最多 ${maxUrls} 条。` : '支持批量添加：每行一条。',
          control: urlsInput,
        }))
      }

      const categories = Array.isArray(state.options?.categories) ? state.options.categories : []
      if (state.options?.supports_categories) {
        const categorySelect = makeSelect({
          value: state.category,
          options: [{ value: '', label: '不使用分类路径' }].concat(categories.map((item: any) => ({ value: item.name, label: `${item.name}${item.save_path ? ` · ${item.save_path}` : ''}` }))),
          onChange: (value: string) => {
            state.category = value
            const found = categories.find((item: any) => item.name === value)
            if (found?.save_path) state.savepath = String(found.save_path)
            render()
          },
        })
        form.appendChild(makeField({ label: '分类 / 路径建议', control: categorySelect }))
      }

      const paths = Array.isArray(state.options?.paths) ? state.options.paths.filter((item: any) => item?.path) : []
      if (state.options?.supports_savepath && paths.length) {
        const pathSelect = makeSelect({
          value: state.selectedPath || state.savepath,
          options: [{ value: '', label: '选择历史路径' }].concat(paths.map((item: any) => ({
            value: String(item.path || ''),
            label: String(item.name || item.path || ''),
          }))),
          onChange: (value: string) => {
            state.selectedPath = value
            if (value) state.savepath = value
            render()
          },
        })
        form.appendChild(makeField({ label: '历史路径', control: pathSelect, hint: '选择后仍可继续编辑为更深层的子目录。' }))
      }

      if (state.options?.supports_rename) {
        const renameInput = makeInput({
          value: state.rename,
          placeholder: state.itemTitle || '下载任务名称',
          onInput: (value: string) => {
            state.rename = value
            state.name = value
          },
        })
        if (state.titleOptions.length > 1) {
          const titleModeSelect = makeSelect({
            value: state.titleMode || String(state.titleOptions[0]?.key || ''),
            options: state.titleOptions.map((item: any) => ({ value: String(item.key || item.label || item.value || ''), label: String(item.label || item.key || '') })),
            onChange: (value: string) => {
              state.titleMode = value
              const found = state.titleOptions.find((item: any) => String(item.key || '') === value)
              if (found?.value) {
                state.rename = String(found.value)
                state.name = String(found.value)
              }
              render()
            },
          })
          const combo = document.createElement('div')
          combo.className = 'noor-downloader-title-combo'
          combo.append(renameInput, titleModeSelect)
          const activeHint = state.titleOptions.find((item: any) => String(item.key || '') === state.titleMode)?.hint || '优先使用智能命名'
          form.appendChild(makeField({ label: '下载任务名称', control: combo, hint: activeHint }))
        } else {
          form.appendChild(makeField({ label: '下载任务名称', control: renameInput }))
        }
      }

      if (state.options?.supports_savepath) {
        const savepathInput = makeInput({
          value: state.savepath,
          placeholder: '/downloads/av',
          onInput: (value: string) => {
            state.savepath = value
            state.selectedPath = value
          },
        })
        form.appendChild(makeField({ label: '下载路径', control: savepathInput, hint: '优先使用下载器插件返回的历史路径或默认路径。' }))
      }

      if (state.options?.supports_file_indices) {
        const fileOptions = Array.isArray(state.options?.file_indices_options) ? state.options.file_indices_options.filter(Boolean) : []
        const fileControl = fileOptions.length
          ? makeSelect({
              value: state.fileIndices,
              options: fileOptions.map((item: any) => ({ value: String(item.value ?? ''), label: String(item.label ?? item.value ?? '') })),
              onChange: (value: string) => { state.fileIndices = value },
            })
          : makeInput({
              value: state.fileIndices,
              placeholder: 'auto / --1 / 0 / 1,3',
              onInput: (value: string) => { state.fileIndices = value },
            })
        const fileHint = fileOptions.find((item: any) => String(item.value ?? '') === String(state.fileIndices))?.hint || ''
        form.appendChild(makeField({ label: '文件选择', control: fileControl, hint: fileHint || undefined }))
      }

      if (state.options?.supports_small_file_filter) {
        const filterInput = makeInput({
          value: state.minFileSizeMb,
          placeholder: String(state.options?.small_file_filter?.default_mb ?? '0'),
          onInput: (value: string) => { state.minFileSizeMb = value },
        })
        const filterHint = state.options?.small_file_filter?.keep_subtitles
          ? '自动过滤小于该阈值的非字幕文件，字幕始终保留。填 0 表示关闭。'
          : '自动过滤小于该阈值的文件。填 0 表示关闭。'
        form.appendChild(makeField({ label: '自动过滤小文件（MB）', control: filterInput, hint: filterHint }))
      }

      body.appendChild(form)
      if (state.loading) body.appendChild(makeLoadingState({ text: '读取下载器配置中…' }))
      else if (state.options?.supports_resource_preview) {
        body.appendChild(renderResourcePreview({
          options: state.options,
          loading: state.previewLoading,
          error: state.previewError,
          data: state.previewData,
        }))
      }

      const footer = document.createElement('div')
      footer.className = 'noor-plugin-modal__actions'
      const cancel = makeButton({ label: '关闭', onClick: () => !state.submitting && modal.close() })
      const submitBtn = makeSubmitButton({
        idleLabel: submitIdleLabel,
        submittingLabel: '推送中',
        successLabel: submitSuccessLabel,
        errorLabel: submitErrorLabel,
        status: state.submitStatus,
        progress: state.submitProgress,
        className: 'noor-downloader-submit',
        disabled: state.loading || !(allowBatchUrls ? String(state.urlsText || '').trim() : String(state.url || '').trim()) || !state.downloaderId || state.submitStatus === 'success',
        onClick: async () => {
          try {
            const result = await submit()
            options.onSuccess?.(result)
          } catch (e: any) {
            options.onError?.(e)
          }
        },
      })
      state.submitButton = submitBtn
      footer.append(cancel, submitBtn)
      const existingFooter = modal.el.querySelector('.noor-plugin-modal__actions')
      if (existingFooter) existingFooter.remove()
      modal.el.querySelector('.noor-plugin-modal')?.appendChild(footer)
    }

    await loadOptions()
    if (allowBatchUrls) {
      window.setTimeout(() => {
        const input = modal.body.querySelector('.noor-downloader-textarea') as HTMLTextAreaElement | null
        input?.focus()
      }, 0)
    }
    render()
    return modal
  }

  return { open, openTask: open }
}

function sdkFor(id: string) {
  const pluginFetch = (path: string, init?: RequestInit) => fetch(`/api/plugins/${id}${path}`, init)
  const downloads = createDownloaderDialogContext(id)
  return {
    pluginId: id,
    api: {
      plugin: pluginFetch,
      wsUrl: (path: string) => `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/api/plugins/${id}${path}`,
      get: (path: string, config?: any) => api.get(path, config),
      post: (path: string, data?: any, config?: any) => api.post(path, data, config),
    },
    toast: {
      success: (msg: string) => toast.success(msg),
      error: (msg: string) => toast.error(msg),
      info: (msg: string) => toast.info(msg),
      warning: (msg: string) => toast.warning(msg),
    },
    downloads,
    ui: {
      button: makeButton,
      input: makeInput,
      select: makeSelect,
      field: makeField,
      modal: makeModal,
      panel: makePanel,
      tabs: makeTabs,
      pagination: makePagination,
      submitButton: makeSubmitButton,
      topBar: makeTopBar,
      actionRow: makeActionRow,
      statCard: makeStatCard,
      statGrid: makeStatGrid,
      mediaCard: makeMediaCard,
      loadingState: makeLoadingState,
      badge: (o: any) => { const b = document.createElement(o.onClick ? 'button' : 'span'); b.className = ['noor-plugin-badge', o.tone ? `noor-plugin-badge--${o.tone}` : '', o.className || ''].filter(Boolean).join(' '); b.textContent = o.label || ''; if (o.onClick) (b as HTMLButtonElement).onclick = o.onClick; return b },
      chip: (o: any) => { const b = makeButton({ label: o.label, className: ['noor-plugin-chip', o.active ? 'is-active' : '', o.className || ''].filter(Boolean).join(' ') }); b.onclick = o.onClick; return b },
      notice: (o: any) => { const d = document.createElement('div'); d.className = `noor-plugin-notice noor-plugin-notice--${o.tone || 'info'}`; d.textContent = o.text || ''; return d },
      emptyState: (o: any) => { const d = document.createElement('div'); d.className = 'noor-plugin-state'; d.textContent = o.text || '暂无内容'; return d },
      errorState: (o: any) => { const d = document.createElement('div'); d.className = 'noor-plugin-state noor-plugin-state--error'; d.textContent = o.text || '加载失败'; return d },
      skeletonCard: (o: any) => { const d = document.createElement('div'); d.className = `noor-plugin-skeleton ${o.className || ''}`; return d },
      card: (o: any) => { const a = document.createElement(o.href ? 'a' : 'div'); a.className = `noor-plugin-card ${o.className || ''}`; if (o.href) { (a as HTMLAnchorElement).href = o.href; (a as HTMLAnchorElement).target = o.target || '_self' }; return a },
      confirm: (o: any) => confirm.confirm({ title: o.title || '确认操作', message: o.message || '', confirmText: o.confirmText || '确认', danger: !!o.danger }),
    },
  }
}

async function mountPlugin() {
  clearMounted()
  if (!pluginId.value || !host.value) return
  loading.value = true
  error.value = ''
  try {
    const info = await api.get(`/plugins/${pluginId.value}/config`).then(r => r.data)
    const style = info?.plugin?.frontend?.style
    if (style) {
      const bust = Date.now()
      styleEl = document.createElement('link')
      styleEl.rel = 'stylesheet'
      styleEl.href = `/api/plugins/${pluginId.value}/assets/${style.replace(/^frontend\//, '')}?t=${bust}`
      document.head.appendChild(styleEl)
    }
    const entry = info?.plugin?.frontend?.entry || 'frontend/page.js'
    const mod = await import(/* @vite-ignore */ `/api/plugins/${pluginId.value}/assets/${entry.replace(/^frontend\//, '')}?t=${Date.now()}`)
    await nextTick()
    const ret = await mod.mount(host.value, sdkFor(pluginId.value))
    if (typeof ret === 'function') dispose = ret
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || '插件加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(mountPlugin)
watch(pluginId, mountPlugin)
onBeforeUnmount(clearMounted)
</script>

<template>
  <div class="plugin-host-page">
    <div v-if="loading" class="plugin-host-state">插件加载中</div>
    <div v-if="error" class="plugin-host-state plugin-host-state--error">{{ error }}</div>
    <div ref="host" class="plugin-host-mount" :class="{ 'is-loading': loading }" />
  </div>
</template>

<style>
.plugin-host-page { min-height: 40vh; }
.plugin-host-state { padding: 1rem; margin-bottom: 1rem; border-radius: var(--radius-lg); background: rgba(255,255,255,.04); border: 1px solid rgba(255,255,255,.08); color: rgba(255,255,255,.7); }
.plugin-host-state--error { color: var(--color-error); border-color: rgba(227,26,26,.25); background: rgba(227,26,26,.1); }
.plugin-host-mount.is-loading { opacity: .6; }
.noor-plugin-topbar { display: flex; align-items: center; justify-content: space-between; gap: .75rem; margin-bottom: 1rem; flex-wrap: wrap; }
.noor-plugin-topbar__tabs, .noor-plugin-topbar__actions { display: flex; align-items: center; gap: .5rem; flex-wrap: wrap; }
.noor-plugin-btn { min-height: 30px; padding: .35rem .75rem; border-radius: var(--radius-md); border: 1px solid rgba(255,255,255,.08); background: rgba(255,255,255,.04); color: rgba(255,255,255,.78); font-size: .75rem; font-weight: 600; transition: all var(--transition-fast); }
.noor-plugin-btn:hover:not(:disabled) { background: rgba(255,255,255,.08); color: #fff; }
.noor-plugin-btn:disabled { opacity: .45; cursor: not-allowed; }
.noor-plugin-btn--primary { background: var(--color-brand); color: white; border-color: transparent; }
.noor-plugin-btn--danger { background: rgba(227,26,26,.18); color: #ff8a80; border-color: rgba(227,26,26,.28); }
.noor-plugin-input { width: 100%; min-height: 36px; padding: .5rem .75rem; border-radius: var(--radius-md); background: rgba(255,255,255,.05); border: 1px solid rgba(255,255,255,.08); color: white; outline: none; }
.noor-plugin-input:focus { border-color: var(--color-brand); box-shadow: 0 0 0 3px rgba(0,117,255,.12); }
.noor-plugin-select option { background: #111936; color: white; }
.noor-plugin-field { display: flex; flex-direction: column; gap: .35rem; }
.noor-plugin-field__label { font-size: .75rem; color: rgba(255,255,255,.52); font-weight: 600; }
.noor-plugin-field__hint { color: rgba(255,255,255,.35); }
.noor-plugin-modal-mask { position: fixed; inset: 0; z-index: var(--z-modal); display: flex; align-items: center; justify-content: center; padding: 1rem; background: rgba(0,0,0,.62); backdrop-filter: blur(10px); }
.noor-plugin-modal { width: min(560px, 100%); max-height: min(760px, 92vh); overflow: auto; border-radius: var(--radius-xl); background: rgb(26,31,55); border: 1px solid rgba(255,255,255,.08); box-shadow: var(--shadow-xl); }
.noor-plugin-modal--lg { width: min(920px, 100%); }
.noor-plugin-modal__head, .noor-plugin-modal__actions { display: flex; align-items: center; justify-content: space-between; gap: .75rem; padding: 1rem; border-bottom: 1px solid rgba(255,255,255,.06); }
.noor-plugin-modal__actions { justify-content: flex-end; border-top: 1px solid rgba(255,255,255,.06); border-bottom: 0; }
.noor-plugin-modal__title { color: white; font-weight: 700; }
.noor-plugin-modal__body { padding: 1rem; display: grid; gap: .85rem; }
.noor-plugin-tabs { position: relative; display: inline-flex; align-items: center; gap: .25rem; padding: .375rem; border-radius: var(--radius-xl); background: rgba(255,255,255,.04); border: 1px solid rgba(255,255,255,.06); max-width: 100%; overflow-x: auto; scrollbar-width: none; }
.noor-plugin-tabs::-webkit-scrollbar { display: none; }
.noor-plugin-tabs__marker { position: absolute; top: .375rem; bottom: .375rem; left: 0; border-radius: var(--radius-lg); background: var(--color-brand); box-shadow: 0 4px 12px rgba(0,117,255,.3); transition: none; z-index: 0; pointer-events: none; }
.noor-plugin-tabs--ready .noor-plugin-tabs__marker { transition: transform .25s cubic-bezier(.4,0,.2,1), width .25s cubic-bezier(.4,0,.2,1); }
.noor-plugin-tabs__item { position: relative; z-index: 1; min-height: 34px; padding: .5rem 1.5rem; border-radius: var(--radius-lg); color: rgba(255,255,255,.4); font-size: .875rem; font-weight: 600; white-space: nowrap; transition: color .2s ease; }
.noor-plugin-tabs__item:hover { color: rgba(255,255,255,.7); }
.noor-plugin-tabs__item.is-active { color: #fff; }
.noor-plugin-pagination, .noor-pagination { display: flex; justify-content: center; align-items: center; gap: .4rem; margin-top: 1rem; flex-wrap: wrap; }
.noor-pagination__btn { min-height: 30px; min-width: 30px; padding: .35rem .75rem; border-radius: var(--radius-md); border: 1px solid rgba(255,255,255,.08); background: rgba(255,255,255,.04); color: rgba(255,255,255,.78); font-size: .75rem; font-weight: 700; transition: all var(--transition-fast); }
.noor-pagination__btn:hover:not(:disabled) { background: rgba(255,255,255,.08); color: #fff; transform: translateY(-1px); }
.noor-pagination__btn:disabled { opacity: .38; cursor: not-allowed; }
.noor-pagination__page.is-active, .noor-pagination__btn.is-active { background: var(--color-brand); color: white; border-color: transparent; box-shadow: 0 4px 12px rgba(0,117,255,.25); }
.noor-plugin-badge { min-height: 28px; display: inline-flex; align-items: center; padding: .25rem .6rem; border-radius: var(--radius-pill); background: rgba(255,255,255,.06); border: 1px solid rgba(255,255,255,.08); color: rgba(255,255,255,.68); font-size: .75rem; }
.noor-plugin-chip { border-radius: var(--radius-pill); }
.noor-plugin-chip.is-active { background: var(--color-brand); color: white; }
.noor-plugin-notice, .noor-plugin-state { padding: 1rem; border-radius: var(--radius-lg); background: rgba(255,255,255,.04); border: 1px solid rgba(255,255,255,.08); color: rgba(255,255,255,.7); }
.noor-plugin-notice--error, .noor-plugin-state--error { color: #ff8a80; background: rgba(227,26,26,.1); border-color: rgba(227,26,26,.25); }
.noor-plugin-card { background: rgb(26,31,55); border: 1px solid rgba(255,255,255,.06); color: inherit; text-decoration: none; }
.noor-plugin-skeleton { min-height: 180px; border-radius: var(--radius-lg); background: linear-gradient(90deg, rgba(255,255,255,.04), rgba(255,255,255,.08), rgba(255,255,255,.04)); background-size: 200% 100%; animation: noor-skeleton 1.2s linear infinite; }
@keyframes noor-skeleton { to { background-position: -200% 0; } }
@media (max-width: 640px) { .noor-plugin-topbar { flex-direction: column-reverse; align-items: stretch; } .noor-plugin-topbar__actions { order: -1; } }
/* SDK visual contract: plugins must share main NOOR component metrics. */
.plugin-host-mount, .plugin-host-mount * { box-sizing: border-box; }
.noor-plugin-btn { height: 30px; min-height: 30px; display: inline-flex; align-items: center; justify-content: center; line-height: 1; font-family: var(--font-display); border-radius: var(--radius-button); }
.noor-plugin-btn--primary:hover:not(:disabled) { background: var(--color-brand-hover); border-color: transparent; }
.noor-plugin-modal__close { width: 30px; min-width: 30px; padding: 0; border-radius: 50%; font-size: 18px; line-height: 1; }
.noor-plugin-modal__close:hover:not(:disabled) { color: #fff; border-color: rgba(227,26,26,.35); background: rgba(227,26,26,.16); }
.detail-panel-topbar { display: flex; align-items: center; justify-content: space-between; gap: .75rem; }
.detail-panel-topbar__meta { min-width: 0; }
.detail-panel-topbar__eyebrow { display: inline-flex; align-items: center; min-height: 1.5rem; font-size: .72rem; letter-spacing: .08em; text-transform: uppercase; color: var(--color-text-muted); }
.detail-panel-topbar__close { width: 2.1rem; height: 2.1rem; flex: none; border-radius: .7rem; display: inline-flex; align-items: center; justify-content: center; color: var(--color-text-secondary); background: var(--color-bg-elevated); border: 1px solid var(--color-border-default); transition: color .16s ease, background .16s ease, border-color .16s ease, transform .16s ease; }
.detail-panel-topbar__close:hover { color: var(--color-text-primary); background: var(--color-bg-hover); border-color: var(--color-border-strong); transform: translateY(-1px); }
.noor-plugin-panel-mask { position: fixed; inset: 0; z-index: var(--z-modal); display: flex; justify-content: flex-end; background: rgba(0,0,0,.8); backdrop-filter: blur(8px); }
.noor-plugin-panel { position: relative; width: 100vw; height: 100vh; background: var(--color-bg-surface); border-left: 1px solid var(--color-border-default); box-shadow: var(--shadow-xl); overflow: hidden; }
.noor-plugin-panel__scroll { height: 100%; overflow-y: auto; padding: 1rem; display: grid; gap: 1rem; }
.noor-plugin-panel__head { padding: 0; }
.noor-plugin-panel__meta { min-width: 0; display: grid; gap: .2rem; }
.noor-plugin-panel__eyebrow { font-size: .72rem; letter-spacing: .08em; text-transform: uppercase; color: var(--color-text-muted); }
.noor-plugin-panel__title { color: #fff; font-weight: 700; font-size: 1rem; line-height: 1.35; }
.noor-plugin-panel__body { display: grid; gap: 1rem; }
.noor-plugin-panel__close { padding: 0; }
.noor-plugin-input { font-family: var(--font-display); }
.noor-plugin-tabs { font-family: var(--font-display); }
.noor-plugin-tabs__item { min-height: 34px; background: transparent; border: 0; cursor: pointer; }
.noor-plugin-badge--success, .noor-plugin-badge--good { border-color: rgba(1,181,116,.28); background: rgba(1,181,116,.10); color: #fff; }
.noor-plugin-badge--info { border-color: rgba(0,117,255,.36); background: rgba(0,117,255,.14); color: #fff; }
.noor-plugin-badge--warning, .noor-plugin-badge--warn { border-color: rgba(255,181,71,.28); background: rgba(255,181,71,.10); color: #fff; }
.noor-plugin-badge--error, .noor-plugin-badge--danger { border-color: rgba(227,26,26,.28); background: rgba(227,26,26,.10); color: #fff; }
.noor-plugin-card { border-radius: var(--radius-lg); background: var(--color-bg-surface); border: 1px solid var(--color-glass-border); box-shadow: 0 1px 0 rgba(255,255,255,.02) inset, 0 8px 18px rgba(0,0,0,.16); overflow: hidden; }


.noor-submit-btn { position: relative; overflow: hidden; min-width: 108px; isolation: isolate; }
.noor-submit-btn__bar { position: absolute; inset: 0 auto 0 0; width: var(--submit-progress, 0%); background: linear-gradient(90deg, rgba(0,117,255,.48), rgba(33,212,253,.34)); transition: width .18s ease-out, background var(--transition-fast); z-index: -1; }
.noor-submit-btn__text { position: relative; z-index: 1; white-space: nowrap; }
.noor-submit-btn.is-running { border-color: rgba(33,212,253,.45); background: rgba(33,212,253,.1); }
.noor-submit-btn.is-success { border-color: rgba(1,181,116,.46); background: rgba(1,181,116,.22); color: #fff; }
.noor-submit-btn.is-success .noor-submit-btn__bar { background: rgba(1,181,116,.36); }
.noor-submit-btn.is-error { border-color: rgba(227,26,26,.38); background: rgba(227,26,26,.14); color: #fff; }
.noor-submit-btn.is-error .noor-submit-btn__bar { background: rgba(227,26,26,.22); }

/* Promoted plugin patterns: reusable NOOR SDK components. */
.noor-plugin-action-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.noor-plugin-stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; }
.noor-plugin-stat-card { min-height: 58px; display: grid; align-content: center; gap: 3px; padding: 9px 12px; border-radius: var(--radius-lg); border: 1px solid var(--color-glass-border); background: var(--color-bg-surface); color: inherit; text-align: left; box-shadow: 0 1px 0 rgba(255,255,255,.02) inset, 0 8px 18px rgba(0,0,0,.16); }
button.noor-plugin-stat-card { cursor: pointer; transition: all var(--transition-fast); }
button.noor-plugin-stat-card:hover { transform: translateY(-1px); border-color: rgba(0,117,255,.3); background: var(--color-bg-elevated); }
.noor-plugin-stat-card__label { font-size: 12px; color: var(--color-text-muted); }
.noor-plugin-stat-card__value { font-size: 18px; color: #fff; font-weight: 750; line-height: 1.15; }
.noor-plugin-stat-card__hint { color: var(--color-text-muted); font-size: 11px; line-height: 1.25; }
.noor-plugin-stat-card--success { border-color: rgba(1,181,116,.2); background: rgba(1,181,116,.08); }
.noor-plugin-stat-card--info { border-color: rgba(0,117,255,.22); background: rgba(0,117,255,.09); }
.noor-plugin-stat-card--warning { border-color: rgba(255,181,71,.22); background: rgba(255,181,71,.08); }
.noor-plugin-stat-card--error { border-color: rgba(227,26,26,.22); background: rgba(227,26,26,.08); }
.noor-plugin-media-card { width: 100%; min-width: 0; display: flex; flex-direction: column; overflow: hidden; border-radius: var(--radius-lg); border: 1px solid var(--color-glass-border); background: var(--color-bg-surface); color: inherit; text-decoration: none; box-shadow: 0 1px 0 rgba(255,255,255,.02) inset, 0 8px 18px rgba(0,0,0,.16); transition: all var(--transition-fast); text-align: left; }
.noor-plugin-media-card--sharp { border-radius: 0; }
button.noor-plugin-media-card { cursor: pointer; }
.noor-plugin-media-card:hover { transform: translateY(-1px); border-color: rgba(0,117,255,.3); background: var(--color-bg-elevated); }
.noor-plugin-media-card__cover { aspect-ratio: 2184 / 1468; background: rgba(255,255,255,.04); overflow: hidden; }
.noor-plugin-media-card__cover.is-clickable, .noor-plugin-media-card__title.is-clickable { cursor: pointer; }
.noor-plugin-media-card__cover img { width: 100%; height: 100%; object-fit: cover; display: block; }
.noor-plugin-media-card__placeholder { height: 100%; display: flex; align-items: center; justify-content: center; color: var(--color-text-muted); font-size: 12px; }
.noor-plugin-media-card__body { display: grid; gap: 7px; padding: 10px; }
.noor-plugin-media-card__title { height: 38px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; color: #fff; font-size: 13px; font-weight: 750; line-height: 1.42; }
.noor-plugin-media-card__title.is-clickable:hover { color: rgba(255,255,255,.82); }
.noor-plugin-media-card__meta { display: flex; align-items: center; justify-content: space-between; gap: 8px; color: var(--color-text-muted); font-size: 11px; min-width: 0; }
.noor-plugin-media-card__meta span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.noor-plugin-media-card__badges { min-height: 22px; display: flex; flex-wrap: wrap; gap: 5px; }
.noor-plugin-media-card__actions { display: flex; justify-content: flex-end; gap: 8px; }
.noor-plugin-state--loading { display: flex; align-items: center; justify-content: center; gap: 10px; }
.noor-plugin-spinner { width: 14px; height: 14px; border-radius: 50%; border: 2px solid rgba(255,255,255,.16); border-top-color: var(--color-brand); animation: noor-plugin-spin .8s linear infinite; }
@keyframes noor-plugin-spin { to { transform: rotate(360deg); } }
.noor-downloader-form { display: grid; gap: 12px; }
.noor-downloader-submit { min-width: 132px; }
.noor-downloader-textarea { min-height: 120px; height: auto; resize: vertical; line-height: 1.45; padding-top: 10px; padding-bottom: 10px; }
.noor-downloader-title-combo { display: grid; grid-template-columns: minmax(0,1fr) 144px; gap: 8px; align-items: stretch; }
.noor-downloader-preview { display: grid; gap: 10px; padding: 12px; border-radius: var(--radius-lg); border: 1px solid var(--color-glass-border); background: rgba(255,255,255,.03); }
.noor-downloader-preview__head { display: flex; align-items: center; justify-content: space-between; gap: 12px; color: var(--color-text-secondary); font-size: 12px; }
.noor-downloader-preview__head span { color: #fff; font-weight: 700; }
.noor-downloader-preview__head .is-error { color: #ff8a80; }
.noor-downloader-preview__files { display: grid; gap: 6px; }
.noor-downloader-preview__file, .noor-downloader-preview__more { display: flex; align-items: center; justify-content: space-between; gap: 12px; font-size: 12px; color: var(--color-text-secondary); }
.noor-downloader-preview__file span, .noor-downloader-preview__file em { overflow: hidden; white-space: nowrap; text-overflow: ellipsis; font-style: normal; }
@media (max-width: 640px) { .noor-downloader-title-combo { grid-template-columns: 1fr; } }
</style>
