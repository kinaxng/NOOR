<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import { useToast } from '../composables/useToast'
import { useConfirm } from '../composables/useConfirm'
import { useSystemLog } from '../composables/useSystemLog'
import { createDownloaderDialogContext as createSharedDownloaderDialogContext } from '../composables/useDownloaderDialog'
import { openSubscriptionDialog } from '../composables/useSubscriptionDialog'

const route = useRoute()
const router = useRouter()
const toast = useToast()
const confirm = useConfirm()
const { show: showSystemLog } = useSystemLog()
const host = ref<HTMLElement | null>(null)
const loading = ref(false)
const error = ref('')
const pluginId = computed(() => String(route.params.pluginId || ''))
let dispose: null | (() => void) = null
let styleEl: HTMLLinkElement | null = null
let mountSeq = 0
let sdkAbortController: AbortController | null = null
let sdkCleanupFns: Array<() => void> = []

function isLifecycleCancelMessage(value: unknown) {
  const text = String(value || '').toLowerCase()
  return ['aborterror', 'err_canceled', 'operation was aborted', 'request aborted', 'request canceled', 'request cancelled', 'is unmounted', 'plugin unmounted', 'cancelederror'].some(token => text.includes(token))
}

function isAbortLikeError(error: any) {
  return error?.name === 'AbortError'
    || error?.name === 'CanceledError'
    || error?.code === 'ERR_CANCELED'
    || isLifecycleCancelMessage(error?.response?.data?.detail || error?.message)
}

function pluginDiagnostic(level: 'info' | 'warning' | 'error', message: string, sourceId = pluginId.value) {
  if (!showSystemLog.value || isLifecycleCancelMessage(message)) return
  void api.post('/system/logs/client', {
    level,
    source: `plugin.${sourceId || 'unknown'}.frontend`,
    message: String(message || '').slice(0, 2000),
    route: window.location.pathname + window.location.search,
  }).catch(() => {})
}

function shouldLogPluginRequest(path: string, level: 'info' | 'warning' | 'error' = 'info') {
  if (level !== 'info') return true
  const value = String(path || '').toLowerCase()
  if (value.includes('/ws/overview') || value.includes('/ws/metrics')) return false
  if (value.includes('/system/metrics')) return false
  if (value.includes('/actions/overview') || value.includes('/actions/metrics')) return false
  if (value.includes('/actions/status') || value.endsWith('/status')) return false
  if (value.includes('refresh-status') || value.includes('refresh_status')) return false
  return true
}

function errorMessage(error: any) {
  return error?.response?.data?.detail || error?.message || String(error || 'unknown error')
}

