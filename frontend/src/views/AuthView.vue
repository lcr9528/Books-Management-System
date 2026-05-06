<script setup>
import { computed, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { checkRegisterAvailability, obtainToken, register } from '../api/auth'
import { refreshUser } from '../auth'
import '../styles/auth.css'

const router = useRouter()
const route = useRoute()
const isRegister = computed(() => route.name === 'register')

const loginUsername = ref('')
const loginPassword = ref('')
const regUsername = ref('')
const regPassword = ref('')
const regEmail = ref('')

const loginErr = ref('')
const registerErr = ref('')
const regUsernameErr = ref('')
const regEmailErr = ref('')
const loginLoading = ref(false)
const registerLoading = ref(false)

let regUsernameDebounce = null
let regEmailDebounce = null
let registerErrDismissTimer = null

const REGISTER_ERR_AUTO_HIDE_MS = 3000

function clearRegisterErrTimer() {
  if (registerErrDismissTimer) {
    clearTimeout(registerErrDismissTimer)
    registerErrDismissTimer = null
  }
}

/** 顶栏注册错误提示，默认约 3 秒后自动消失 */
function showRegisterErr(message, ms = REGISTER_ERR_AUTO_HIDE_MS) {
  clearRegisterErrTimer()
  registerErr.value = message
  if (ms > 0) {
    registerErrDismissTimer = setTimeout(() => {
      registerErr.value = ''
      registerErrDismissTimer = null
    }, ms)
  }
}

function normalizeRegisterApiError(raw) {
  const s = typeof raw === 'string' ? raw : String(raw ?? '')
  if (s.includes('使用该名字')) return '该账号已被使用。'
  if (s.includes('使用该邮箱地址')) return '该邮箱已被使用。'
  return s || '注册失败，请重试。'
}

onUnmounted(() => {
  clearRegisterErrTimer()
})

async function checkUsernameField() {
  const u = regUsername.value.trim()
  if (!u) {
    regUsernameErr.value = ''
    return
  }
  try {
    const { data } = await checkRegisterAvailability({ username: u })
    if (regUsername.value.trim() !== u) return
    regUsernameErr.value = data.username_available ? '' : '该账号已被使用。'
  } catch {
    regUsernameErr.value = ''
  }
}

async function checkEmailField() {
  const em = regEmail.value.trim()
  if (!em) {
    regEmailErr.value = ''
    return
  }
  try {
    const { data } = await checkRegisterAvailability({ email: em })
    if (regEmail.value.trim() !== em) return
    regEmailErr.value = data.email_available ? '' : '该邮箱已被使用。'
  } catch {
    regEmailErr.value = ''
  }
}

function onRegUsernameInput() {
  regUsernameErr.value = ''
  clearTimeout(regUsernameDebounce)
  regUsernameDebounce = setTimeout(() => {
    void checkUsernameField()
  }, 450)
}

function onRegUsernameBlur() {
  clearTimeout(regUsernameDebounce)
  void checkUsernameField()
}

function onRegEmailInput() {
  regEmailErr.value = ''
  clearTimeout(regEmailDebounce)
  regEmailDebounce = setTimeout(() => {
    void checkEmailField()
  }, 450)
}

function onRegEmailBlur() {
  clearTimeout(regEmailDebounce)
  void checkEmailField()
}

function goLogin() {
  const q = { ...route.query }
  if (q.register !== undefined) delete q.register
  router.push({ name: 'login', query: q })
}
function goRegister() {
  router.push({ name: 'register', query: route.query })
}

watch(
  () => route.name,
  () => {
    loginErr.value = ''
    clearRegisterErrTimer()
    registerErr.value = ''
    regUsernameErr.value = ''
    regEmailErr.value = ''
  }
)

async function onLogin(e) {
  e.preventDefault()
  loginErr.value = ''
  loginLoading.value = true
  try {
    const { data } = await obtainToken(loginUsername.value, loginPassword.value)
    localStorage.setItem('access', data.access)
    localStorage.setItem('refresh', data.refresh)
    await refreshUser({ force: true })
    const next = route.query.next
    router.push(typeof next === 'string' && next ? next : '/')
  } catch (err) {
    loginErr.value = err?.response?.data?.detail || '登录失败，请检查用户名与密码。'
  } finally {
    loginLoading.value = false
  }
}

async function onRegister(e) {
  e.preventDefault()
  clearRegisterErrTimer()
  registerErr.value = ''
  await Promise.all([checkUsernameField(), checkEmailField()])
  if (regUsernameErr.value || regEmailErr.value) {
    showRegisterErr('请更换已被占用的账号或邮箱后再试。')
    return
  }
  registerLoading.value = true
  try {
    await register({
      username: regUsername.value.trim(),
      password: regPassword.value,
      email: regEmail.value.trim(),
    })
    router.push({ name: 'login', query: route.query })
  } catch (err) {
    const d = err?.response?.data
    if (typeof d?.detail === 'string') {
      showRegisterErr(normalizeRegisterApiError(d.detail))
    } else if (d && typeof d === 'object') {
      const first = Object.values(d)[0]
      const raw = Array.isArray(first) ? first[0] : String(first)
      showRegisterErr(normalizeRegisterApiError(raw))
    } else {
      showRegisterErr('注册失败，请重试。')
    }
  } finally {
    registerLoading.value = false
  }
}
</script>

<template>
  <div class="auth-page">
    <div class="auth-wrap">
      <div class="auth-card" :class="{ 'is-register': isRegister }">
        <div class="auth-column auth-column--login">
          <h1>登录</h1>
          <!-- <p class="auth-hint" style="text-align: center; margin-bottom: 18px">
            使用已注册的读者账号进入系统
          </p> -->
          <form @submit="onLogin">
            <p v-if="loginErr" class="auth-alert">{{ loginErr }}</p>
            <div class="auth-field">
              <input
                v-model="loginUsername"
                name="username"
                type="text"
                required
                autocomplete="username"
                placeholder="请输入账号"
                aria-label="用户名"
              />
            </div>
            <div class="auth-field">
              <input
                v-model="loginPassword"
                name="password"
                type="password"
                required
                autocomplete="current-password"
                placeholder="请输入密码"
                aria-label="密码"
              />
            </div>
            <router-link class="auth-forgot" :to="{ name: 'forgot-password', query: route.query }"
              >忘记密码？</router-link
            >
            <button type="submit" class="auth-btn-solid" :disabled="loginLoading">
              {{ loginLoading ? '登录中…' : '登录' }}
            </button>
          </form>
          <p class="auth-back">← <router-link to="/">返回首页</router-link></p>
        </div>

        <div class="auth-column auth-column--register">
          <h1>注册</h1>
          <!-- <p class="auth-hint" style="text-align: center; margin-bottom: 18px">
            新读者可自助注册，默认仅读者身份
          </p> -->
          <form @submit="onRegister">
            <p v-if="registerErr" class="auth-alert">{{ registerErr }}</p>
            <div class="auth-field" :class="{ 'auth-field--error': regUsernameErr }">
              <input
                v-model="regUsername"
                name="reg-username"
                type="text"
                required
                minlength="1"
                autocomplete="username"
                placeholder="请设置账号"
                aria-label="注册用户名"
                :aria-invalid="regUsernameErr ? 'true' : 'false'"
                @input="onRegUsernameInput"
                @blur="onRegUsernameBlur"
              />
              <p v-if="regUsernameErr" class="auth-field-msg">{{ regUsernameErr }}</p>
            </div>
            <div class="auth-field">
              <input
                v-model="regPassword"
                name="reg-password"
                type="password"
                required
                minlength="6"
                autocomplete="new-password"
                placeholder="请设置密码（至少 6 位）"
                aria-label="注册密码"
              />
            </div>
            <div class="auth-field" :class="{ 'auth-field--error': regEmailErr }">
              <input
                v-model="regEmail"
                name="email"
                type="email"
                required
                autocomplete="email"
                placeholder="邮箱（必填，用于登录与安全验证）"
                aria-label="邮箱"
                :aria-invalid="regEmailErr ? 'true' : 'false'"
                @input="onRegEmailInput"
                @blur="onRegEmailBlur"
              />
              <p v-if="regEmailErr" class="auth-field-msg">{{ regEmailErr }}</p>
            </div>
            <button type="submit" class="auth-btn-solid" :disabled="registerLoading">
              {{ registerLoading ? '注册中…' : '注册' }}
            </button>
          </form>
          <p class="auth-back">← <router-link to="/">返回首页</router-link></p>
        </div>

        <div class="auth-overlay" aria-hidden="true">
          <div class="auth-overlay__face auth-overlay__face--to-register">
            <h2>你好，朋友！</h2>
            <p>请注册您的个人信息以使用系统的全部功能</p>
            <button type="button" class="auth-btn-ghost" @click="goRegister">注册</button>
          </div>
          <div class="auth-overlay__face auth-overlay__face--to-login">
            <h2>欢迎回来</h2>
            <p>请登录以管理借阅与续借，访问图书与个人信息</p>
            <button type="button" class="auth-btn-ghost" @click="goLogin">登录</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
