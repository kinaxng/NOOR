import api from '../api'

let styleInjected = false
let lastSavepathCache: Record<string, string> | null = null

function injectStyle() {
  if (styleInjected || typeof document === 'undefined') return
  styleInjected = true
  const style = document.createElement('style')
  style.id = 'noor-downloader-dialog-style'
  style.textContent = `
.noor-plugin-modal-mask{position:fixed;inset:0;z-index:var(--z-modal,1000);display:flex;align-items:center;justify-content:center;padding:1rem;background:rgba(0,0,0,.62);backdrop-filter:blur(10px)}
.noor-plugin-modal{width:min(560px,100%);max-height:min(760px,92vh);display:flex;flex-direction:column;overflow:hidden;border-radius:var(--radius-xl);background:rgb(26,31,55);border:1px solid rgba(255,255,255,.08);box-shadow:var(--shadow-xl,0 24px 64px rgba(0,0,0,.45))}
.noor-plugin-modal--lg{width:min(920px,100%)}.noor-plugin-modal__head,.noor-plugin-modal__actions{display:flex;align-items:center;justify-content:space-between;gap:.75rem;padding:1rem;border-bottom:1px solid rgba(255,255,255,.06)}
.noor-plugin-modal__actions{justify-content:flex-end;border-top:1px solid rgba(255,255,255,.06);border-bottom:0;flex:none}.noor-plugin-modal__title{display:inline-flex;align-items:baseline;gap:.45rem;color:white;font-weight:700}.noor-plugin-modal__body{padding:1rem;display:grid;gap:.85rem;overflow:auto;min-height:0}
.noor-plugin-btn{height:32px;display:inline-flex;align-items:center;justify-content:center;gap:.35rem;padding:0 .85rem;border-radius:var(--radius-button,.65rem);border:1px solid rgba(255,255,255,.08);background:rgba(255,255,255,.04);color:var(--color-text-secondary,#cbd5e1);font-size:.76rem;font-weight:750;cursor:pointer}.noor-plugin-btn:hover:not(:disabled){border-color:rgba(0,117,255,.28);background:rgba(0,117,255,.11);color:#fff}.noor-plugin-btn:disabled{opacity:.58;cursor:default}.noor-plugin-btn--primary{border-color:rgba(0,117,255,.34);background:rgba(0,117,255,.16);color:#fff}.noor-plugin-modal__close{width:30px;min-width:30px;padding:0;border-radius:50%;font-size:18px;line-height:1}
.noor-plugin-field{display:grid;gap:.38rem}.noor-plugin-field__label{color:var(--color-text-muted,#94a3b8);font-size:.72rem;font-weight:750}.noor-plugin-field__hint{color:var(--color-text-muted,#94a3b8);font-size:.7rem;line-height:1.45}.noor-plugin-input{width:100%;min-height:36px;border:1px solid var(--color-border-default,rgba(255,255,255,.1));border-radius:var(--radius-md,.55rem);background:rgba(255,255,255,.045);color:#fff;font:inherit;font-size:.8rem;padding:0 .65rem}.noor-plugin-input[readonly]{color:var(--color-text-secondary,#cbd5e1)}.noor-downloader-textarea{min-height:92px;padding:.65rem;resize:vertical}.noor-downloader-form{display:grid;gap:.75rem}.noor-downloader-title-combo{display:grid;grid-template-columns:minmax(0,1fr) minmax(9rem,auto);gap:.5rem}
.noor-plugin-notice{padding:.75rem .85rem;border-radius:var(--radius-lg,.8rem);font-size:.8rem;font-weight:700}.noor-plugin-notice--error{border:1px solid rgba(239,68,68,.24);background:rgba(239,68,68,.12);color:#fecaca}.noor-loading-state{min-height:48px;display:flex;align-items:center;gap:.5rem;color:var(--color-text-secondary,#cbd5e1);font-size:.8rem}.noor-loading-state:before{content:'';width:1rem;height:1rem;border-radius:999px;border:2px solid rgba(255,255,255,.18);border-top-color:#fff;animation:noor-spin .8s linear infinite}@keyframes noor-spin{to{transform:rotate(360deg)}}
.noor-submit-btn{position:relative;overflow:hidden;isolation:isolate;min-width:108px}.noor-submit-btn__bar{position:absolute;inset:0 auto 0 0;width:var(--submit-progress,0);background:linear-gradient(90deg,rgba(0,117,255,.52),rgba(33,212,253,.34));z-index:-1;transition:width .2s ease}.noor-submit-btn__text{position:relative;z-index:1;white-space:nowrap}.noor-submit-btn.is-success{border-color:rgba(1,181,116,.46);background:rgba(1,181,116,.22)}.noor-submit-btn.is-error{border-color:rgba(227,26,26,.38);background:rgba(227,26,26,.14)}
.noor-downloader-preview{display:grid;gap:.55rem;padding:.75rem;border:1px solid rgba(255,255,255,.07);border-radius:var(--radius-lg,.8rem);background:rgba(255,255,255,.025)}.noor-downloader-preview__head{display:flex;justify-content:space-between;gap:.75rem;color:#fff;font-size:.78rem;font-weight:750}.noor-downloader-preview__head em{color:var(--color-text-muted,#94a3b8);font-style:normal}.noor-downloader-preview__head .is-error{color:#fca5a5}.noor-downloader-preview__files{display:grid;gap:.35rem}.noor-downloader-preview__file{display:flex;justify-content:space-between;gap:.75rem;color:var(--color-text-secondary,#cbd5e1);font-size:.72rem}.noor-downloader-preview__file span{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.noor-downloader-preview__file em,.noor-downloader-preview__more{color:var(--color-text-muted,#94a3b8);font-style:normal;font-size:.7rem}`
  document.head.appendChild(style)
}

