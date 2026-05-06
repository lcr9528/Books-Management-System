import { ref } from 'vue'

/** 默认展示时长（毫秒） */
export const TOAST_DEFAULT_DURATION = 3000

const visible = ref(false)
const message = ref('')
const variant = ref('success')

let hideTimer = null

/**
 * @param {string} text
 * @param {{ variant?: 'success' | 'error' | 'info'; duration?: number }} [options]
 */
export function showToast(text, options = {}) {
  const msg = text == null ? '' : String(text)
  const v = options.variant ?? 'success'
  const ms =
    options.duration === undefined
      ? TOAST_DEFAULT_DURATION
      : Number(options.duration)

  message.value = msg
  variant.value = ['success', 'error', 'info'].includes(v) ? v : 'success'

  if (hideTimer != null) {
    window.clearTimeout(hideTimer)
    hideTimer = null
  }
  visible.value = true

  if (ms > 0) {
    hideTimer = window.setTimeout(() => {
      visible.value = false
      hideTimer = null
    }, ms)
  }
}

export function dismissToast() {
  if (hideTimer != null) {
    window.clearTimeout(hideTimer)
    hideTimer = null
  }
  visible.value = false
}

/** 供 AppToast 根组件绑定（单例状态） */
export function useToastState() {
  return { visible, message, variant, dismissToast }
}

export const toast = {
  show: showToast,
  success: (text, opts) => showToast(text, { ...opts, variant: 'success' }),
  error: (text, opts) => showToast(text, { ...opts, variant: 'error' }),
  info: (text, opts) => showToast(text, { ...opts, variant: 'info' }),
  dismiss: dismissToast,
}
