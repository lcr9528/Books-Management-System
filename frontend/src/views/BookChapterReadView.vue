<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getBook, getBookChapter, listBookChapters } from '../api/books'

const READ_THEME_KEY = 'bookChapterReadTheme'

function storedReadTheme() {
  try {
    const v = localStorage.getItem(READ_THEME_KEY)
    if (v === 'night' || v === 'day') return v
  } catch (_) {
    /* ignore */
  }
  return 'day'
}

const route = useRoute()
const router = useRouter()

const readTheme = ref(storedReadTheme())

watch(readTheme, (v) => {
  try {
    localStorage.setItem(READ_THEME_KEY, v)
  } catch (_) {
    /* ignore */
  }
})

function toggleReadTheme() {
  readTheme.value = readTheme.value === 'night' ? 'day' : 'night'
}

const book = ref(null)
const chapters = ref([])
const chapter = ref(null)
const err = ref('')
const loading = ref(true)

const bookId = computed(() => Number(route.params.id))
const chapterIdParam = computed(() => Number(route.params.chapterId))

async function loadAll() {
  loading.value = true
  err.value = ''
  chapter.value = null
  book.value = null
  const bid = bookId.value
  const cid = chapterIdParam.value
  if (!Number.isFinite(bid) || !Number.isFinite(cid)) {
    err.value = '无效的图书或章节链接。'
    loading.value = false
    return
  }
  try {
    const [bookRes, listRes] = await Promise.all([
      getBook(bid),
      listBookChapters(bid),
    ])
    book.value = bookRes.data
    const raw = listRes.data
    const list = Array.isArray(raw) ? raw : raw?.results ?? []
    list.sort((a, b) => (a.order - b.order) || (a.id - b.id))
    chapters.value = list
    const chRes = await getBookChapter(bid, cid)
    chapter.value = chRes.data
  } catch (e) {
    err.value = e?.response?.data?.detail || e?.message || '加载失败'
  } finally {
    loading.value = false
  }
}

watch(
  () => [route.params.id, route.params.chapterId],
  () => loadAll(),
  { immediate: true }
)

const chapterIndex = computed(() =>
  chapters.value.findIndex((c) => c.id === chapterIdParam.value)
)

const prevChapter = computed(() => {
  const i = chapterIndex.value
  return i > 0 ? chapters.value[i - 1] : null
})

const nextChapter = computed(() => {
  const i = chapterIndex.value
  return i >= 0 && i < chapters.value.length - 1 ? chapters.value[i + 1] : null
})

function goBook() {
  router.push({ name: 'book-detail', params: { id: String(bookId.value) } })
}

/** 合并空白，便于对比正文首行与标题是否重复 */
function normSpace(s) {
  return String(s || '')
    .replace(/[\u3000\s]+/g, ' ')
    .trim()
}

/**
 * 去掉正文开头与页面标题重复的一行（爬虫常写入「书名 + 章节标题」或单独章节标题）。
 */
const displayContent = computed(() => {
  const raw = chapter.value?.content
  if (!raw) return ''
  const ct = normSpace(chapter.value?.title)
  const bt = normSpace(book.value?.title)
  const lines = raw.replace(/^\uFEFF/, '').split(/\r?\n/)
  let i = 0
  while (i < lines.length && !normSpace(lines[i])) i++
  if (i >= lines.length) return ''
  const first = normSpace(lines[i])
  const combined = bt && ct ? normSpace(`${bt} ${ct}`) : ''
  let dup =
    Boolean(ct && first === ct) ||
    Boolean(combined && first === combined)
  if (!dup && bt && ct && first.startsWith(bt)) {
    const rest = normSpace(first.slice(bt.length))
    dup = rest === ct
  }
  if (dup) {
    i++
    while (i < lines.length && !normSpace(lines[i])) i++
    return lines.slice(i).join('\n')
  }
  return raw
})
</script>