function escapeHtml(value: any) {
  return String(value ?? '').replace(/[&<>'"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[c]!))
}

function makeButton(options: any = {}) {
  const btn = document.createElement('button')
  btn.type = 'button'
  btn.className = ['noor-plugin-btn', options.tone === 'primary' ? 'noor-plugin-btn--primary' : '', options.className || ''].filter(Boolean).join(' ')
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
  field.className = 'noor-plugin-field'
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
  injectStyle()
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
  panel.append(head, body)
  mask.appendChild(panel)
  const close = () => { mask.remove(); options.onClose?.() }
  closeBtn.onclick = close
  mask.onclick = event => { if (event.target === mask && options.closeOnMask !== false) close() }
  document.body.appendChild(mask)
  return { el: mask, body, close }
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
    btn.classList.toggle('is-running', next === 'running')
    btn.classList.toggle('is-success', next === 'success')
    btn.classList.toggle('is-error', next === 'error')
    btn.style.setProperty('--submit-progress', `${pct}%`)
    text.textContent = labelFor(next, pct, label)
    btn.disabled = !!options.disabled || next === 'running' || next === 'success'
  }
  btn.onclick = event => { if (!btn.disabled) options.onClick?.(event) }
  ;(btn as any).__setState = setState
  setState(options.status || 'idle', Number(options.progress || 0), options.labelOverride || '')
  return btn
}

function makeLoadingState(options: any = {}) {
  const div = document.createElement('div')
  div.className = 'noor-loading-state'
  div.textContent = options.text || '加载中…'
  return div
}

function readLastSavepath(id: string) {
  try {
    if (!lastSavepathCache) lastSavepathCache = JSON.parse(localStorage.getItem('noor.downloader.savepaths') || '{}')
    return lastSavepathCache?.[id] || ''
  } catch { return '' }
}

function writeLastSavepath(id: string, value: string) {
  try {
    lastSavepathCache = { ...(lastSavepathCache || {}), [id]: value }
    localStorage.setItem('noor.downloader.savepaths', JSON.stringify(lastSavepathCache))
  } catch {}
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
  d.innerHTML = `<div class="noor-downloader-preview__head"><span>资源预览</span><em>${escapeHtml(resourceState.data?.total_size_formatted || '')} · ${files.length} 个文件</em></div><div class="noor-downloader-preview__files">${visible.map((file: any) => `<div class="noor-downloader-preview__file"><span>${escapeHtml(file.name || file.full_path || '')}</span><em>${escapeHtml(file.size_formatted || '')}</em></div>`).join('')}${files.length > visible.length ? `<div class="noor-downloader-preview__more">还有 ${files.length - visible.length} 个文件</div>` : ''}</div>`
  return d
}

async function postJson(url: string, payload: any) {
  const { data } = await api.post(url.replace(/^\/api/, ''), { payload })
  if (data?.ok === false) throw new Error(data?.detail || data?.message || '请求失败')
  return data
}

export function createDownloaderDialogContext(sourcePluginId: string) {
  let progressTimer: number | null = null

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
      downloaderIds: Array.isArray(options.downloaderIds) ? options.downloaderIds.map((item: any) => String(item || '').trim()).filter(Boolean) : [],
      downloaderChoices: [], title: String(options.title || ''), name: String(options.name || options.rename || options.title || ''), rename: String(options.rename || options.name || options.title || ''),
      titleOptions: Array.isArray(options.titleOptions) ? options.titleOptions.filter(Boolean) : [], titleMode: String(options.titleMode || ''),
      url: String(options.url || options.magnet || options.urls || ''), urlsText: String(options.urlsText || options.urls || options.url || options.magnet || ''), itemTitle: String(options.itemTitle || options.title || ''),
      fileIndices: 'auto', savepath: '', selectedPath: '', category: '', minFileSizeMb: '', options: null, error: '', loading: true, previewLoading: false, previewError: '', previewData: null, submitStatus: 'idle', submitProgress: 0, submitting: false, submitButton: null as any,
    }
    if (!state.downloaderId && state.downloaderIds.length) state.downloaderId = state.downloaderIds[0]
    if (!state.downloaderId) throw new Error('未绑定下载器')
    if (!allowBatchUrls && !state.url) throw new Error('缺少下载链接')
    if (!state.titleMode && state.titleOptions.length) state.titleMode = String(state.titleOptions[0]?.key || '')

    const modal = makeModal({ title: String(options.modalTitle || (allowBatchUrls ? '新建下载任务' : '推送下载')), width: 'md', closeOnMask: false, onClose: () => { if (state.submitting) return; if (progressTimer) window.clearInterval(progressTimer) } })

    async function loadPreview() {
      if (!state.options?.supports_resource_preview) return
      state.previewLoading = true; state.previewError = ''; state.previewData = null; render()
      try {
        const previewUrl = String(state.url || state.urlsText || '').split(/\r?\n/).map((item: string) => item.trim()).filter(Boolean)[0] || ''
        if (!previewUrl) return
        state.previewData = await postJson(`/plugins/${state.downloaderId}/actions/resource_info`, { url: previewUrl, magnet: previewUrl })
      } catch (e: any) { state.previewError = e?.message || '资源预览失败' }
      finally { state.previewLoading = false; render() }
    }

    async function loadOptions() {
      state.loading = true; state.error = ''; render()
      try {
        if (state.downloaderIds.length > 1 && !state.downloaderChoices.length) {
          const pluginList = await api.get('/plugins').then(r => r.data).catch(() => [])
          const lookup = new Map((Array.isArray(pluginList) ? pluginList : []).map((item: any) => [String(item.id || ''), String(item.name || item.id || '')]))
          state.downloaderChoices = state.downloaderIds.map((id: string) => ({ value: id, label: lookup.get(id) || id }))
        }
        const infoRes = await api.get(`/plugins/${state.downloaderId}/config`).then(r => r.data).catch(() => null)
        const dlOptions = await postJson(`/plugins/${state.downloaderId}/actions/download_options`, {})
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
          if (firstPath) { state.savepath = String(firstPath); state.selectedPath = state.savepath }
        }
        if (previewEnabled && dlOptions.supports_resource_preview && !allowBatchUrls && state.url) await loadPreview()
      } catch (e: any) { state.error = e?.message || '下载器配置读取失败'; state.options = { categories: [] } }
      finally { state.loading = false; render() }
    }

    async function submit() {
      if (state.submitting) return
      state.submitting = true; state.submitStatus = 'running'; state.submitProgress = 8; state.error = ''; state.submitButton?.__setState?.('running', 8, '8%'); render()
      progressTimer = window.setInterval(() => { if (!state.submitting || state.submitStatus !== 'running') return; state.submitProgress = Math.min(92, Number(state.submitProgress || 0) + 8); state.submitButton?.__setState?.('running', state.submitProgress, `${Math.round(state.submitProgress)}%`) }, 180)
      try {
        const urlList = String(allowBatchUrls ? state.urlsText : (state.url || state.urlsText || '')).split(/\r?\n/).map((item: string) => item.trim()).filter(Boolean)
        if (!urlList.length) throw new Error('请填写下载链接')
        if (maxUrls > 0 && urlList.length > maxUrls) throw new Error(`单次最多添加 ${maxUrls} 条链接`)
        const firstUrl = urlList[0] || ''
        const payload = { url: firstUrl, urls: allowBatchUrls ? urlList.join('\n') : firstUrl, magnet: firstUrl, title: state.title, name: state.name, rename: state.options?.supports_rename ? state.rename : '', savepath: state.options?.supports_savepath ? state.savepath : '', category: state.options?.supports_categories ? state.category : '', file_indices: state.options?.supports_file_indices ? state.fileIndices : undefined, min_file_size_mb: state.options?.supports_small_file_filter ? state.minFileSizeMb : undefined, source_plugin: options.sourcePluginId || sourcePluginId }
        const result = await postJson(`/plugins/${state.downloaderId}/downloads`, payload)
        writeLastSavepath(state.downloaderId, state.savepath || '')
        const partialFailure = Number(result?.failure_count || 0) > 0
        state.submitStatus = partialFailure ? 'error' : 'success'; state.submitProgress = 100
        if (partialFailure) { state.error = String(result?.message || `${result?.failure_count || 0} 条任务失败`); state.submitButton?.__setState?.('error', 100, submitPartialLabel) }
        else state.submitButton?.__setState?.('success', 100, submitSuccessLabel)
        render(); return result
      } catch (e: any) { state.error = e?.message || '推送失败'; state.submitStatus = 'error'; state.submitProgress = 100; state.submitButton?.__setState?.('error', 100, submitErrorLabel); render(); throw e }
      finally { state.submitting = false; if (progressTimer) { window.clearInterval(progressTimer); progressTimer = null } }
    }

    function render() {
      const body = modal.body
      body.innerHTML = ''
      if (state.error) body.appendChild(Object.assign(document.createElement('div'), { className: 'noor-plugin-notice noor-plugin-notice--error', textContent: state.error }))
      const form = document.createElement('div')
      form.className = 'noor-downloader-form'
      if (showDownloaderField && state.downloaderIds.length > 1) {
        form.appendChild(makeField({ label: '下载器', control: makeSelect({ value: state.downloaderId, options: state.downloaderChoices.length ? state.downloaderChoices : state.downloaderIds.map((id: string) => ({ value: id, label: id })), onChange: (value: string) => { if (!value || value === state.downloaderId) return; state.downloaderId = value; state.downloaderName = state.downloaderChoices.find((item: any) => item.value === value)?.label || value; void loadOptions() } }) }))
      } else if (showDownloaderField) form.appendChild(makeField({ label: '下载器', control: makeInput({ value: state.downloaderName || state.downloaderId, readonly: true }) }))
      if (allowBatchUrls) {
        const urlsInput = document.createElement('textarea'); urlsInput.className = 'noor-plugin-input noor-downloader-textarea'; urlsInput.rows = Number(options.urlRows || 6); urlsInput.placeholder = String(options.urlPlaceholder || '每行一个 magnet / BT URL / 普通 URL'); urlsInput.value = state.urlsText; urlsInput.oninput = () => { state.urlsText = urlsInput.value }
        form.appendChild(makeField({ label: options.urlLabel || '下载链接', hint: maxUrls > 0 ? `支持批量添加：每行一条，最多 ${maxUrls} 条。` : '支持批量添加：每行一条。', control: urlsInput }))
      }
      const categories = Array.isArray(state.options?.categories) ? state.options.categories : []
      if (state.options?.supports_categories) form.appendChild(makeField({ label: '分类 / 路径建议', control: makeSelect({ value: state.category, options: [{ value: '', label: '不使用分类路径' }].concat(categories.map((item: any) => ({ value: item.name, label: `${item.name}${item.save_path ? ` · ${item.save_path}` : ''}` }))), onChange: (value: string) => { state.category = value; const found = categories.find((item: any) => item.name === value); if (found?.save_path) state.savepath = String(found.save_path); render() } }) }))
      const paths = Array.isArray(state.options?.paths) ? state.options.paths.filter((item: any) => item?.path) : []
      if (state.options?.supports_savepath && paths.length) form.appendChild(makeField({ label: '历史路径', control: makeSelect({ value: state.selectedPath || state.savepath, options: [{ value: '', label: '选择历史路径' }].concat(paths.map((item: any) => ({ value: String(item.path || ''), label: String(item.name || item.path || '') }))), onChange: (value: string) => { state.selectedPath = value; if (value) state.savepath = value; render() } }), hint: '选择后仍可继续编辑为更深层的子目录。' }))
      if (state.options?.supports_rename) {
        const renameInput = makeInput({ value: state.rename, placeholder: state.itemTitle || '下载任务名称', onInput: (value: string) => { state.rename = value; state.name = value } })
        if (state.titleOptions.length > 1) {
          const titleModeSelect = makeSelect({ value: state.titleMode || String(state.titleOptions[0]?.key || ''), options: state.titleOptions.map((item: any) => ({ value: String(item.key || item.label || item.value || ''), label: String(item.label || item.key || '') })), onChange: (value: string) => { state.titleMode = value; const found = state.titleOptions.find((item: any) => String(item.key || '') === value); if (found?.value) { state.rename = String(found.value); state.name = String(found.value) } render() } })
          const combo = document.createElement('div'); combo.className = 'noor-downloader-title-combo'; combo.append(renameInput, titleModeSelect)
          form.appendChild(makeField({ label: '下载任务名称', control: combo, hint: state.titleOptions.find((item: any) => String(item.key || '') === state.titleMode)?.hint || '优先使用智能命名' }))
        } else form.appendChild(makeField({ label: '下载任务名称', control: renameInput }))
      }
      if (state.options?.supports_savepath) form.appendChild(makeField({ label: '下载路径', control: makeInput({ value: state.savepath, placeholder: '/downloads/av', onInput: (value: string) => { state.savepath = value; state.selectedPath = value } }), hint: '优先使用下载器插件返回的历史路径或默认路径。' }))
      if (state.options?.supports_file_indices) {
        const fileOptions = Array.isArray(state.options?.file_indices_options) ? state.options.file_indices_options.filter(Boolean) : []
        const fileControl = fileOptions.length ? makeSelect({ value: state.fileIndices, options: fileOptions.map((item: any) => ({ value: String(item.value ?? ''), label: String(item.label ?? item.value ?? '') })), onChange: (value: string) => { state.fileIndices = value } }) : makeInput({ value: state.fileIndices, placeholder: 'auto / --1 / 0 / 1,3', onInput: (value: string) => { state.fileIndices = value } })
        form.appendChild(makeField({ label: '文件选择', control: fileControl, hint: fileOptions.find((item: any) => String(item.value ?? '') === String(state.fileIndices))?.hint || undefined }))
      }
      if (state.options?.supports_small_file_filter) form.appendChild(makeField({ label: '自动过滤小文件（MB）', control: makeInput({ value: state.minFileSizeMb, placeholder: String(state.options?.small_file_filter?.default_mb ?? '0'), onInput: (value: string) => { state.minFileSizeMb = value } }), hint: state.options?.small_file_filter?.keep_subtitles ? '自动过滤小于该阈值的非字幕文件，字幕始终保留。填 0 表示关闭。' : '自动过滤小于该阈值的文件。填 0 表示关闭。' }))
      body.appendChild(form)
      if (state.loading) body.appendChild(makeLoadingState({ text: '读取下载器配置中…' }))
      else if (state.options?.supports_resource_preview) body.appendChild(renderResourcePreview({ options: state.options, loading: state.previewLoading, error: state.previewError, data: state.previewData }))
      const footer = document.createElement('div'); footer.className = 'noor-plugin-modal__actions'
      const cancel = makeButton({ label: '关闭', onClick: () => !state.submitting && modal.close() })
      const submitBtn = makeSubmitButton({ idleLabel: submitIdleLabel, submittingLabel: '推送中', successLabel: submitSuccessLabel, errorLabel: submitErrorLabel, status: state.submitStatus, progress: state.submitProgress, className: 'noor-downloader-submit', disabled: state.loading || !(allowBatchUrls ? String(state.urlsText || '').trim() : String(state.url || '').trim()) || !state.downloaderId || state.submitStatus === 'success', onClick: async () => { try { const result = await submit(); options.onSuccess?.(result) } catch (e: any) { options.onError?.(e) } } })
      state.submitButton = submitBtn; footer.append(cancel, submitBtn)
      const existingFooter = modal.el.querySelector('.noor-plugin-modal__actions')
      if (existingFooter) existingFooter.remove()
      modal.el.querySelector('.noor-plugin-modal')?.appendChild(footer)
    }

    await loadOptions()
    render()
    return modal
  }

  return { open, openTask: open }
}
