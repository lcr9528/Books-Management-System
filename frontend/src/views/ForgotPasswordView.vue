<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { requestPasswordReset, confirmPasswordReset } from '../api/auth'
import '../styles/auth.css'

const route = useRoute()
const router = useRouter()
const email = ref('')
const code = ref('')
const newPassword = ref('')
const newPassword2 = ref('')
const err = ref('')
const success = ref('')
const sendLoading = ref(false)
const submitLoading = ref(false)
const sendCooldown = ref(0)
let sendTimer = null

async function onSend() {
  err.value = ''
  success.value = ''
  const e = email.value.trim()
  if (!e) {
    err.value = '请填写注册时使用的邮箱。'
    return
  }
  sendLoading.value = true
  try {
    const { data } = await requestPasswordReset(e)
    success.value = data?.detail || '如该邮箱已注册，将很快收到邮件。'
    if (sendCooldown.value <= 0) {
      sendCooldown.value = 60
      sendTimer = window.setInterval(() => {
        sendCooldown.value -= 1
        if (sendCooldown.value <= 0 && sendTimer) {
          window.clearInterval(sendTimer)
          sendTimer = null
        }
      }, 1000)
    }
  } catch (e2) {
    const d = e2?.response?.data
    err.value =
      (typeof d?.detail === 'string' && d.detail) || '发送失败，请检查邮箱或稍后再试。'
  } finally {
    sendLoading.value = false
  }
}

async function onSubmit(e) {
  e.preventDefault()
  err.value = ''
  success.value = ''
  if (newPassword.value !== newPassword2.value) {
    err.value = '两次输入的新密码不一致。'
    return
  }
  const e0 = email.value.trim()
  if (!e0 || !code.value.trim() || newPassword.value.length < 6) {
    err.value = '请完整填写邮箱、6 位验证码与新密码（至少 6 位）。'
    return
  }
  submitLoading.value = true
  try {
    const { data } = await confirmPasswordReset({
      email: e0,
      code: code.value.replace(/\D/g, '').slice(0, 6),
      new_password: newPassword.value,
    })
    success.value = data?.detail || '成功'
    setTimeout(() => {
      router.push({ name: 'login', query: { ...router.currentRoute.value.query } })
    }, 1200)
  } catch (e2) {
    const d = e2?.response?.data
    if (d && typeof d === 'object') {
      const first = Object.values(d).flat().find((x) => x)
      err.value = Array.isArray(first) ? first[0] : first || e2?.message
    } else {
      err.value = '重设失败，请检查验证码后重试。'
    }
  } finally {
    submitLoading.value = false
  }
}
</script>

<template>
  <div class="auth-page">
    <div class="auth-wrap">
      <div class="forgot-card">
        <h1>忘记密码</h1>
        <p class="forgot-hint">向注册邮箱获取 6 位验证码，验证后即可设置新密码。</p>
        <p v-if="err" class="auth-alert">{{ err }}</p>
        <p v-if="success" class="forgot-success">{{ success }}</p>
        <form @submit="onSubmit">
          <div class="auth-field forgot-email-row">
            <input
              v-model="email"
              name="email"
              type="email"
              required
              autocomplete="email"
              placeholder="注册时使用的邮箱"
              aria-label="邮箱"
            />
            <button
              type="button"
              class="forgot-btn-send"
              :disabled="sendLoading || sendCooldown > 0"
              @click="onSend"
            >
              {{ sendLoading ? '发送中…' : sendCooldown > 0 ? `${sendCooldown}s` : '发送验证码' }}
            </button>
          </div>
          <div class="auth-field">
            <input
              v-model="code"
              name="code"
              type="text"
              inputmode="numeric"
              maxlength="6"
              required
              autocomplete="one-time-code"
              placeholder="6 位数字验证码"
              aria-label="验证码"
            />
          </div>
          <div class="auth-field">
            <input
              v-model="newPassword"
              name="new_password"
              type="password"
              required
              minlength="6"
              autocomplete="new-password"
              placeholder="新密码（至少 6 位）"
              aria-label="新密码"
            />
          </div>
          <div class="auth-field">
            <input
              v-model="newPassword2"
              name="new_password2"
              type="password"
              required
              minlength="6"
              autocomplete="new-password"
              placeholder="再次输入新密码"
              aria-label="确认新密码"
            />
          </div>
          <button type="submit" class="auth-btn-solid" :disabled="submitLoading">
            {{ submitLoading ? '提交中…' : '确定' }}
          </button>
        </form>
        <p class="auth-back">
          ←
          <router-link :to="{ name: 'login', query: route.query }">返回登录</router-link>
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.forgot-card {
  width: min(440px, 100%);
  margin: 0 auto;
  padding: 2.5rem 2rem 2rem;
  background: #fff;
  border-radius: 20px;
  box-shadow: 0 25px 50px -12px rgba(15, 23, 42, 0.18);
  border: 1px solid rgba(15, 23, 42, 0.04);
}
.forgot-card h1 {
  margin: 0 0 0.5rem;
  text-align: center;
  font-size: 1.5rem;
  color: #1a1a2e;
}
.forgot-hint {
  margin: 0 0 1.25rem;
  font-size: 0.85rem;
  line-height: 1.5;
  color: #64748b;
  text-align: center;
}
.forgot-success {
  margin: 0 0 0.75rem;
  padding: 10px 12px;
  font-size: 0.88rem;
  line-height: 1.45;
  color: #0f766e;
  background: #ecfdf5;
  border-radius: 10px;
  border: 1px solid #a7f3d0;
  text-align: left;
}
.forgot-email-row {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  align-items: stretch;
}
.forgot-email-row input {
  flex: 1 1 8rem;
  min-width: 0;
  padding: 12px 14px;
  border: none;
  border-radius: 10px;
  font-size: 0.95rem;
  background: #e8f4f8;
  color: #1a1a2e;
  box-sizing: border-box;
  outline: none;
}
.forgot-email-row input:focus {
  box-shadow: 0 0 0 3px rgba(20, 184, 166, 0.25);
}
.forgot-btn-send {
  flex: 0 0 auto;
  white-space: nowrap;
  font-size: 0.9rem;
  font-weight: 600;
  border-radius: 10px;
  padding: 12px 16px;
  cursor: pointer;
  font-family: inherit;
}
</style>
