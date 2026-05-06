<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { updateMe } from '../api/auth'
import { refreshUser, user } from '../auth'
import { showToast } from '../composables/useToast'

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
/** 点击头像：大图预览 */
const avatarPreviewOpen = ref(false)

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
    await refreshUser({ force: true })
    fillFromUser(user.value)
  } catch {
    err.value = '加载失败'
  }
})

watch(user, (u) => fillFromUser(u), { immediate: true })

watch(avatarPreviewOpen, (open) => {
  if (open) {
    window.addEventListener('keydown', onPreviewKeydown)
  } else {
    window.removeEventListener('keydown', onPreviewKeydown)
  }
})

function onPickAvatar() {
  fileInput.value?.click()
}

function openAvatarPreview() {
  avatarPreviewOpen.value = true
}

function closeAvatarPreview() {
  avatarPreviewOpen.value = false
}

function onPreviewKeydown(ev) {
  if (ev.key === 'Escape') closeAvatarPreview()
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
    await refreshUser({ force: true })
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
  window.removeEventListener('keydown', onPreviewKeydown)
})
</script>

<template>
  <div class="container profile-page">
    <h1 class="profile-page-title">个人资料</h1>
    <p v-if="err" class="profile-err">{{ err }}</p>

    <div class="profile-body">
    <form class="profile-form" @submit="onSubmit">
      <div class="profile-avatar-row">
        <div class="profile-avatar-stack">
          <button
            type="button"
            class="profile-avatar-wrap"
            title="点击预览大图"
            @click="openAvatarPreview"
          >
            <img class="profile-avatar-img" :src="avatarPreview" alt="头像" />
          </button>
          <button type="button" class="profile-change-btn" @click="onPickAvatar">
            更换
          </button>
          <input
            ref="fileInput"
            type="file"
            class="profile-file"
            accept="image/jpeg,image/png,image/webp,image/gif"
            @change="onFileChange"
          />
        </div>
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
    </div>

    <Teleport to="body">
      <Transition name="profile-preview">
        <div
          v-if="avatarPreviewOpen"
          class="profile-preview-mask"
          role="presentation"
          @click.self="closeAvatarPreview"
        >
          <div
            class="profile-preview-dialog"
            role="dialog"
            aria-modal="true"
            aria-label="头像预览，点击空白处关闭"
            @click.stop
          >
            <img class="profile-preview-img" :src="avatarPreview" alt="头像预览" />
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<style scoped>
.profile-page {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
}
.profile-page-title {
  width: 100%;
  text-align: center;
  margin: 0 0 1rem;
  font-size: clamp(1.35rem, 3vw, 1.55rem);
  font-weight: 800;
  color: #1a1a2e;
  letter-spacing: -0.02em;
}
.profile-body {
  width: 100%;
  max-width: 520px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  align-items: center;
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
  max-width: 520px;
  text-align: center;
}
.profile-form {
  margin-top: 0.5rem;
  width: 100%;
  max-width: 420px;
  margin-left: auto;
  margin-right: auto;
  text-align: left;
}
.profile-avatar-row {
  margin-bottom: 1.25rem;
  display: flex;
  justify-content: center;
}
.profile-avatar-stack {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.55rem;
}
.profile-file {
  position: absolute;
  width: 0;
  height: 0;
  opacity: 0;
  pointer-events: none;
}
.profile-avatar-wrap {
  display: block;
  padding: 0;
  border: none;
  border-radius: 50%;
  background: transparent !important;
  cursor: zoom-in;
  font: inherit;
  line-height: 0;
  box-shadow: 0 0 0 2px transparent;
  transition:
    box-shadow 0.2s ease,
    transform 0.2s ease;
}
.profile-avatar-wrap:hover {
  background: transparent !important;
  box-shadow: 0 0 0 3px rgba(13, 148, 136, 0.45);
  transform: scale(1.03);
}
.profile-avatar-wrap:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px rgba(13, 148, 136, 0.55), 0 0 0 6px rgba(13, 148, 136, 0.2);
}
.profile-avatar-wrap:active {
  transform: scale(1.01);
}
.profile-avatar-img {
  width: 96px;
  height: 96px;
  border-radius: 50%;
  object-fit: cover;
  border: none;
  display: block;
}
.profile-change-btn {
  padding: 0.42rem 1rem;
  border-radius: 10px;
  border: 1px solid rgba(13, 148, 136, 0.45) !important;
  background: rgba(13, 148, 136, 0.08) !important;
  color: #0f766e !important;
  font-size: 0.88rem;
  font-weight: 700;
  cursor: pointer;
  transition:
    border-color 0.15s ease,
    background 0.15s ease,
    color 0.15s ease;
}
.profile-change-btn:hover {
  background: rgba(13, 148, 136, 0.14) !important;
  border-color: rgba(13, 148, 136, 0.65) !important;
  color: #0d9488 !important;
}
.profile-change-btn:active {
  background: rgba(13, 148, 136, 0.2) !important;
}

/* 头像大图预览 */
.profile-preview-mask {
  position: fixed;
  inset: 0;
  z-index: 20000;
  display: grid;
  place-items: center;
  padding: 1.25rem;
  background: rgba(15, 23, 42, 0.72);
  backdrop-filter: blur(4px);
}
.profile-preview-dialog {
  position: relative;
  max-width: min(92vw, 520px);
  max-height: min(88vh, 720px);
  margin: auto;
}
.profile-preview-img {
  display: block;
  max-width: min(92vw, 520px);
  max-height: min(88vh, 720px);
  width: auto;
  height: auto;
  object-fit: contain;
  border-radius: 12px;
  box-shadow: 0 24px 48px -12px rgba(0, 0, 0, 0.45);
}
.profile-preview-enter-active,
.profile-preview-leave-active {
  transition: opacity 0.22s ease;
}
.profile-preview-enter-active .profile-preview-dialog,
.profile-preview-leave-active .profile-preview-dialog {
  transition: transform 0.22s ease, opacity 0.22s ease;
}
.profile-preview-enter-from,
.profile-preview-leave-to {
  opacity: 0;
}
.profile-preview-enter-from .profile-preview-dialog,
.profile-preview-leave-to .profile-preview-dialog {
  opacity: 0;
  transform: scale(0.94);
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
</style>
