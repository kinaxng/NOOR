import api from '../api'

type SubscriptionDialogOptions = {
  code: string
  title?: string
  cover_url?: string
  fanart_url?: string
  image?: string
  sourcePlugin?: string
  sourceLabel?: string
  sourceRoute?: string
  sourceContext?: string
  defaultMode?: 'loose' | 'strict'
  requireCracked?: boolean
  requireSubtitle?: boolean
  onSuccess?: (result: any) => void
  onError?: (error: any) => void
}

let styleInjected = false

function injectStyle() {
  if (styleInjected || typeof document === 'undefined') return
  styleInjected = true
  const style = document.createElement('style')
  style.id = 'noor-subscription-dialog-style'
  style.textContent = `
.noor-subscription-mask{position:fixed;inset:0;z-index:var(--z-modal,1000);display:flex;align-items:center;justify-content:center;padding:1rem;background:rgba(0,0,0,.62);backdrop-filter:blur(10px)}
.noor-subscription-modal{width:min(560px,100%);max-height:min(760px,92vh);display:flex;flex-direction:column;overflow:hidden;border-radius:var(--radius-xl);background:rgb(26,31,55);border:1px solid rgba(255,255,255,.08);box-shadow:var(--shadow-xl,0 24px 64px rgba(0,0,0,.45))}
.noor-subscription-head,.noor-subscription-actions{display:flex;align-items:center;justify-content:space-between;gap:.75rem;padding:1rem;border-bottom:1px solid rgba(255,255,255,.06)}.noor-subscription-actions{justify-content:flex-end;border-top:1px solid rgba(255,255,255,.06);border-bottom:0}.noor-subscription-title{color:#fff;font-weight:800}.noor-subscription-close{width:30px;height:30px;border-radius:50%;border:1px solid rgba(255,255,255,.08);background:rgba(255,255,255,.04);color:rgba(255,255,255,.7);font-size:18px}.noor-subscription-body{padding:1rem;display:grid;gap:.8rem;overflow:auto}.noor-subscription-hint{padding:.75rem .85rem;border:1px solid rgba(0,117,255,.18);border-radius:.75rem;background:rgba(0,117,255,.08);color:var(--color-text-secondary,#cbd5e1);font-size:.78rem;line-height:1.55}.noor-subscription-field{display:grid;gap:.35rem;color:var(--color-text-muted,#94a3b8);font-size:.72rem;font-weight:750}.noor-subscription-field input,.noor-subscription-field select{height:36px;border:1px solid rgba(255,255,255,.1);border-radius:.55rem;background:rgba(255,255,255,.045);color:#fff;padding:0 .65rem}.noor-subscription-field select option{background:#111936;color:#fff}.noor-subscription-checks{display:flex;align-items:center;gap:1rem}.noor-subscription-checks label{display:flex;align-items:center;gap:.35rem;color:var(--color-text-secondary,#cbd5e1);font-size:.78rem}.noor-subscription-btn{min-height:32px;padding:0 .85rem;border-radius:var(--radius-button,.65rem);border:1px solid rgba(255,255,255,.08);background:rgba(255,255,255,.04);color:var(--color-text-secondary,#cbd5e1);font-weight:750}.noor-subscription-btn--primary{border-color:rgba(0,117,255,.34);background:rgba(0,117,255,.16);color:#fff}.noor-subscription-btn:disabled{opacity:.6;cursor:default}.noor-subscription-notice{padding:.65rem .8rem;border-radius:.65rem;background:rgba(239,68,68,.12);color:#fecaca;font-size:.76rem;font-weight:700}`
  document.head.appendChild(style)
}

function escapeHtml(value: any) {
  return String(value ?? '').replace(/[&<>'"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[c]!))
}

export async function openSubscriptionDialog(options: SubscriptionDialogOptions) {
  injectStyle()
  const code = String(options.code || '').trim()
  if (!code) throw new Error('缺少作品番号')
  const mask = document.createElement('div')
  mask.className = 'noor-subscription-mask'
  const modal = document.createElement('div')
  modal.className = 'noor-subscription-modal'
  mask.appendChild(modal)
  modal.innerHTML = `
    <div class="noor-subscription-head">
      <div class="noor-subscription-title">订阅 / 洗版</div>
      <button type="button" class="noor-subscription-close" aria-label="关闭">×</button>
    </div>
    <div class="noor-subscription-body">
      <div class="noor-subscription-hint">由订阅中心统一管理。媒体库未入库创建订阅；已入库创建洗版。条件为默认订阅条件，可在订阅中心继续调整。</div>
      <div data-role="error"></div>
      <label class="noor-subscription-field"><span>番号</span><input data-field="code" readonly value="${escapeHtml(code)}"></label>
      <label class="noor-subscription-field"><span>模式</span><select data-field="mode"><option value="loose">宽松订阅</option><option value="strict">严格订阅</option></select></label>
      <div class="noor-subscription-checks">
        <label><input data-field="require_cracked" type="checkbox"> 破解</label>
        <label><input data-field="require_subtitle" type="checkbox"> 中字</label>
      </div>
    </div>
    <div class="noor-subscription-actions">
      <button type="button" class="noor-subscription-btn" data-action="cancel">取消</button>
      <button type="button" class="noor-subscription-btn noor-subscription-btn--primary" data-action="save">保存</button>
    </div>
  `
  document.body.appendChild(mask)
  const close = () => mask.remove()
  mask.onclick = event => { if (event.target === mask) close() }
  modal.querySelector<HTMLButtonElement>('.noor-subscription-close')!.onclick = close
  modal.querySelector<HTMLButtonElement>('[data-action="cancel"]')!.onclick = close
  const mode = modal.querySelector<HTMLSelectElement>('[data-field="mode"]')!
  const cracked = modal.querySelector<HTMLInputElement>('[data-field="require_cracked"]')!
  const subtitle = modal.querySelector<HTMLInputElement>('[data-field="require_subtitle"]')!
  mode.value = options.defaultMode || 'loose'
  cracked.checked = !!options.requireCracked
  subtitle.checked = !!options.requireSubtitle
  const errorHost = modal.querySelector<HTMLElement>('[data-role="error"]')!
  const saveBtn = modal.querySelector<HTMLButtonElement>('[data-action="save"]')!
  saveBtn.onclick = async () => {
    errorHost.innerHTML = ''
    saveBtn.disabled = true
    const oldText = saveBtn.textContent
    saveBtn.textContent = '保存中…'
    try {
      const response = await api.post('/plugins/subscription-core/actions/create', {
        payload: {
          code,
          title: options.title || code,
          cover_url: options.cover_url || options.image || '',
          fanart_url: options.fanart_url || options.cover_url || options.image || '',
          source_plugin: options.sourcePlugin || '',
          source_label: options.sourceLabel || '',
          source_route: options.sourceRoute || window.location.pathname + window.location.search,
          source_context: options.sourceContext || '',
          type: 'auto',
          mode: mode.value || 'loose',
          require_cracked: cracked.checked,
          require_subtitle: subtitle.checked,
        },
      })
      options.onSuccess?.(response.data)
      saveBtn.textContent = response.data?.created ? '已创建' : '已存在'
      window.setTimeout(close, 500)
    } catch (error: any) {
      options.onError?.(error)
      errorHost.innerHTML = `<div class="noor-subscription-notice">${escapeHtml(error?.response?.data?.detail || error?.message || '保存失败')}</div>`
      saveBtn.textContent = oldText
      saveBtn.disabled = false
    }
  }
  return { close }
}