<template>
  <div class="ch-read" :class="{ 'ch-read--night': readTheme === 'night' }">
    <header class="ch-read__toolbar">
      <div class="ch-read__toolbar-start">
        <button type="button" class="ch-read__back" @click="goBook">← 返回图书详情</button>
      </div>
      <div class="ch-read__toolbar-center">
        <p v-if="book" class="ch-read__title-text ch-read__toolbar-book">{{ book.title }}</p>
      </div>
      <div class="ch-read__toolbar-end">
        <button
          type="button"
          class="ch-read__theme-btn"
          :aria-pressed="readTheme === 'night'"
          :aria-label="readTheme === 'night' ? '切换到日间模式' : '切换到夜间模式'"
          @click="toggleReadTheme"
        >
          {{ readTheme === 'night' ? '日间' : '夜间' }}
        </button>
      </div>
    </header>

    <div v-if="loading" class="ch-read__wrap container">加载中…</div>
    <div v-else-if="err" class="ch-read__wrap container err">{{ err }}</div>
    <article v-else-if="chapter" class="ch-read__wrap">
      <nav class="ch-read__nav ch-read__nav--top" aria-label="章节导航">
        <div class="ch-read__nav-cell ch-read__nav-cell--start">
          <router-link
            v-if="prevChapter"
            :to="{
              name: 'book-chapter-read',
              params: { id: String(bookId), chapterId: String(prevChapter.id) },
            }"
            class="ch-read__jump"
          >
            ← 上一章
          </router-link>
          <span v-else class="ch-read__jump ch-read__jump--off">← 上一章</span>
        </div>
        <div class="ch-read__nav-cell ch-read__nav-cell--center">
          <router-link
            :to="{ name: 'book-detail', params: { id: String(bookId) } }"
            class="ch-read__jump"
          >
            目录
          </router-link>
        </div>
        <div class="ch-read__nav-cell ch-read__nav-cell--end">
          <router-link
            v-if="nextChapter"
            :to="{
              name: 'book-chapter-read',
              params: { id: String(bookId), chapterId: String(nextChapter.id) },
            }"
            class="ch-read__jump"
          >
            下一章 →
          </router-link>
          <span v-else class="ch-read__jump ch-read__jump--off">下一章 →</span>
        </div>
      </nav>
      <h1 class="ch-read__title-text ch-read__chapter-heading">{{ chapter.title }}</h1>
      <pre class="ch-read__text">{{ displayContent }}</pre>
      <nav class="ch-read__nav ch-read__nav--bottom" aria-label="章节导航（文末）">
        <div class="ch-read__nav-cell ch-read__nav-cell--start">
          <router-link
            v-if="prevChapter"
            :to="{
              name: 'book-chapter-read',
              params: { id: String(bookId), chapterId: String(prevChapter.id) },
            }"
            class="ch-read__jump"
          >
            ← 上一章
          </router-link>
          <span v-else class="ch-read__jump ch-read__jump--off">← 上一章</span>
        </div>
        <div class="ch-read__nav-cell ch-read__nav-cell--center">
          <router-link
            :to="{ name: 'book-detail', params: { id: String(bookId) } }"
            class="ch-read__jump"
          >
            目录
          </router-link>
        </div>
        <div class="ch-read__nav-cell ch-read__nav-cell--end">
          <router-link
            v-if="nextChapter"
            :to="{
              name: 'book-chapter-read',
              params: { id: String(bookId), chapterId: String(nextChapter.id) },
            }"
            class="ch-read__jump"
          >
            下一章 →
          </router-link>
          <span v-else class="ch-read__jump ch-read__jump--off">下一章 →</span>
        </div>
      </nav>
    </article>
  </div>
</template>

<style scoped>
.ch-read {
  min-height: calc(100vh - 120px);
  padding: clamp(0.75rem, 2vw, 1.25rem) clamp(1rem, 3vw, 2rem) 2rem;
  padding-left: clamp(1.25rem, 5vw, 3rem);
  padding-right: clamp(1.25rem, 5vw, 3rem);
  box-sizing: border-box;
  transition: background-color 0.25s ease, color 0.2s ease;
}

/* —— 夜间模式 —— */
.ch-read--night {
  background: #18181b;
  color: #e4e4e7;
}

.ch-read--night .ch-read__toolbar {
  border-bottom-color: #3f3f46;
}

.ch-read--night .ch-read__title-text {
  color: #f4f4f5;
}

.ch-read--night .ch-read__nav--top,
.ch-read--night .ch-read__nav--bottom {
  border-color: #3f3f46;
}

.ch-read--night .ch-read__jump {
  color: #2dd4bf;
}

.ch-read--night .ch-read__jump--off {
  color: #52525b;
}

.ch-read--night .ch-read__text {
  color: #d4d4d8;
  background: rgba(39, 39, 42, 0.65);
  padding: 1rem 1.1rem;
  border-radius: 12px;
  border: 1px solid #3f3f46;
}

.ch-read--night .err {
  color: #fca5a5;
}

