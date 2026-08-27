import { reactive } from 'vue'

type ConfirmOptions = {
  title?: string
  message: string
  confirmText?: string
  cancelText?: string
  danger?: boolean
  size?: 'sm' | 'md' | 'lg' | 'xl'
  hideCancel?: boolean
  note?: string
  details?: Array<{
    label: string
    items: string[]
  }>
}

type ConfirmState = {
  open: boolean
  title: string
  message: string
  confirmText: string
  cancelText: string
  danger: boolean
  size: 'sm' | 'md' | 'lg' | 'xl'
  hideCancel: boolean
  note: string
  details: Array<{
    label: string
    items: string[]
  }>
  resolver: ((value: boolean) => void) | null
}

const state = reactive<ConfirmState>({
  open: false,
  title: '',
  message: '',
  confirmText: '',
  cancelText: '',
  danger: false,
  size: 'sm',
  hideCancel: false,
  note: '',
  details: [],
  resolver: null,
})

export function useConfirm() {
  function ask(options: ConfirmOptions) {
    if (state.open && state.resolver) {
      state.resolver(false)
    }

    state.open = true
    state.title = options.title || ''
    state.message = options.message
    state.confirmText = options.confirmText || ''
    state.cancelText = options.cancelText || ''
    state.danger = !!options.danger
    state.size = options.size || 'sm'
    state.hideCancel = !!options.hideCancel
    state.note = options.note || ''
    state.details = options.details || []

    return new Promise<boolean>((resolve) => {
      state.resolver = resolve
    })
  }

  function resolve(value: boolean) {
    if (state.resolver) {
      state.resolver(value)
    }
    state.open = false
    state.resolver = null
  }

  return {
    confirmState: state,
    confirm: ask,
    resolveConfirm: resolve,
  }
}
