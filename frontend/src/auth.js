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

export async function refreshUser() {
  const at = localStorage.getItem('access')
  if (!at) {
    user.value = null
    return null
  }
  loading.value = true
  try {
    const { data } = await fetchMe()
    user.value = data
    return data
  } catch {
    user.value = null
    return null
  } finally {
    loading.value = false
  }
}

export function clearSession() {
  localStorage.removeItem('access')
  localStorage.removeItem('refresh')
  user.value = null
}

export function isLibrarian() {
  return user.value?.is_librarian === true
}
