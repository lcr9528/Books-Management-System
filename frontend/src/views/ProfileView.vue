<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { updateMe } from '../api/auth'
import { refreshUser, user } from '../auth'

const DEFAULT_AVATAR = '/toux.png'
const router = useRouter()

const form = ref({
  username: '',
  email: '',
  first_name: '',
  last_name: '',
  student_id: '',
})
const fileInput = ref(null)
const pendingFile = ref(null)
const previewUrl = ref(null)
const err = ref('')
const loading = ref(false)
const toastVisible = ref(false)
let toastTimer = null

function showSuccessToast() {
  toastVisible.value = true
  if (toastTimer != null) {
    window.clearTimeout(toastTimer)
    toastTimer = null
  }
  toastTimer = window.setTimeout(() => {
    toastVisible.value = false
    toastTimer = null
  }, 3000)
}

const avatarPreview = computed(() => {
  if (previewUrl.value) return previewUrl.value
  return user.value?.avatar || DEFAULT_AVATAR
})

function fillFromUser(u) {
  if (!u) return
  form.value = {
    username: u.username || '',
    email: u.email || '',
    first_name: u.first_name || '',
    last_name: u.last_name || '',
    student_id: u.student_id || '',
  }
}

onMounted(async () => {
  try {
    await refreshUser()
    fillFromUser(user.value)
  } catch {
    err.value = '加载失败'
  }
})

watch(user, (u) => fillFromUser(u), { immediate: true })

function onPickAvatar() {
  fileInput.value?.click()
}

function onFileChange(e) {
  const f = e.target.files?.[0]
  if (!f || !f.type.startsWith('image/')) {
    err.value = '请选择图片文件。'
    return
  }
  if (f.size > 2 * 1024 * 1024) {
    err.value = '图片请小于 2MB。'
    return
  }
  err.value = ''
  pendingFile.value = f
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
  previewUrl.value = URL.createObjectURL(f)
}

async function onSubmit(e) {
  e.preventDefault()
  err.value = ''
  loading.value = true
  try {
    const fd = new FormData()
    fd.append('username', form.value.username.trim())
    fd.append('email', form.value.email.trim())
    fd.append('first_name', form.value.first_name.trim())
    fd.append('last_name', form.value.last_name.trim())
    fd.append('student_id', form.value.student_id.trim())
    if (pendingFile.value) {
      fd.append('avatar', pendingFile.value)
    }
    const { data } = await updateMe(fd)
    pendingFile.value = null
    if (previewUrl.value) {
      URL.revokeObjectURL(previewUrl.value)
      previewUrl.value = null
    }
    if (fileInput.value) fileInput.value.value = ''
    await refreshUser()
    fillFromUser(data)
    showSuccessToast()
  } catch (e2) {
    const d = e2?.response?.data
    if (d && typeof d === 'object') {
      const parts = []
      for (const v of Object.values(d)) {
        if (Array.isArray(v)) parts.push(v[0])
        else if (typeof v === 'string') parts.push(v)
      }
      err.value = parts.join(' ') || '保存失败'
    } else {
      err.value = '保存失败，请检查网络或稍后重试。'
    }
  } finally {
    loading.value = false
  }
}

onBeforeUnmount(() => {
  if (toastTimer != null) {
    window.clearTimeout(toastTimer)
    toastTimer = null
  }
})
</script>

