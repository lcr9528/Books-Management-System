<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getBook, borrowBook, listBookChapters } from '../api/books'
import { useUser } from '../auth'

const route = useRoute()
const router = useRouter()
const { isLoggedIn, user } = useUser()
const id = computed(() => Number(route.params.id))
const book = ref(null)
const err = ref('')
const msg = ref('')
const borrowModalVisible = ref(false)
const borrowDueAt = ref('')
const borrowLoading = ref(false)
const borrowDueAtInput = ref(null)

const chapters = ref([])
const chaptersErr = ref('')
/** 目录每行列数（随窗口变化，与 tocRows 分块一致） */
const tocCols = ref(3)

function updateTocCols() {
  if (typeof window === 'undefined') return
  const w = window.innerWidth
  if (w < 520) tocCols.value = 1
  else if (w < 880) tocCols.value = 2
  else tocCols.value = 3
}

const tocRows = computed(() => {
  const n = tocCols.value
  const chs = chapters.value
  const rows = []
  for (let i = 0; i < chs.length; i += n) {
    rows.push(chs.slice(i, i + n))
  }
  return rows
})

onMounted(async () => {
  updateTocCols()
  window.addEventListener('resize', updateTocCols)
  try {
    const { data } = await getBook(id.value)
    book.value = data
    try {
      const cr = await listBookChapters(id.value)
      chapters.value = Array.isArray(cr.data) ? cr.data : cr.data?.results ?? []
    } catch (ce) {
      chaptersErr.value = ce?.response?.data?.detail || ce?.message || '章节列表加载失败'
    }
  } catch (e) {
    err.value = e?.response?.data?.detail || e?.message || '加载失败'
  }
})

function openChapter(ch) {
  router.push({
    name: 'book-chapter-read',
    params: { id: String(id.value), chapterId: String(ch.id) },
  })
}

function openBorrowModal() {
  if (book.value?.available_copies < 1) return
  borrowDueAt.value = ''
  borrowModalVisible.value = true
}

function closeBorrowModal() {
  if (borrowLoading.value) return
  borrowModalVisible.value = false
}

function formatDateTime(dt) {
  if (!dt) return '—'
  const raw = String(dt).replace('T', ' ')
  const noTz = raw.replace(/(Z|[+-]\d{2}:?\d{2})$/, '')
  return noTz.split('.')[0]
}

async function confirmBorrow() {
  err.value = ''
  msg.value = ''
  if (!isLoggedIn.value) {
    err.value = '请先登录后再借阅。'
    return
  }
  if (!borrowDueAt.value) {
    err.value = '请选择借阅时间。'
    return
  }
  borrowLoading.value = true
  try {
    const { data } = await borrowBook(id.value, {
      due_at: new Date(borrowDueAt.value).toISOString(),
    })
    msg.value = `借阅成功，归还时间：${formatDateTime(data.due_at)}`
    if (book.value) book.value.available_copies = book.value.available_copies - 1
    borrowModalVisible.value = false
  } catch (e) {
    const d = e?.response?.data
    err.value =
      d?.book?.[0] ||
      d?.detail ||
      d?.non_field_errors?.[0] ||
      (typeof d === 'string' ? d : e?.message) ||
      '借阅失败'
  } finally {
    borrowLoading.value = false
  }
}

onBeforeUnmount(() => {
  borrowModalVisible.value = false
  window.removeEventListener('resize', updateTocCols)
})

