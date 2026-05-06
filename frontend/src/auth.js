import { ref, computed } from 'vue'
import { fetchMe } from './api/auth'

const user = ref(null)
const loading = ref(false)

export { user, loading }

export function useUser() {
  return { user, loading, isLoggedIn: computed(() => !!user.value) }
}

export function setUser(u) {
  user.value = u
}

/** 路由切换时避免每次都对 /me 发请求，减轻「详情 → 首页」等跳转卡顿 */
let lastMeFetchAt = 0
const REFRESH_USER_MIN_INTERVAL_MS = 25_000

/**
 * @param {{ force?: boolean }} [opts] force=true 时忽略节流（登录成功、资料保存后等）
 */
export async function refreshUser(opts = {}) {
  const force = opts.force === true
  const at = localStorage.getItem('access')
  if (!at) {
    user.value = null
    return null
  }
  const now = Date.now()
  if (
    !force &&
    user.value &&
    now - lastMeFetchAt < REFRESH_USER_MIN_INTERVAL_MS
  ) {
    return user.value
  }
  loading.value = true
  try {
    const { data } = await fetchMe()
    user.value = data
    lastMeFetchAt = Date.now()
    return data
  } catch {
    user.value = null
    lastMeFetchAt = 0
    return null
  } finally {
    loading.value = false
  }
}

export function clearSession() {
  localStorage.removeItem('access')
  localStorage.removeItem('refresh')
  user.value = null
  lastMeFetchAt = 0
}

export function isLibrarian() {
  return user.value?.is_librarian === true
}