.ch-read--night .ch-read__wrap.container {
  color: #a1a1aa;
}
.ch-read__toolbar {
  display: grid;
  grid-template-columns: 1fr minmax(0, auto) 1fr;
  align-items: center;
  gap: 0.5rem 0.75rem;
  margin-bottom: 1rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid #e8dfd0;
}
.ch-read__toolbar-start {
  justify-self: start;
  min-width: 0;
}
.ch-read__toolbar-center {
  justify-self: center;
  text-align: center;
  min-width: 0;
  max-width: 100%;
}
.ch-read__toolbar-end {
  justify-self: end;
  display: flex;
  align-items: center;
  min-width: 0;
}

.ch-read__theme-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.38rem 0.65rem;
  font-size: 0.82rem;
  font-weight: 700;
  color: #0f766e;
  background: #f0fdfa;
  border: 1px solid rgba(13, 148, 136, 0.35);
  border-radius: 999px;
  cursor: pointer;
  transition:
    background 0.2s ease,
    border-color 0.2s ease,
    color 0.2s ease,
    box-shadow 0.2s ease;
}

.ch-read__theme-btn:hover {
  background: #ccfbf1;
  border-color: rgba(13, 148, 136, 0.55);
}

.ch-read__theme-btn:focus-visible {
  outline: 2px solid #0d9488;
  outline-offset: 2px;
}

.ch-read--night .ch-read__theme-btn {
  color: #e4e4e7;
  background: #27272a;
  border-color: #52525b;
}

.ch-read--night .ch-read__theme-btn:hover {
  background: #3f3f46;
  border-color: #71717a;
}
.ch-read__back {
  border: 1px solid transparent;
  background: transparent;
  color: #0d9488;
  font-weight: 700;
  font-size: 0.92rem;
  cursor: pointer;
  padding: 0.42rem 0.85rem;
  border-radius: 999px;
  transition:
    background 0.2s ease,
    border-color 0.2s ease,
    box-shadow 0.2s ease,
    color 0.2s ease,
    transform 0.15s ease;
}
.ch-read__back:hover {
  background: #f0fdfa;
  border-color: rgba(13, 148, 136, 0.38);
  box-shadow: 0 4px 14px -6px rgba(13, 148, 136, 0.35);
  text-decoration: none;
}
.ch-read__back:active {
  transform: scale(0.98);
}
.ch-read__back:focus {
  outline: none;
}
.ch-read__back:focus-visible {
  outline: 2px solid #0d9488;
  outline-offset: 2px;
}

.ch-read--night .ch-read__back {
  color: #5eead4;
  border-color: transparent;
}
.ch-read--night .ch-read__back:hover {
  background: rgba(45, 212, 191, 0.14);
  border-color: rgba(45, 212, 191, 0.42);
  box-shadow:
    0 4px 16px -8px rgba(0, 0, 0, 0.45),
    inset 0 1px 0 rgba(255, 255, 255, 0.06);
}
.ch-read--night .ch-read__back:focus-visible {
  outline-color: #5eead4;
}
/* 书名（顶栏）与章节标题共用字号与字重 */
.ch-read__title-text {
  font-size: clamp(1.05rem, 2.8vw, 1.25rem);
  font-weight: 800;
  color: #0f172a;
  line-height: 1.35;
}
.ch-read__toolbar-book {
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: min(36rem, 72vw);
}
.ch-read__chapter-heading {
  margin: 0 0 1rem;
  padding-top: 0;
}
.ch-read__wrap {
  max-width: min(50rem, 94vw);
  margin: 0 auto;
}
.ch-read__wrap.container {
  max-width: none;
}
.ch-read__text {
  margin: 0;
  font-family: ui-serif, 'Noto Serif SC', 'Source Han Serif SC', serif;
  font-size: 0.95rem;
  line-height: 1.85;
  color: #1e293b;
  white-space: pre-wrap;
  word-break: break-word;
}
.ch-read__nav {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  gap: 0.5rem;
}
.ch-read__nav--top {
  margin-bottom: 1rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px dashed #d4ccc1;
}
.ch-read__nav--bottom {
  margin-top: 2rem;
  padding-top: 1rem;
  border-top: 1px dashed #d4ccc1;
}
.ch-read__nav-cell--start {
  justify-self: start;
}
.ch-read__nav-cell--center {
  justify-self: center;
}
.ch-read__nav-cell--end {
  justify-self: end;
}
.ch-read__jump {
  color: #0d9488;
  font-weight: 600;
  font-size: 0.9rem;
  text-decoration: none;
}
.ch-read__jump:hover:not(.ch-read__jump--off) {
  text-decoration: underline;
}
.ch-read__jump--off {
  color: #94a3b8;
  cursor: default;
  pointer-events: none;
}
.err {
  color: #b91c1c;
}
</style>