function clearMounted() {
  mountSeq += 1
  if (sdkAbortController) {
    try { sdkAbortController.abort() } catch {}
    sdkAbortController = null
  }
  for (const cleanup of sdkCleanupFns.splice(0)) {
    try { cleanup() } catch {}
  }
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
  type SelectItem = { value: string; label: string; disabled: boolean }
  const items = (Array.isArray(options.options) ? options.options : []).map((item: any) => ({
    value: String(item?.value ?? ''),
    label: String(item?.label ?? item?.value ?? ''),
    disabled: !!item?.disabled,
  })) as SelectItem[]
  let current = String(options.value ?? '')
  let open = false
  let detachOutside: null | (() => void) = null
  const wrap = document.createElement('div')
  wrap.className = ['noor-plugin-select', 'noor-plugin-select--pill', options.className || ''].filter(Boolean).join(' ')
  if (options.disabled) wrap.classList.add('is-disabled')
  const trigger = document.createElement('button')
  trigger.type = 'button'
  trigger.className = 'noor-plugin-select__trigger'
  trigger.disabled = !!options.disabled
  const labelNode = document.createElement('span')
  labelNode.className = 'noor-plugin-select__label'
  labelNode.textContent = String(options.label || '')
  const valueNode = document.createElement('span')
  valueNode.className = 'noor-plugin-select__value'
  const caret = document.createElement('span')
  caret.className = 'noor-plugin-select__caret'
  caret.setAttribute('aria-hidden', 'true')
  if (options.label) trigger.appendChild(labelNode)
  trigger.append(valueNode, caret)
  const menu = document.createElement('div')
  menu.className = 'noor-plugin-select__menu'
  menu.hidden = true
  const selectedItem = () => items.find(item => item.value === current) || items[0] || { value: '', label: '' }
  const syncLabel = () => {
    const selected = selectedItem()
    valueNode.textContent = selected.label || ''
    wrap.classList.toggle('is-active', !!current)
    trigger.title = selected.label || ''
  }
  const closeMenu = () => {
    if (!open) return
    open = false
    wrap.classList.remove('is-open')
    trigger.setAttribute('aria-expanded', 'false')
    menu.hidden = true
    detachOutside?.()
    detachOutside = null
  }
  const setValue = (value: string, emit = true) => {
    current = String(value ?? '')
    syncLabel()
    Array.from(menu.children).forEach(child => {
      const node = child as HTMLElement
      node.classList.toggle('is-active', node.dataset.value === current)
    })
    if (emit) options.onChange?.(current)
  }
  const renderOptions = () => {
    menu.innerHTML = ''
    for (const item of items) {
      const option = document.createElement('button')
      option.type = 'button'
      option.className = 'noor-plugin-select__option'
      option.dataset.value = item.value
      option.textContent = item.label
      option.disabled = item.disabled
      option.classList.toggle('is-active', item.value === current)
      option.onclick = event => {
        event.stopPropagation()
        if (item.disabled) return
        setValue(item.value)
        closeMenu()
        trigger.focus()
      }
      menu.appendChild(option)
    }
  }
  const openMenu = () => {
    if (options.disabled || open) return
    open = true
    wrap.classList.add('is-open')
    trigger.setAttribute('aria-expanded', 'true')
    menu.hidden = false
    detachOutside = () => document.removeEventListener('pointerdown', onOutside, true)
    document.addEventListener('pointerdown', onOutside, true)
  }
  const onOutside = (event: PointerEvent) => {
    if (!wrap.contains(event.target as Node)) closeMenu()
  }
  const moveSelection = (direction: number) => {
    const enabled = items.filter((item: SelectItem) => !item.disabled)
    if (!enabled.length) return
    const index = Math.max(0, enabled.findIndex((item: SelectItem) => item.value === current))
    const next = enabled[(index + direction + enabled.length) % enabled.length]
    setValue(next.value)
  }
  trigger.setAttribute('aria-haspopup', 'listbox')
  trigger.setAttribute('aria-expanded', 'false')
  trigger.onclick = event => {
    event.stopPropagation()
    open ? closeMenu() : openMenu()
  }
  trigger.onkeydown = event => {
    if (event.key === 'Escape') {
      closeMenu()
      return
    }
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault()
      if (!open) openMenu()
      moveSelection(event.key === 'ArrowDown' ? 1 : -1)
      return
    }
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      open ? closeMenu() : openMenu()
    }
  }
  renderOptions()
  syncLabel()
  wrap.append(trigger, menu)
  ;(wrap as any).__noorSetValue = (value: string) => setValue(value, false)
  Object.defineProperty(wrap, 'value', {
    get: () => current,
    set: value => setValue(String(value ?? ''), false),
  })
  return wrap
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
  const titleText = document.createElement('span')
  titleText.textContent = options.title || ''
  title.appendChild(titleText)
  if (options.titleMeta) {
    const titleMeta = document.createElement('span')
    titleMeta.className = 'noor-plugin-modal__title-meta'
    titleMeta.textContent = String(options.titleMeta)
    title.appendChild(titleMeta)
  }
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
  const routeConfig = options.route && typeof options.route === 'object' ? options.route as any : null
  const routeBasePath = routeConfig?.basePath ? String(routeConfig.basePath).replace(/^\/+|\/+$/g, '') : ''
  const routeMode = routeConfig?.mode || 'path'
  const routeReplace = routeConfig?.replace === true
  const routeDefaultReplace = routeConfig?.defaultReplace !== false
  const pathToValue = new Map<string, string>()
  const tabPath = (value: string) => {
    const tab = (Array.isArray(options.tabs) ? options.tabs : []).find((item: any) => getTabValue(item) === value)
    return String(tab?.path ?? tab?.route ?? value).replace(/^\/+|\/+$/g, '')
  }
  const valueFromRoute = () => {
    if (!routeConfig || routeMode !== 'path') return ''
    const raw = String(routeConfig.subPath?.() ?? routeConfig.subPath ?? '').replace(/^\/+|\/+$/g, '')
    const relative = routeBasePath && raw.startsWith(`${routeBasePath}/`) ? raw.slice(routeBasePath.length + 1) : raw
    const first = relative.split('/').filter(Boolean)[0]
    return first ? (pathToValue.get(first) || '') : ''
  }
  const syncRoute = (value: string, forceReplace = false) => {
    if (!routeConfig || routeMode !== 'path') return
    const next = [routeBasePath, tabPath(value)].filter(Boolean).join('/')
    const currentRaw = String(routeConfig.subPath?.() ?? routeConfig.subPath ?? '').replace(/^\/+|\/+$/g, '')
    if (currentRaw === next) return
    const nav = (forceReplace || routeReplace) ? routeConfig.replace : routeConfig.push
    nav?.(next)
  }
  const initialTabs = Array.isArray(options.tabs) ? options.tabs : []
  initialTabs.forEach((tab: any) => {
    const value = getTabValue(tab)
    pathToValue.set(tabPath(value) || value, value)
  })
  const routeValue = valueFromRoute()
  const providedValue = String(options.value ?? '')
  const initialValue = routeValue || providedValue || getTabValue(initialTabs[0])
  options.value = initialValue
  if (routeConfig && !routeValue && routeDefaultReplace) queueMicrotask(() => syncRoute(initialValue, true))
  if (routeConfig && routeValue && routeValue !== providedValue) {
    queueMicrotask(() => options.onChange?.(initialValue, { syncRoute: false, initial: true }))
  }
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
      syncRoute(value)
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
  const onRouteChange = () => {
    const next = valueFromRoute()
    if (!next || String(options.value ?? '') === next) return
    options.value = next
    refresh()
    options.onChange?.(next, { syncRoute: false })
    scheduleRefresh()
  }
  if (routeConfig) window.addEventListener('noor-plugin-route-change', onRouteChange)
  const dispose = () => {
    if (raf) cancelAnimationFrame(raf)
    window.removeEventListener('resize', scheduleRefresh)
    if (routeConfig) window.removeEventListener('noor-plugin-route-change', onRouteChange)
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

function makeControlPanelSection(options: any = {}) {
  const section = document.createElement('div')
  section.className = ['noor-control-panel__section', options.className || ''].filter(Boolean).join(' ')
  if (options.label) {
    const label = document.createElement('span')
    label.className = 'noor-control-panel__section-label'
    label.textContent = options.label
    section.appendChild(label)
  }
  const body = document.createElement('div')
  body.className = 'noor-control-panel__section-body'
  const children = options.items || options.children
  for (const item of (Array.isArray(children) ? children : [children]).filter(Boolean)) body.appendChild(item)
  section.appendChild(body)
  return section
}

function makeControlPanelGroup(options: any = {}) {
  const group = document.createElement('div')
  group.className = ['noor-control-panel__group', options.className || ''].filter(Boolean).join(' ')
  if (options.label) {
    const label = document.createElement('span')
    label.className = 'noor-control-panel__group-label'
    label.textContent = options.label
    group.appendChild(label)
  }
  const items = document.createElement('div')
  items.className = 'noor-control-panel__group-items'
  const children = options.items || options.children
  for (const item of (Array.isArray(children) ? children : [children]).filter(Boolean)) items.appendChild(item)
  group.appendChild(items)
  return group
}

function makeControlPanelRow(options: any = {}) {
  const row = document.createElement('div')
  row.className = ['noor-control-panel__row', options.className || ''].filter(Boolean).join(' ')
  const children = options.sections || options.items || options.children
  for (const item of (Array.isArray(children) ? children : [children]).filter(Boolean)) row.appendChild(item)
  return row
}

function makeControlPanel(options: any = {}) {
  const panel = document.createElement('section')
  panel.className = ['noor-control-panel', options.collapsible ? 'is-collapsible' : '', options.className || ''].filter(Boolean).join(' ')
  const collapseStorageKey = options.collapseKey ? `noor:filter-panel:${options.collapseKey}` : ''
  const legacyCollapseStorageKey = options.collapseKey ? `noor:control-panel:${options.collapseKey}` : ''
  const readCollapsed = () => {
    if (!options.collapsible) return false
    if (!collapseStorageKey) return options.defaultCollapsed !== false
    const saved = window.localStorage.getItem(collapseStorageKey)
    if (saved == null && legacyCollapseStorageKey) {
      const legacySaved = window.localStorage.getItem(legacyCollapseStorageKey)
      if (legacySaved != null) return legacySaved === '1'
    }
    if (saved == null) return options.defaultCollapsed !== false
    return saved === '1'
  }
  let collapsed = readCollapsed()
  const persistCollapsed = () => {
    if (!options.collapsible || !collapseStorageKey) return
    window.localStorage.setItem(collapseStorageKey, collapsed ? '1' : '0')
  }
  const rows = Array.isArray(options.rows) ? options.rows : []
  const extraRows: HTMLElement[] = []
  let collapseBtn: HTMLButtonElement | null = null
  let footer: HTMLDivElement | null = null
  const syncCollapsed = () => {
    panel.classList.toggle('is-collapsed', !!(options.collapsible && collapsed))
    extraRows.forEach(row => { row.style.display = options.collapsible && collapsed ? 'none' : '' })
    if (body.childNodes.length) body.style.display = options.collapsible && collapsed && rows.length ? 'none' : ''
    if (footer && footer.childNodes.length) footer.style.display = options.collapsible && collapsed ? 'none' : ''
    if (collapseBtn) {
      collapseBtn.title = collapsed ? '展开筛选面板' : '收起筛选面板'
    }
  }

  if (options.title || options.summary || options.headerActions || options.collapsible) {
    const header = document.createElement('div')
    header.className = 'noor-control-panel__header'
    const main = document.createElement('div')
    main.className = 'noor-control-panel__header-main'
    if (options.title) {
      const title = document.createElement('strong')
      title.className = 'noor-control-panel__title'
      title.textContent = options.title
      main.appendChild(title)
    }
    if (options.summary) {
      const summary = document.createElement('span')
      summary.className = 'noor-control-panel__summary'
      summary.textContent = options.summary
      main.appendChild(summary)
    }
    header.appendChild(main)
    if (options.headerActions || options.collapsible) {
      const actions = document.createElement('div')
      actions.className = 'noor-control-panel__header-actions'
      if (options.headerActions) {
        const headerActions = Array.isArray(options.headerActions) ? options.headerActions : [options.headerActions]
        for (const action of headerActions.filter(Boolean)) actions.appendChild(action)
      }
      if (options.collapsible) {
        collapseBtn = document.createElement('button')
        collapseBtn.type = 'button'
        collapseBtn.className = 'noor-control-panel__collapse-btn'
        collapseBtn.title = collapsed ? '展开筛选面板' : '收起筛选面板'
        const icon = document.createElement('span')
        icon.className = 'noor-control-panel__collapse-icon'
        icon.textContent = '⌃'
        collapseBtn.appendChild(icon)
        collapseBtn.onclick = () => {
          collapsed = !collapsed
          persistCollapsed()
          syncCollapsed()
        }
        actions.appendChild(collapseBtn)
      }
      header.appendChild(actions)
    }
    panel.appendChild(header)
  }

  const body = document.createElement('div')
  body.className = 'noor-control-panel__body'
  if (options.left) {
    const left = document.createElement('div')
    left.className = 'noor-control-panel__left'
    const leftChildren = Array.isArray(options.left) ? options.left : [options.left]
    for (const child of leftChildren.filter(Boolean)) left.appendChild(child)
    body.appendChild(left)
  }
  if (options.right) {
    const right = document.createElement('div')
    right.className = 'noor-control-panel__right'
    const rightChildren = Array.isArray(options.right) ? options.right : [options.right]
    for (const child of rightChildren.filter(Boolean)) right.appendChild(child)
    body.appendChild(right)
  }
  if (body.childNodes.length) panel.appendChild(body)

  for (const [index, rowConfig] of rows.entries()) {
    const row = makeControlPanelRow(rowConfig)
    if (row.childNodes.length) {
      row.classList.add(`noor-control-panel__row--${index === 0 ? 'primary' : index === 1 ? 'secondary' : 'tertiary'}`)
      if (index > 0) extraRows.push(row)
      panel.appendChild(row)
    }
  }

  if (options.footer) {
    footer = document.createElement('div')
    footer.className = 'noor-control-panel__footer'
    const footerChildren = Array.isArray(options.footer) ? options.footer : [options.footer]
    for (const child of footerChildren.filter(Boolean)) footer.appendChild(child)
    panel.appendChild(footer)
  }

  syncCollapsed()
  return panel
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

function sdkFor(id: string) {
  const controller = sdkAbortController || new AbortController()
  sdkAbortController = controller
  const ensureActive = () => {
    if (controller.signal.aborted) throw new DOMException('Plugin is unmounted.', 'AbortError')
  }
  const onUnmount = (cleanup: () => void) => {
    sdkCleanupFns.push(cleanup)
    return () => {
      const index = sdkCleanupFns.indexOf(cleanup)
      if (index >= 0) sdkCleanupFns.splice(index, 1)
    }
  }
  const pluginFetch = async (path: string, init?: RequestInit) => {
    ensureActive()
    try {
      return await fetch(`/api/plugins/${id}${path}`, { ...(init || {}), signal: init?.signal || controller.signal })
    } catch (error: any) {
      if (!isAbortLikeError(error)) pluginDiagnostic('error', `${path}: ${error?.message || '请求失败'}`, id)
      throw error
    }
  }
  const sdkGet = async (path: string, config?: any) => {
    ensureActive()
    const start = performance.now()
    try {
      const response = await api.get(path, { ...(config || {}), signal: config?.signal || controller.signal })
      if (shouldLogPluginRequest(path, 'info')) {
        pluginDiagnostic('info', `sdk.api.get ${path} status=${response.status} cost=${Math.round(performance.now() - start)}ms`, id)
      }
      return response
    } catch (error: any) {
      if (controller.signal.aborted || isAbortLikeError(error)) throw error
      pluginDiagnostic('error', `sdk.api.get ${path} failed cost=${Math.round(performance.now() - start)}ms error=${errorMessage(error)}`, id)
      throw error
    }
  }
  const sdkPost = async (path: string, data?: any, config?: any) => {
    ensureActive()
    const start = performance.now()
    try {
      const response = await api.post(path, data, { ...(config || {}), signal: config?.signal || controller.signal })
      if (shouldLogPluginRequest(path, 'info')) {
        pluginDiagnostic('info', `sdk.api.post ${path} status=${response.status} cost=${Math.round(performance.now() - start)}ms`, id)
      }
      return response
    } catch (error: any) {
      if (controller.signal.aborted || isAbortLikeError(error)) throw error
      pluginDiagnostic('error', `sdk.api.post ${path} failed cost=${Math.round(performance.now() - start)}ms error=${errorMessage(error)}`, id)
      throw error
    }
  }
  const downloads = createSharedDownloaderDialogContext(id)
  const basePath = `/plugins/${id}`
  const routeSubPath = () => {
    const path = route.path.startsWith(basePath) ? route.path.slice(basePath.length) : ''
    return path.replace(/^\/+/, '')
  }
  const pluginPath = (subPath = '') => {
    const clean = String(subPath || '').replace(/^\/+/, '')
    return clean ? `${basePath}/${clean}` : basePath
  }
  return {
    pluginId: id,
    navigate: (to: any) => router.push(to),
    route: {
      basePath,
      get path() { return route.path },
      get fullPath() { return route.fullPath },
      get subPath() { return routeSubPath() },
      push: (subPath = '', options: any = {}) => router.push({ path: pluginPath(subPath), query: options.query ?? route.query }),
      replace: (subPath = '', options: any = {}) => router.replace({ path: pluginPath(subPath), query: options.query ?? route.query }),
      onChange: (handler: (payload: any) => void) => {
        const onRoute = (event: Event) => {
          const detail = (event as CustomEvent).detail || {}
          if (!detail.pluginId || detail.pluginId === id) handler(detail)
        }
        window.addEventListener('noor-plugin-route-change', onRoute)
        const cleanup = () => window.removeEventListener('noor-plugin-route-change', onRoute)
        const off = onUnmount(cleanup)
        return () => { cleanup(); off() }
      },
    },
    api: {
      plugin: pluginFetch,
      wsUrl: (path: string) => `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/api/plugins/${id}${path}`,
      get: sdkGet,
      post: sdkPost,
    },
    lifecycle: {
      signal: controller.signal,
      get aborted() { return controller.signal.aborted },
      onUnmount,
    },
    timers: {
      setTimeout: (handler: TimerHandler, timeout?: number, ...args: any[]) => {
        ensureActive()
        const timer = window.setTimeout(handler, timeout, ...args)
        const off = onUnmount(() => window.clearTimeout(timer))
        return { id: timer, clear: () => { window.clearTimeout(timer); off() } }
      },
      setInterval: (handler: TimerHandler, timeout?: number, ...args: any[]) => {
        ensureActive()
        const timer = window.setInterval(handler, timeout, ...args)
        const off = onUnmount(() => window.clearInterval(timer))
        return { id: timer, clear: () => { window.clearInterval(timer); off() } }
      },
    },
    events: {
      on: (target: EventTarget, type: string, listener: EventListenerOrEventListenerObject, options?: AddEventListenerOptions | boolean) => {
        ensureActive()
        target.addEventListener(type, listener, options)
        const cleanup = () => target.removeEventListener(type, listener, options)
        const off = onUnmount(cleanup)
        return () => { cleanup(); off() }
      },
    },
    net: {
      webSocket: (path: string) => {
        ensureActive()
        const ws = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/api/plugins/${id}${path}`)
        onUnmount(() => {
          try { ws.close() } catch {}
        })
        return ws
      },
    },
    toast: {
      success: (msg: string) => toast.success(msg),
      error: (msg: string) => { if (!isLifecycleCancelMessage(msg)) toast.error(msg) },
      info: (msg: string) => toast.info(msg),
      warning: (msg: string) => { if (!isLifecycleCancelMessage(msg)) toast.warning(msg) },
    },
    downloads,
    subscription: {
      open: (options: any) => openSubscriptionDialog(options),
    },
    avatar: {
      candidates: (options: any = {}) => sdkPost('/plugins/gfriends/actions/candidates', { payload: options }).then((r: any) => r.data),
    },
    ui: {
      button: makeButton,
      input: makeInput,
      select: makeSelect,
      field: makeField,
      modal: makeModal,
      panel: makePanel,
      tabs: makeTabs,
      pagination: makePagination,
      filterPanel: makeControlPanel,
      controlPanel: makeControlPanel,
      filterPanelGroup: makeControlPanelGroup,
      controlPanelGroup: makeControlPanelGroup,
      filterPanelSection: makeControlPanelSection,
      controlPanelSection: makeControlPanelSection,
      filterPanelRow: makeControlPanelRow,
      controlPanelRow: makeControlPanelRow,
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
  const currentMount = mountSeq
  const controller = new AbortController()
  sdkAbortController = controller
  loading.value = true
  error.value = ''
  const start = performance.now()
  pluginDiagnostic('info', '插件页面开始加载', pluginId.value)
  try {
    const info = await api.get(`/plugins/${pluginId.value}/config`, { signal: controller.signal }).then(r => r.data)
    if (currentMount !== mountSeq) return
    const entry = info?.plugin?.frontend?.entry
    if (!entry) {
      if (host.value) {
        host.value.innerHTML = ''
        const notice = document.createElement('div')
        notice.className = 'noor-plugin-state'
        notice.textContent = '该插件没有独立页面，请通过资源搜索使用。'
        host.value.appendChild(notice)
      }
      pluginDiagnostic('info', '插件没有独立前端页面', pluginId.value)
      return
    }
    const style = info?.plugin?.frontend?.style
    if (style) {
      const bust = Date.now()
      styleEl = document.createElement('link')
      styleEl.rel = 'stylesheet'
      styleEl.href = `/api/plugins/${pluginId.value}/assets/${style.replace(/^frontend\//, '')}?t=${bust}`
      document.head.appendChild(styleEl)
    }
    const mod = await import(/* @vite-ignore */ `/api/plugins/${pluginId.value}/assets/${entry.replace(/^frontend\//, '')}?t=${Date.now()}`)
    if (currentMount !== mountSeq) return
    await nextTick()
    if (currentMount !== mountSeq || !host.value) return
    const ret = await mod.mount(host.value, sdkFor(pluginId.value))
    if (currentMount !== mountSeq) {
      if (typeof ret === 'function') ret()
      return
    }
    if (typeof ret === 'function') dispose = ret
    pluginDiagnostic('info', `插件页面加载完成 cost=${Math.round(performance.now() - start)}ms`, pluginId.value)
  } catch (e: any) {
    if (!isAbortLikeError(e) && currentMount === mountSeq) {
      error.value = e?.response?.data?.detail || e?.message || '插件加载失败'
      pluginDiagnostic('error', error.value)
    }
  } finally {
    if (currentMount === mountSeq) loading.value = false
  }
}

onMounted(mountPlugin)
watch(pluginId, mountPlugin)
watch(() => route.fullPath, () => {
  window.dispatchEvent(new CustomEvent('noor-plugin-route-change', {
    detail: {
      path: route.path,
      fullPath: route.fullPath,
      pluginId: pluginId.value,
    },
  }))
})
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
.noor-plugin-input option, .noor-plugin-select option { background: #111936; color: white; }
.noor-plugin-select { position: relative; min-width: 0; }
.noor-plugin-select__trigger { width: 100%; min-height: 1.85rem; display: inline-flex; align-items: center; justify-content: space-between; gap: .35rem; padding: .32rem .68rem; border: 1px solid rgba(255,255,255,.12); border-radius: 999px; background: rgba(255,255,255,.04); color: var(--color-text-primary,#fff); font-size: .76rem; font-weight: 700; line-height: 1.1; white-space: nowrap; cursor: pointer; transition: border-color .18s ease, background .18s ease, color .18s ease, box-shadow .18s ease; }
.noor-plugin-select__trigger:hover:not(:disabled), .noor-plugin-select.is-open .noor-plugin-select__trigger { border-color: color-mix(in srgb, var(--color-brand,#0075ff) 45%, transparent); background: color-mix(in srgb, var(--color-brand,#0075ff) 10%, transparent); }
.noor-plugin-select.is-active .noor-plugin-select__trigger { border-color: color-mix(in srgb, var(--color-brand,#0075ff) 52%, transparent); background: color-mix(in srgb, var(--color-brand,#0075ff) 16%, transparent); color: color-mix(in srgb, var(--color-brand,#0075ff) 28%, white); }
.noor-plugin-select__trigger:focus-visible { outline: none; border-color: var(--color-brand,#0075ff); box-shadow: 0 0 0 3px rgba(0,117,255,.14); }
.noor-plugin-select__trigger:disabled { opacity: .5; cursor: not-allowed; }
.noor-plugin-select__label { flex: none; color: inherit; opacity: .68; font-weight: 650; }
.noor-plugin-select__value { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.noor-plugin-select__caret { flex: none; width: 0; height: 0; border-left: .22rem solid transparent; border-right: .22rem solid transparent; border-top: .28rem solid currentColor; opacity: .65; transition: transform .18s ease; }
.noor-plugin-select.is-open .noor-plugin-select__caret { transform: rotate(180deg); }
.noor-plugin-select__menu { position: absolute; z-index: calc(var(--z-modal,1000) + 20); top: calc(100% + 6px); left: 0; min-width: 100%; max-width: min(28rem, calc(100vw - 2rem)); max-height: 18rem; overflow: auto; display: flex; flex-direction: column; gap: .25rem; padding: .45rem; border: 1px solid rgba(255,255,255,.1); border-radius: var(--radius-lg,.8rem); background: color-mix(in srgb, var(--color-bg-elevated,rgb(30,37,68)) 94%, black); box-shadow: 0 16px 42px rgba(0,0,0,.42); backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px); }
.noor-plugin-select__menu[hidden] { display: none; }
.noor-plugin-select__option { width: 100%; min-height: 1.85rem; display: flex; align-items: center; text-align: left; padding: .32rem .62rem; border: 1px solid transparent; border-radius: var(--radius-md,.55rem); background: transparent; color: var(--color-text-secondary,rgba(255,255,255,.72)); font-size: .76rem; font-weight: 650; cursor: pointer; }
.noor-plugin-select__option:hover:not(:disabled) { border-color: color-mix(in srgb, var(--color-brand,#0075ff) 34%, transparent); background: color-mix(in srgb, var(--color-brand,#0075ff) 10%, transparent); color: #fff; }
.noor-plugin-select__option.is-active { border-color: color-mix(in srgb, var(--color-brand,#0075ff) 45%, transparent); background: color-mix(in srgb, var(--color-brand,#0075ff) 18%, transparent); color: color-mix(in srgb, var(--color-brand,#0075ff) 24%, white); }
.noor-plugin-select__option:disabled { opacity: .45; cursor: not-allowed; }
.noor-plugin-field { display: flex; flex-direction: column; gap: .35rem; }
.noor-plugin-field__label { font-size: .75rem; color: rgba(255,255,255,.52); font-weight: 600; }
.noor-plugin-field__hint { color: rgba(255,255,255,.35); }
.noor-plugin-modal-mask { position: fixed; inset: 0; z-index: var(--z-modal); display: flex; align-items: center; justify-content: center; padding: 1rem; background: rgba(0,0,0,.62); backdrop-filter: blur(10px); }
.noor-plugin-modal { width: min(560px, 100%); max-height: min(760px, 92vh); display: flex; flex-direction: column; overflow: hidden; border-radius: var(--radius-xl); background: rgb(26,31,55); border: 1px solid rgba(255,255,255,.08); box-shadow: var(--shadow-xl); }
.noor-plugin-modal--lg { width: min(920px, 100%); }
.noor-plugin-modal__head, .noor-plugin-modal__actions { display: flex; align-items: center; justify-content: space-between; gap: .75rem; padding: 1rem; border-bottom: 1px solid rgba(255,255,255,.06); }
.noor-plugin-modal__actions { justify-content: flex-end; border-top: 1px solid rgba(255,255,255,.06); border-bottom: 0; flex: none; }
.noor-plugin-modal__title { display: inline-flex; align-items: baseline; gap: .45rem; color: white; font-weight: 700; }
.noor-plugin-modal__title-meta { color: rgba(255,255,255,.46); font-size: .8em; font-weight: 600; }
.noor-plugin-modal__body { padding: 1rem; display: grid; gap: .85rem; overflow: auto; min-height: 0; }
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