function toLocalDateTimeInput(dt) {
  const date = dt ? new Date(dt) : new Date()
  const d = new Date(date.getTime() - date.getTimezoneOffset() * 60000)
  return d.toISOString().slice(0, 16)
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

function openBorrowDueAtPicker() {
  openDateTimePicker(borrowDueAtInput.value)
}
</script>

<template>
  <div v-if="book" class="bd">
    <div class="bd__hero">
      <div class="bd__cover-col">
        <div class="bd__cover">
          <img
            v-if="book.cover"
            :src="book.cover"
            :alt="book.title"
            width="320"
            height="448"
          />
          <div v-else class="bd__ph" aria-hidden="true">无封面</div>
        </div>
      </div>
      <div class="bd__hero-text">
        <div class="bd__info-head">
          <h1 class="bd__h">{{ book.title }}</h1>
          <p class="bd__meta">作者：{{ book.author }} ｜ ISBN：{{ book.isbn }}</p>
          <p class="bd__meta">
            分类：{{ book.category_name }} ｜ 出版社：{{ book.publisher || '—' }}
          </p>
          <p class="bd__stat">
            在架/总册：<span class="bd__stat-num">{{ book.available_copies }} / {{ book.total_copies }}</span>
          </p>
          <p v-if="msg" class="ok">{{ msg }}</p>
          <p v-if="err" class="err">{{ err }}</p>
          <p v-if="!isLoggedIn" class="bd__login-hint">
            请 <router-link to="/login">登录</router-link> 后借阅。
          </p>
        </div>
        <section class="bd__intro" aria-labelledby="bd-intro-h">
          <h2 id="bd-intro-h" class="bd__intro-h">简介</h2>
          <div class="bd__intro-body">{{ book.description || '（暂无）' }}</div>
        </section>
      </div>
    </div>

    <div class="bd__tail">
      <div class="bd__info-actions">
        <div v-if="isLoggedIn" class="bd__act">
          <button type="button" :disabled="book.available_copies < 1" @click="openBorrowModal">
            借阅
          </button>
          <span v-if="book.available_copies < 1" class="muted">（无在架册）</span>
        </div>
      </div>
      <div class="bd__info-foot">
        <p class="bd__nav">
          <router-link to="/books">返回列表</router-link>
          <span class="bd__nav-sep"> · </span>
          <router-link to="/">首页</router-link>
        </p>
      </div>
    </div>

    <section class="bd__toc" aria-labelledby="bd-toc-h">
      <h2 id="bd-toc-h" class="bd__toc-h">目录</h2>
      <p v-if="chaptersErr" class="err bd__toc-msg">{{ chaptersErr }}</p>
      <p v-else-if="chapters.length === 0" class="bd__toc-empty muted">
        暂无章节
      </p>
      <nav
        v-else
        class="bd__toc-rows"
        aria-label="章节目录"
        :style="{ '--bd-toc-cols': tocCols }"
      >
        <div
          v-for="(row, ri) in tocRows"
          :key="ri"
          class="bd__toc-row"
        >
          <button
            v-for="ch in row"
            :key="ch.id"
            type="button"
            class="bd__toc-btn"
            :aria-label="`第 ${ch.order} 章：${ch.title}`"
            @click="openChapter(ch)"
          >
            {{ ch.title }}
          </button>
        </div>
      </nav>
    </section>

    <Teleport to="body">
      <Transition name="bd-modal">
        <div v-if="borrowModalVisible" class="bd-modal-mask" @click.self="closeBorrowModal">
          <div class="bd-modal-panel" role="dialog" aria-modal="true" aria-label="借阅确认">
            <h3 class="bd-modal-title">借阅确认</h3>
            <div class="bd-modal-row">
              <span>图书名称</span>
              <div class="bd-modal-value">{{ book?.title || '—' }}</div>
            </div>
            <div class="bd-modal-row">
              <span>借阅时间</span>
              <div class="bd-modal-value" @click="openBorrowDueAtPicker">
                <input
                  ref="borrowDueAtInput"
                  v-model="borrowDueAt"
                  type="datetime-local"
                  class="bd-select"
                  aria-label="借阅时间"
                  :min="toLocalDateTimeInput()"
                />
              </div>
            </div>
            <div class="bd-modal-actions">
              <button type="button" class="bd-btn bd-btn--ghost" :disabled="borrowLoading" @click="closeBorrowModal">
                取消
              </button>
              <button type="button" class="bd-btn bd-btn--primary" :disabled="borrowLoading" @click="confirmBorrow">
                {{ borrowLoading ? '提交中…' : '确定借阅' }}
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
  <p v-else-if="!err" class="container">加载中…</p>
  <p v-else class="container err">{{ err }}</p>
</template>

<style scoped>
.bd {
  --teal: #0d9488;
  --bd-cover-col: min(380px, 44vw);
  --bd-hero-gap: 1.35rem;
  width: 100%;
  max-width: none;
  margin: 0;
  padding: clamp(1rem, 2.4vw, 1.65rem) clamp(1rem, 3vw, 2rem) 1.5rem;
  padding-left: clamp(1.65rem, 5.5vw, 3.5rem);
  padding-top: clamp(1.35rem, 3.2vw, 2.1rem);
}
.bd__hero {
  display: grid;
  grid-template-columns: 1fr;
  gap: 1rem;
  margin-bottom: 0.85rem;
}
@media (min-width: 700px) {
  .bd__hero {
    grid-template-columns: var(--bd-cover-col) minmax(0, 1fr);
    gap: var(--bd-hero-gap);
    /* 行高由封面列决定时，右侧列拉满同高，简介区再 flex 撑满贴齐封面底 */
    align-items: stretch;
  }
}
.bd__cover-col {
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  align-items: stretch;
  min-width: 0;
  min-height: 0;
}
.bd__cover {
  width: 100%;
  max-width: var(--bd-cover-col);
  margin: 0;
  border-radius: 12px;
  overflow: hidden;
  background: #0f766e;
  box-shadow: 0 8px 24px -6px rgba(15, 23, 42, 0.12);
  flex-shrink: 0;
  aspect-ratio: 3 / 4.2;
  display: block;
  position: relative;
}
.bd__cover img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: center;
}
.bd__hero-text {
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
  min-width: 0;
  min-height: 0;
}
@media (min-width: 700px) {
  .bd__hero-text {
    height: 100%;
    /* 与封面同高（cover 宽 × 4.2/3），避免简介过长时撑高整行 */
    max-height: calc(var(--bd-cover-col) * 4.2 / 3);
    overflow: hidden;
  }
}
.bd__nav-sep {
  color: #64748b;
}
.bd__ph {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  min-height: 0;
  color: #e2e8f0;
  font-size: 0.9rem;
  background: linear-gradient(160deg, #0d9488 0%, #0f766e 45%, #134e4a 100%);
}
.bd__h {
  font-size: clamp(1.25rem, 3.5vw, 1.6rem);
  font-weight: 800;
  line-height: 1.2;
  letter-spacing: -0.02em;
  margin: 0 0 0.5rem;
  color: #1a1a2e;
}
.bd__meta {
  color: #475569;
  font-size: 0.92rem;
  margin: 0 0 0.4rem;
}
.bd__stat {
  font-size: 0.95rem;
  color: #1e293b;
  margin: 0.5rem 0 0.75rem;
}
.bd__stat-num {
  color: var(--teal);
  font-weight: 800;
}
.bd__info-head {
  flex-shrink: 0;
}
.bd__intro {
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 0.65rem 0.75rem;
  background: #fffefb;
  border: 1px solid #e8dfd0;
  border-radius: 12px;
  box-shadow: 0 4px 18px -8px rgba(15, 23, 42, 0.08);
  max-height: min(42vh, 360px);
  overflow: hidden;
}
@media (min-width: 700px) {
  .bd__intro {
    max-height: none;
    /* 占满标题下方的剩余高度，底边与左侧封面底对齐 */
    flex: 1 1 0;
  }
}
.bd__tail {
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
  margin-bottom: 1rem;
}
@media (min-width: 700px) {
  .bd__tail {
    margin-left: calc(var(--bd-cover-col) + var(--bd-hero-gap));
  }
}
.bd__intro-h {
  font-size: 0.95rem;
  font-weight: 800;
  margin: 0 0 0.45rem;
  color: #1a1a2e;
}
.bd__intro-body {
  margin: 0;
  font-size: 0.9rem;
  line-height: 1.65;
  color: #334155;
  white-space: pre-wrap;
  word-break: break-word;
  min-height: 0;
  flex: 1 1 auto;
  overflow-y: auto;
}
.bd__info-actions {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  flex-shrink: 0;
}
.bd__info-foot {
  flex-shrink: 0;
}
.bd__login-hint {
  margin: 0.35rem 0 0;
  font-size: 0.92rem;
}
.ok {
  color: #166534;
  margin: 0.35rem 0;
}
.err {
  color: #b91c1c;
  margin: 0.35rem 0;
}
.muted {
  color: #6b7280;
  margin-left: 0.4rem;
  font-size: 0.9rem;
}
.bd__act {
  margin: 0;
}
a {
  color: var(--teal);
  font-weight: 600;
}
.bd__toc {
  margin-top: 1.25rem;
  padding: 0.85rem 1rem 1rem 1.55rem;
  background: #fffefb;
  border: 1px solid #e8dfd0;
  border-radius: 14px;
  box-shadow: 0 4px 18px -8px rgba(15, 23, 42, 0.08);
}
.bd__toc-h {
  font-size: 1rem;
  font-weight: 800;
  margin: 0 0 0.65rem;
  color: #1a1a2e;
}
.bd__toc-msg {
  margin: 0;
}
.bd__toc-empty {
  margin: 0;
  font-size: 0.92rem;
}
.bd__toc-rows {
  display: flex;
  flex-direction: column;
  gap: 0;
  margin: 0;
  padding: 0;
}
.bd__toc-row {
  display: grid;
  grid-template-columns: repeat(var(--bd-toc-cols, 3), minmax(0, 1fr));
  column-gap: 1.35rem;
  row-gap: 0.35rem;
  padding: 0.55rem 0 0.65rem;
  border-bottom: 1px dashed #d4ccc1;
  align-items: start;
}
.bd__toc-row:last-child {
  border-bottom: none;
  padding-bottom: 0.2rem;
}
.bd__toc-btn {
  display: block;
  width: 100%;
  box-sizing: border-box;
  text-align: left;
  margin: 0;
  padding: 0.28rem 0;
  border: none;
  border-radius: 0;
  background: transparent;
  cursor: pointer;
  font-size: 0.88rem;
  line-height: 1.5;
  color: #334155;
  word-break: break-word;
  transition: color 0.15s ease;
}
.bd__toc-btn:hover {
  color: #ea580c;
  background: transparent;
}
.bd__toc-btn:focus-visible {
  outline: 2px solid rgba(13, 148, 136, 0.45);
  outline-offset: 2px;
}
.bd__nav {
  font-size: 0.9rem;
  margin: 0;
}
.bd-modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: grid;
  place-items: center;
  padding: 16px;
  z-index: 1200;
}
.bd-modal-panel {
  width: min(520px, 100%);
  background: #fffaf2;
  border: 1px solid #e6d8c1;
  border-radius: 14px;
  padding: 16px;
  box-shadow: 0 18px 40px -12px rgba(15, 23, 42, 0.45);
}
.bd-modal-title {
  margin: 0 0 12px;
  text-align: center;
  color: #020617;
}
.bd-modal-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}
.bd-modal-row > span {
  width: 76px;
  color: #64748b;
  font-size: 0.86rem;
}
.bd-modal-value {
  flex: 1;
  min-height: 36px;
  border: 1px solid #e4d7c3;
  border-radius: 8px;
  background: transparent;
  padding: 6px 10px;
  display: flex;
  align-items: center;
}
.bd-select {
  width: 100%;
  border: 1px solid #d7c8b2;
  border-radius: 8px;
  padding: 6px 8px;
  background: transparent;
}
.bd-select:focus,
.bd-select:focus-visible {
  outline: none;
  border-color: #d7c8b2;
  box-shadow: none;
}
.bd-modal-actions {
  margin-top: 12px;
  display: flex;
  justify-content: center;
  gap: 10px;
}
.bd-btn {
  min-width: 96px;
  border-radius: 10px;
  font-weight: 600;
}
.bd-btn--ghost {
  border: 1px solid #d9cdb9;
  background: #f5ecdf;
  color: #5b4636;
}
.bd-btn--ghost:hover:not(:disabled) {
  background: #efe3d2;
}
.bd-btn--primary {
  border: 1px solid #b99262;
  background: linear-gradient(135deg, #d7b17b, #c29258);
  color: #fffdf8;
}
.bd-btn--primary:hover:not(:disabled) {
  background: linear-gradient(135deg, #dcb983, #c99a61);
}
.bd-modal-enter-active,
.bd-modal-leave-active {
  transition: opacity 0.2s ease;
}
.bd-modal-enter-from,
.bd-modal-leave-to {
  opacity: 0;
}
</style>