<template>
  <div class="container profile-wrap">
    <h1>个人资料</h1>
    <!-- <p class="profile-lead">修改头像与基本信息。未上传头像时使用默认图。</p> -->
    <p v-if="err" class="profile-err">{{ err }}</p>

    <form class="profile-form" @submit="onSubmit">
      <div class="profile-avatar-row">
        <button type="button" class="profile-avatar-wrap" @click="onPickAvatar">
          <img class="profile-avatar-img" :src="avatarPreview" alt="头像" />
          <span class="profile-avatar-hint">点击更换</span>
        </button>
        <input
          ref="fileInput"
          type="file"
          class="profile-file"
          accept="image/jpeg,image/png,image/webp,image/gif"
          @change="onFileChange"
        />
      </div>

      <label class="profile-field">
        <span>用户名</span>
        <input v-model="form.username" type="text" required autocomplete="username" />
      </label>
      <label class="profile-field">
        <span>邮箱</span>
        <input v-model="form.email" type="email" required autocomplete="email" />
      </label>
      <label class="profile-field">
        <span>姓</span>
        <input v-model="form.last_name" type="text" autocomplete="family-name" />
      </label>
      <label class="profile-field">
        <span>名</span>
        <input v-model="form.first_name" type="text" autocomplete="given-name" />
      </label>
      <label class="profile-field">
        <span>学号/工号</span>
        <input v-model="form.student_id" type="text" autocomplete="off" placeholder="选填" />
      </label>

      <div class="profile-actions">
        <button type="submit" class="profile-save" :disabled="loading">
          {{ loading ? '保存中…' : '保存' }}
        </button>
        <button type="button" class="profile-back" @click="router.push('/')">返回首页</button>
      </div>
    </form>

    <Teleport to="body">
      <Transition name="toast">
        <div v-if="toastVisible" class="profile-toast" role="status" aria-live="polite">
          保存成功
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<style scoped>
.profile-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  max-width: 520px;
  margin: 0 auto;
  text-align: center;
  width: 100%;
}
.profile-wrap > h1 {
  width: 100%;
}
.profile-lead {
  color: #64748b;
  font-size: 0.92rem;
  margin: 0 0 1rem;
  width: 100%;
}
.profile-err {
  color: #b91c1c;
  margin: 0 0 0.75rem;
  width: 100%;
}
.profile-form {
  margin-top: 0.5rem;
  width: 100%;
  max-width: 420px;
  text-align: left;
}
.profile-avatar-row {
  margin-bottom: 1.25rem;
  display: flex;
  justify-content: center;
}
.profile-file {
  position: absolute;
  width: 0;
  height: 0;
  opacity: 0;
  pointer-events: none;
}
.profile-avatar-wrap {
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  gap: 0.35rem;
  padding: 0;
  border: none;
  background: none;
  cursor: pointer;
  font: inherit;
}
.profile-avatar-img {
  width: 96px;
  height: 96px;
  border-radius: 50%;
  object-fit: cover;
  border: none;
  display: block;
}
.profile-avatar-hint {
  font-size: 0.82rem;
  color: #0d9488;
  font-weight: 600;
}
.profile-field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  margin-bottom: 0.85rem;
}
.profile-field span {
  font-size: 0.88rem;
  font-weight: 600;
  color: #334155;
  text-align: left;
  width: 100%;
}
.profile-field input {
  padding: 0.55rem 0.65rem;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  font-size: 0.95rem;
  width: 100%;
  text-align: left;
}
.profile-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.65rem;
  margin-top: 1rem;
  justify-content: center;
}
/* 覆盖全局 button:hover，避免悬停变成浅灰/接近白底盖住白字 */
.profile-save {
  padding: 0.55rem 1.25rem;
  border: none !important;
  border-radius: 10px;
  background: linear-gradient(135deg, #2dd4bf, #0d9488) !important;
  color: #fff !important;
  font-weight: 600;
  cursor: pointer;
}
.profile-save:hover:not(:disabled) {
  background: linear-gradient(135deg, #33d0bc, #0a8578) !important;
  color: #fff !important;
}
.profile-save:active:not(:disabled) {
  background: linear-gradient(135deg, #2dd4bf, #0d9488) !important;
}
.profile-save:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}
.profile-back {
  padding: 0.55rem 1rem;
  border-radius: 10px;
  border: 1px solid #cbd5e1 !important;
  background: #fff !important;
  color: #1f2937 !important;
  cursor: pointer;
}
.profile-back:hover:not(:disabled) {
  background: #f1f5f9 !important;
  color: #0f172a !important;
}

/* 保存成功：视口居中浮层，3 秒后关闭 */
.profile-toast {
  position: fixed;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  z-index: 9999;
  padding: 0.85rem 1.75rem;
  border-radius: 12px;
  background: linear-gradient(135deg, #0d9488, #0f766e);
  color: #fff;
  font-size: 0.95rem;
  font-weight: 600;
  box-shadow: 0 12px 32px -10px rgba(15, 23, 42, 0.4);
  pointer-events: none;
}
.toast-enter-active,
.toast-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}
.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translate(-50%, -50%) scale(0.94);
}
</style>
