<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { listBorrows, renewBorrow, returnBook } from '../api/books'
import { showToast } from '../composables/useToast'

const list = ref([])
const count = ref(0)
const hasNext = ref(false)
const err = ref('')
const loading = ref(false)
const page = ref(1)
const pageSize = ref(10)
const pageSizeOptions = [10, 20, 50]
const renewDueAt = ref('')
const renewDueAtInput = ref(null)
const actionLoading = ref(false)
const renewModalVisible = ref(false)
const returnModalVisible = ref(false)
const currentBorrow = ref(null)

function buildParams() {
  return {
    page: page.value,
    page_size: pageSize.value,
  }
}

async function load() {
  loading.value = true
  err.value = ''
  try {
    const { data } = await listBorrows(buildParams())
    if (data.results) {
      list.value = data.results
      count.value = data.count ?? 0
      hasNext.value = Boolean(data.next)
    } else {
      list.value = data || []
      count.value = Array.isArray(data) ? data.length : 0
      hasNext.value = false
    }
  } catch (e) {
    err.value = e?.response?.data?.detail || e?.message || '加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)

watch(pageSize, () => {
  page.value = 1
})
watch([page, pageSize], () => {
  load()
})

function updateRow(data) {
  const i = list.value.findIndex((x) => x.id === data.id)
  if (i >= 0) list.value[i] = { ...data }
}

function openRenewModal(r) {
  if (!r?.id || r.status === 'returned') return
  currentBorrow.value = { ...r }
  renewDueAt.value = ''
  renewModalVisible.value = true
}

function openReturnModal(r) {
  if (!r?.id || r.status === 'returned') return
  currentBorrow.value = { ...r }
  returnModalVisible.value = true
}

function closeRenewModal() {
  if (actionLoading.value) return
  renewModalVisible.value = false
}

function closeReturnModal() {
  if (actionLoading.value) return
  returnModalVisible.value = false
}

async function onReturnConfirm() {
  const r = currentBorrow.value
  if (!r?.id || r.status === 'returned') return
  actionLoading.value = true
  try {
    const { data } = await returnBook(r.id)
    updateRow(data)
    returnModalVisible.value = false
    showToast('归还成功')
  } catch (e) {
    err.value = e?.response?.data?.detail || e?.message || '归还失败'
  } finally {
    actionLoading.value = false
  }
}

async function onRenewConfirm() {
  const r = currentBorrow.value
  if (!r?.id || r.status === 'returned') return
  if (!renewDueAt.value) {
    err.value = '请先选择续借时间。'
    return
  }
  actionLoading.value = true
  try {
    const { data } = await renewBorrow(r.id, {
      due_at: new Date(renewDueAt.value).toISOString(),
    })
    updateRow(data)
    renewModalVisible.value = false
    showToast('续借成功')
  } catch (e) {
    err.value = e?.response?.data?.detail || e?.message || '续借失败'
  } finally {
    actionLoading.value = false
  }
}

function formatDateTime(dt) {
  if (!dt) return '—'
  const raw = String(dt).replace('T', ' ')
  const noTz = raw.replace(/(Z|[+-]\d{2}:?\d{2})$/, '')
  return noTz.split('.')[0]
}

function dueTimeText(r) {
  if (!r) return '—'
  return formatDateTime(r.due_at)
}

function returnedTimeText(r) {
  if (!r?.returned_at) return '—'
  return formatDateTime(r.returned_at)
}

function rowNo(index) {
  return (page.value - 1) * pageSize.value + index + 1
}

function toLocalDateTimeInput(dt) {
  const date = dt ? new Date(dt) : new Date()
  const d = new Date(date.getTime() - date.getTimezoneOffset() * 60000)
  return d.toISOString().slice(0, 16)
}

function renewMinTime(r) {
  if (!r?.due_at) return toLocalDateTimeInput()
  const now = new Date()
  const due = new Date(r.due_at)
  return toLocalDateTimeInput(due > now ? due : now)
}

function openDateTimePicker(inputEl) {
  if (!inputEl) return
  inputEl.focus()
  if (typeof inputEl.showPicker === 'function') {
    try {
      inputEl.showPicker()
    } catch {
      // 某些浏览器可能拦截；至少保持聚焦
    }
  }
}

function openRenewDueAtPicker() {
  openDateTimePicker(renewDueAtInput.value)
}

</script>

<template>
  <div class="container">
    <h1>我的借阅</h1>
    <p v-if="err" class="err">{{ err }}</p>
    <p v-else-if="loading">加载中…</p>
    <table v-else class="t">
      <thead>
        <tr>
          <th>序号</th>
          <th>图书名称</th>
          <th>借出时间</th>
          <th>借阅时间</th>
          <th>归还时间</th>
          <th>状态</th>
          <th>超期</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(r, idx) in list" :key="r.id">
          <td>{{ rowNo(idx) }}</td>
          <td>
            <router-link :to="{ name: 'book-detail', params: { id: r.book } }">{{
              r.book_title
            }}</router-link>
          </td>
          <td>{{ formatDateTime(r.borrowed_at) }}</td>
          <td>{{ dueTimeText(r) }}</td>
          <td>{{ returnedTimeText(r) }}</td>
          <td>{{ r.status === 'borrowed' ? '在借' : '已还' }}</td>
          <td>{{ r.is_overdue ? '是' : '否' }}</td>
          <td class="t__ops">
            <button v-if="r.status === 'borrowed'" @click="openRenewModal(r)">续借</button>
            <button v-if="r.status === 'borrowed'" @click="openReturnModal(r)">归还</button>
            <span v-else class="muted">—</span>
          </td>
        </tr>
      </tbody>
    </table>
    <p v-if="!err && !list.length">暂无记录</p>
    <p v-if="!err && !!list.length" class="bl__page">
      <label class="bl__size">
        每页
        <select v-model.number="pageSize" class="bl__size-select" aria-label="每页条数">
          <option v-for="s in pageSizeOptions" :key="s" :value="s">{{ s }} 条</option>
        </select>
      </label>
      第 {{ page }} 页
      <button type="button" :disabled="page <= 1" @click="page--">上一页</button>
      <button type="button" :disabled="!hasNext" @click="page++">下一页</button>
      <span v-if="count" class="bl__count">共 {{ count }} 条</span>
    </p>

    <Teleport to="body">
      <Transition name="mb-modal">
        <div v-if="renewModalVisible" class="mb-modal-mask" @click.self="closeRenewModal">
          <div class="mb-modal-panel" role="dialog" aria-modal="true" aria-label="续借表单">
            <h3 class="mb-modal-title">续借确认</h3>
            <div class="mb-grid">
              <div class="mb-row">
                <span class="mb-row__label">图书名称</span>
                <div class="mb-row__value">{{ currentBorrow?.book_title || '—' }}</div>
              </div>
              <div class="mb-row">
                <span class="mb-row__label">借出时间</span>
                <div class="mb-row__value">{{ formatDateTime(currentBorrow?.borrowed_at) }}</div>
              </div>
              <div class="mb-row">
                <span class="mb-row__label">借阅时间</span>
                <div class="mb-row__value">{{ dueTimeText(currentBorrow) }}</div>
              </div>
              <div class="mb-row">
                <span class="mb-row__label">归还时间</span>
                <div class="mb-row__value">{{ returnedTimeText(currentBorrow) }}</div>
              </div>
              <div class="mb-row">
                <span class="mb-row__label">续借时间</span>
                <div class="mb-row__value" @click="openRenewDueAtPicker">
                  <input
                    ref="renewDueAtInput"
                    v-model="renewDueAt"
                    type="datetime-local"
                    class="mb-select"
                    aria-label="续借时间"
                    :min="renewMinTime(currentBorrow)"
                  />
                </div>
              </div>
              <div class="mb-row">
                <span class="mb-row__label">状态</span>
                <div class="mb-row__value">{{ currentBorrow?.status === 'borrowed' ? '在借' : '已还' }}</div>
              </div>
              <div class="mb-row">
                <span class="mb-row__label">超期</span>
                <div class="mb-row__value">{{ currentBorrow?.is_overdue ? '是' : '否' }}</div>
              </div>
            </div>
            <div class="mb-actions">
              <button
                type="button"
                class="mb-btn mb-btn--ghost"
                :disabled="actionLoading"
                @click="closeRenewModal"
              >
                取消
              </button>
              <button
                type="button"
                class="mb-btn mb-btn--primary"
                :disabled="actionLoading"
                @click="onRenewConfirm"
              >
                {{ actionLoading ? '提交中…' : '确定续借' }}
              </button>
            </div>
          </div>
        </div>
      </Transition>

      <Transition name="mb-modal">
        <div v-if="returnModalVisible" class="mb-modal-mask" @click.self="closeReturnModal">
          <div class="mb-modal-panel" role="dialog" aria-modal="true" aria-label="归还表单">
            <h3 class="mb-modal-title">归还确认</h3>
            <div class="mb-grid">
              <div class="mb-row">
                <span class="mb-row__label">图书名称</span>
                <div class="mb-row__value">{{ currentBorrow?.book_title || '—' }}</div>
              </div>
              <div class="mb-row">
                <span class="mb-row__label">借出时间</span>
                <div class="mb-row__value">{{ formatDateTime(currentBorrow?.borrowed_at) }}</div>
              </div>
              <div class="mb-row">
                <span class="mb-row__label">借阅时间</span>
                <div class="mb-row__value">{{ dueTimeText(currentBorrow) }}</div>
              </div>
              <div class="mb-row">
                <span class="mb-row__label">归还时间</span>
                <div class="mb-row__value">{{ returnedTimeText(currentBorrow) }}</div>
              </div>
              <div class="mb-row">
                <span class="mb-row__label">状态</span>
                <div class="mb-row__value">{{ currentBorrow?.status === 'borrowed' ? '在借' : '已还' }}</div>
              </div>
              <div class="mb-row">
                <span class="mb-row__label">超期</span>
                <div class="mb-row__value">{{ currentBorrow?.is_overdue ? '是' : '否' }}</div>
              </div>
            </div>
            <div class="mb-actions">
              <button
                type="button"
                class="mb-btn mb-btn--ghost"
                :disabled="actionLoading"
                @click="closeReturnModal"
              >
                取消
              </button>
              <button
                type="button"
                class="mb-btn mb-btn--primary"
                :disabled="actionLoading"
                @click="onReturnConfirm"
              >
                {{ actionLoading ? '提交中…' : '确定归还' }}
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<style scoped>
.t {
  width: 100%;
  border-collapse: collapse;
  margin: 0 0 1rem;
  border: 1px solid #cbd5e1;
  box-shadow: 0 0 0 1px rgba(148, 163, 184, 0.25);
}
th,
td {
  border: 1px solid #d1d5db;
  padding: 0.45rem 0.55rem;
  text-align: center;
}
th {
  background: #f3eadb;
  color: #0f172a;
}
.err {
  color: #b91c1c;
  text-align: center;
}
.muted {
  color: #6b7280;
}
a {
  color: #2563eb;
}
.t__ops {
  white-space: nowrap;
}
.t__ops button + button {
  margin-left: 0.35rem;
}
.t__ops button {
  border: 1px solid #d8c4a7;
  background: #f3e7d6;
  color: #5f4939;
}
.t__ops button:hover:not(:disabled) {
  background: #ecdcc7;
}
h1 {
  text-align: center;
  margin-bottom: 1rem;
}
.container > p {
  text-align: center;
}
.bl__page {
  margin: 0.8rem 0 0;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 0.5rem;
}
.bl__size {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  color: #475569;
  font-size: 0.9rem;
}
.bl__size-select {
  padding: 0.24rem 0.45rem;
  border: 1px solid #d8c4a7;
  border-radius: 8px;
  color: #5f4939;
  background: #f3e7d6;
}
.bl__size-select:focus,
.bl__size-select:focus-visible {
  outline: none;
  border-color: #d8c4a7;
  box-shadow: none;
}
.bl__count {
  color: #6b7280;
  font-size: 0.9rem;
  margin-left: 0.25rem;
}
.container {
  margin-top: 1rem;
}
.bl__page button {
  border: 1px solid #d8c4a7;
  background: #f3e7d6;
  color: #5f4939;
}
.bl__page button:hover:not(:disabled) {
  background: #ecdcc7;
}
.bl__page button:disabled {
  background: #f7efe3;
  color: #a18a72;
  border-color: #e6d8c3;
}
.mb-modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: grid;
  place-items: center;
  padding: 16px;
  z-index: 1200;
}
.mb-modal-panel {
  width: min(560px, 100%);
  background: #fffaf2;
  border-radius: 14px;
  border: 1px solid #e6d8c1;
  box-shadow: 0 18px 40px -12px rgba(15, 23, 42, 0.45);
  padding: 18px 18px 16px;
}
.mb-modal-title {
  margin: 0 0 12px;
  text-align: center;
  font-size: 1.05rem;
  color: #020617;
}
.mb-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 10px 14px;
}
.mb-row {
  padding: 4px 2px;
  display: flex;
  align-items: center;
  gap: 10px;
}
.mb-row__label {
  flex: 0 0 84px;
  font-size: 0.82rem;
  color: #64748b;
  text-align: left;
}
.mb-row__value {
  flex: 1;
  min-height: 34px;
  border: 1px solid #e4d7c3;
  border-radius: 8px;
  background: transparent;
  color: #0f172a;
  font-size: 0.92rem;
  font-weight: 400;
  padding: 6px 10px;
  display: flex;
  align-items: center;
  text-align: left;
  word-break: break-word;
}
.mb-select {
  width: 100%;
  border: 1px solid #d7c8b2;
  border-radius: 8px;
  padding: 6px 8px;
  font-size: 0.9rem;
  background: transparent;
  color: #0f172a;
}
.mb-select:focus,
.mb-select:focus-visible {
  outline: none;
  border-color: #d7c8b2;
  box-shadow: none;
}
.mb-actions {
  margin-top: 14px;
  display: flex;
  justify-content: center;
  gap: 10px;
}
.mb-actions button {
  min-width: 96px;
}
.mb-btn {
  min-width: 96px;
  border-radius: 10px;
  font-weight: 600;
}
.mb-btn--ghost {
  border: 1px solid #d9cdb9;
  background: #f5ecdf;
  color: #5b4636;
}
.mb-btn--ghost:hover:not(:disabled) {
  background: #efe3d2;
}
.mb-btn--primary {
  border: 1px solid #b99262;
  background: linear-gradient(135deg, #d7b17b, #c29258);
  color: #fffdf8;
}
.mb-btn--primary:hover:not(:disabled) {
  background: linear-gradient(135deg, #dcb983, #c99a61);
}
.mb-modal-enter-active,
.mb-modal-leave-active {
  transition: opacity 0.2s ease;
}
.mb-modal-enter-from,
.mb-modal-leave-to {
  opacity: 0;
}
</style>
