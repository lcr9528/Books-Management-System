<script setup>
import { computed, onMounted, ref } from 'vue'
import {
  listCategories,
  createCategory,
  createBook,
  getSiteSettings,
  patchSiteSettings,
} from '../api/books'
import { showToast } from '../composables/useToast'

/** 左侧菜单：book 默认首屏 */
const activePanel = ref('book')

const panelTitle = computed(() => {
  if (activePanel.value === 'book') return '新增图书'
  if (activePanel.value === 'category') return '新增图书分类'
  return '阅读正文开关'
})

const requireBorrowToReadChapters = ref(false)
const settingsLoading = ref(false)

const catName = ref('')
const book = ref({
  title: '',
  isbn: '',
  author: '',
  category: null,
  publisher: '',
  description: '',
  total_copies: 1,
})
const categories = ref([])

onMounted(async () => {
  try {
    const [{ data: cats }, { data: site }] = await Promise.all([
      listCategories(),
      getSiteSettings(),
    ])
    const rows = cats.results || cats
    categories.value = rows
    if (rows.length) book.value.category = rows[0].id
    requireBorrowToReadChapters.value = !!site.require_borrow_to_read_chapters
  } catch (e) {
    showToast(e?.message || '加载失败', { variant: 'error' })
  }
})

async function toggleRequireBorrowToRead(ev) {
  ev.preventDefault()
  settingsLoading.value = true
  const next = !requireBorrowToReadChapters.value
  try {
    const { data } = await patchSiteSettings({
      require_borrow_to_read_chapters: next,
    })
    requireBorrowToReadChapters.value = !!data.require_borrow_to_read_chapters
    showToast(
      next
        ? '已开启：阅读章节正文须先借阅本书（在借中）。'
        : '已关闭：访客与未在借用户可依权限阅读章节正文。'
    )
  } catch (e) {
    const d = e?.response?.data
    let errText = e?.message || '保存失败'
    if (d?.detail) errText = String(d.detail)
    else if (d && typeof d === 'object') {
      const k = Object.keys(d)[0]
      const v = d[k]
      errText = Array.isArray(v) ? v[0] : String(v)
    }
    showToast(errText, { variant: 'error' })
  } finally {
    settingsLoading.value = false
  }
}

async function addCategory() {
  if (!catName.value.trim()) return
  try {
    const { data } = await createCategory(catName.value.trim())
    categories.value.push(data)
    book.value.category = data.id
    showToast(`已创建分类：${data.name}`)
    catName.value = ''
  } catch (e) {
    showToast(e?.response?.data?.name?.[0] || e?.message || '创建失败', {
      variant: 'error',
    })
  }
}

async function addBook() {
  if (!book.value.category) {
    showToast('请选择或先新增分类。', { variant: 'error' })
    return
  }
  try {
    const { data } = await createBook({
      title: book.value.title,
      isbn: book.value.isbn,
      author: book.value.author,
      category: book.value.category,
      publisher: book.value.publisher,
      description: book.value.description,
      total_copies: Number(book.value.total_copies) || 1,
    })
    showToast(`已添加图书《${data.title}》，ID ${data.id}`)
  } catch (e) {
    const d = e?.response?.data
    let errText = e?.message || '失败'
    if (d && typeof d === 'object') {
      const k = Object.keys(d)[0]
      const v = d[k]
      errText = Array.isArray(v) ? v[0] : String(v)
    }
    showToast(errText, { variant: 'error' })
  }
}
</script>

<template>
  <div class="lib">
    <header class="lib__head">
      <h1 class="lib__title">管理后台</h1>
    </header>

    <div class="lib__layout">
      <nav class="lib__sidebar" aria-label="管理功能导航">
        <p class="lib__sidebar-label">目录</p>
        <button
          type="button"
          class="lib__nav-item"
          :class="{ 'lib__nav-item--active': activePanel === 'book' }"
          :aria-current="activePanel === 'book' ? 'page' : undefined"
          @click="activePanel = 'book'"
        >
          新增图书
        </button>
        <button
          type="button"
          class="lib__nav-item"
          :class="{ 'lib__nav-item--active': activePanel === 'category' }"
          :aria-current="activePanel === 'category' ? 'page' : undefined"
          @click="activePanel = 'category'"
        >
          新增图书分类
        </button>
        <button
          type="button"
          class="lib__nav-item"
          :class="{ 'lib__nav-item--active': activePanel === 'settings' }"
          :aria-current="activePanel === 'settings' ? 'page' : undefined"
          @click="activePanel = 'settings'"
        >
          阅读正文开关
        </button>
      </nav>

      <div class="lib__main">
        <section
          v-show="activePanel === 'book'"
          class="lib__card lib__card--panel"
          :aria-hidden="activePanel !== 'book'"
          aria-labelledby="lib-book-heading"
        >
          <h2 id="lib-book-heading" class="lib__card-title">{{ panelTitle }}</h2>
          <div class="lib__form">
            <label class="lib__field">
              <span class="lib__label">书名</span>
              <input v-model="book.title" type="text" class="lib__input" required placeholder="必填" />
            </label>
            <label class="lib__field">
              <span class="lib__label">ISBN</span>
              <input v-model="book.isbn" type="text" class="lib__input" required placeholder="必填" />
            </label>
            <label class="lib__field">
              <span class="lib__label">作者</span>
              <input v-model="book.author" type="text" class="lib__input" required placeholder="必填" />
            </label>
            <label class="lib__field">
              <span class="lib__label">分类</span>
              <select v-model="book.category" class="lib__input lib__select">
                <option v-for="c in categories" :key="c.id" :value="c.id">{{ c.name }}</option>
              </select>
            </label>
            <label class="lib__field">
              <span class="lib__label">出版社</span>
              <input v-model="book.publisher" type="text" class="lib__input" placeholder="选填" />
            </label>
            <label class="lib__field">
              <span class="lib__label">总册数</span>
              <input
                v-model.number="book.total_copies"
                type="number"
                min="1"
                class="lib__input"
              />
            </label>
            <label class="lib__field lib__field--full">
              <span class="lib__label">简介</span>
              <textarea
                v-model="book.description"
                class="lib__textarea"
                rows="4"
                placeholder="图书内容简介（选填）"
              />
            </label>
          </div>
          <div class="lib__actions">
            <button type="button" class="lib__btn lib__btn--primary lib__btn--lg" @click="addBook">
              创建图书
            </button>
          </div>
        </section>

        <section
          v-show="activePanel === 'category'"
          class="lib__card lib__card--panel"
          :aria-hidden="activePanel !== 'category'"
          aria-labelledby="lib-cat-heading"
        >
          <h2 id="lib-cat-heading" class="lib__card-title">{{ panelTitle }}</h2>
          <div class="lib__cat-row">
            <input
              v-model="catName"
              type="text"
              class="lib__input lib__input--grow"
              placeholder="输入分类名称，如：军事历史"
              maxlength="100"
              @keydown.enter.prevent="addCategory"
            />
            <button type="button" class="lib__btn lib__btn--primary" @click="addCategory">
              添加分类
            </button>
          </div>
        </section>

        <section
          v-show="activePanel === 'settings'"
          class="lib__card lib__card--panel"
          :aria-hidden="activePanel !== 'settings'"
          aria-labelledby="lib-site-heading"
        >
          <h2 id="lib-site-heading" class="lib__card-title">{{ panelTitle }}</h2>
          <label class="lib__toggle">
            <input
              type="checkbox"
              :checked="requireBorrowToReadChapters"
              :disabled="settingsLoading"
              @click.prevent="toggleRequireBorrowToRead"
            />
            <span class="lib__toggle-text">
              阅读章节正文须先借阅本书（在借中）
              <span class="lib__toggle-hint"
                >开启后，未登录或未有本书在借记录的用户无法阅读章节正文。</span
              >
            </span>
          </label>
        </section>
      </div>
    </div>

    <footer class="lib__foot">
      <router-link class="lib__link" to="/books">图书列表</router-link>
      <span class="lib__dot" aria-hidden="true">·</span>
      <router-link class="lib__link" to="/">首页</router-link>
    </footer>
  </div>
</template>

<style scoped>
.lib {
  --teal: #0d9488;
  --teal-dark: #0f766e;
  --surface: #ffffff;
  --border: #e2e8f0;
  width: 100%;
  max-width: none;
  margin: 0;
  padding: 0.5rem clamp(1rem, 3vw, 2rem) 2.5rem;
  box-sizing: border-box;
}

.lib__layout {
  display: grid;
  grid-template-columns: 220px minmax(0, 1fr);
  gap: 1.25rem;
  align-items: start;
}

.lib__sidebar {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  padding: 1rem 0.85rem;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 16px;
  box-shadow:
    0 4px 6px -1px rgba(15, 23, 42, 0.05),
    0 10px 28px -12px rgba(15, 23, 42, 0.08);
}

.lib__sidebar-label {
  margin: 0 0 0.5rem;
  padding: 0 0.35rem;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #94a3b8;
}

.lib__nav-item {
  display: block;
  width: 100%;
  margin: 0;
  padding: 0.62rem 0.75rem;
  text-align: left;
  font-size: 0.92rem;
  font-weight: 600;
  color: #475569;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 10px;
  cursor: pointer;
  transition:
    background 0.15s ease,
    color 0.15s ease,
    border-color 0.15s ease;
}

.lib__nav-item:hover {
  background: #f8fafc;
  color: #0f172a;
}

.lib__nav-item--active {
  color: var(--teal-dark);
  background: linear-gradient(135deg, rgba(13, 148, 136, 0.12), rgba(13, 148, 136, 0.06));
  border-color: rgba(13, 148, 136, 0.35);
  box-shadow: inset 3px 0 0 var(--teal);
}

.lib__main {
  min-width: 0;
}

.lib__card--panel {
  margin: 0;
}

.lib__head {
  margin-bottom: 1.25rem;
}

.lib__title {
  margin: 0 0 0.35rem;
  font-size: clamp(1.35rem, 3vw, 1.55rem);
  font-weight: 800;
  letter-spacing: -0.02em;
  color: #1a1a2e;
}

.lib__lead {
  margin: 0;
  font-size: 0.92rem;
  color: #64748b;
  line-height: 1.5;
}

.lib__card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: clamp(1rem, 2.5vw, 1.35rem);
  box-shadow:
    0 4px 6px -1px rgba(15, 23, 42, 0.05),
    0 10px 28px -12px rgba(15, 23, 42, 0.08);
}

.lib__card-title {
  margin: 0 0 1rem;
  padding-bottom: 0.65rem;
  border-bottom: 1px solid #f1f5f9;
  font-size: 1rem;
  font-weight: 800;
  color: #334155;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.lib__card-title::before {
  content: '';
  width: 4px;
  height: 1.05rem;
  border-radius: 3px;
  background: linear-gradient(180deg, var(--teal), var(--teal-dark));
  flex-shrink: 0;
}

.lib__toggle {
  display: flex;
  align-items: flex-start;
  gap: 0.65rem;
  cursor: pointer;
  font-size: 0.95rem;
  color: #334155;
  line-height: 1.45;
}

.lib__toggle input {
  margin-top: 0.2rem;
  width: 1.05rem;
  height: 1.05rem;
  accent-color: var(--teal);
  cursor: pointer;
  flex-shrink: 0;
}

.lib__toggle input:disabled {
  cursor: not-allowed;
  opacity: 0.65;
}

.lib__toggle-text {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-weight: 600;
}

.lib__toggle-hint {
  font-weight: 400;
  font-size: 0.85rem;
  color: #64748b;
}

.lib__cat-row {
  display: flex;
  flex-wrap: wrap;
  align-items: stretch;
  gap: 0.65rem;
}

.lib__input--grow {
  flex: 1 1 12rem;
  min-width: 0;
}

.lib__form {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem 1.25rem;
}

@media (max-width: 640px) {
  .lib__form {
    grid-template-columns: 1fr;
  }
}

.lib__field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  min-width: 0;
}

.lib__field--full {
  grid-column: 1 / -1;
}

.lib__label {
  font-size: 0.82rem;
  font-weight: 600;
  color: #475569;
}

.lib__input,
.lib__textarea,
.lib__select {
  width: 100%;
  margin: 0;
  padding: 0.55rem 0.7rem;
  font-size: 0.95rem;
  color: #0f172a;
  background: #fafafa;
  border: 1px solid var(--border);
  border-radius: 10px;
  box-sizing: border-box;
  transition:
    border-color 0.15s ease,
    box-shadow 0.15s ease,
    background 0.15s ease;
}

.lib__input:hover,
.lib__textarea:hover,
.lib__select:hover {
  border-color: #cbd5e1;
  background: #fff;
}

.lib__input:focus,
.lib__textarea:focus,
.lib__select:focus {
  outline: none;
  border-color: rgba(13, 148, 136, 0.55);
  background: #fff;
  box-shadow: 0 0 0 3px rgba(13, 148, 136, 0.18);
}

.lib__textarea {
  resize: vertical;
  min-height: 6rem;
  line-height: 1.55;
  font-family: inherit;
}

.lib__select {
  cursor: pointer;
  appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%2364748b' d='M3 4.5L6 8l3-3.5'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 0.65rem center;
  padding-right: 2rem;
}

.lib__actions {
  margin-top: 1.25rem;
  padding-top: 1rem;
  border-top: 1px dashed #e2e8f0;
}

.lib__btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.5rem 1rem;
  font-size: 0.9rem;
  font-weight: 700;
  border-radius: 10px;
  border: 1px solid transparent;
  cursor: pointer;
  transition:
    transform 0.15s ease,
    box-shadow 0.15s ease,
    filter 0.15s ease;
}

.lib__btn:active:not(:disabled) {
  transform: translateY(1px);
}

.lib__btn--primary {
  background: linear-gradient(135deg, #14b8a6 0%, var(--teal) 45%, var(--teal-dark) 100%);
  color: #fff;
  box-shadow:
    0 4px 14px -4px rgba(13, 148, 136, 0.55),
    inset 0 1px 0 rgba(255, 255, 255, 0.2);
}

.lib__btn--primary:hover {
  filter: brightness(1.05);
  box-shadow:
    0 6px 18px -4px rgba(13, 148, 136, 0.55),
    inset 0 1px 0 rgba(255, 255, 255, 0.22);
}

.lib__btn--lg {
  padding: 0.62rem 1.35rem;
  font-size: 0.95rem;
  border-radius: 12px;
}

.lib__foot {
  margin-top: 2rem;
  padding-top: 1rem;
  border-top: 1px solid rgba(226, 232, 240, 0.85);
  font-size: 0.92rem;
}

.lib__link {
  color: var(--teal);
  font-weight: 600;
  text-decoration: none;
}

.lib__link:hover {
  text-decoration: underline;
}

.lib__dot {
  margin: 0 0.35rem;
  color: #94a3b8;
}

@media (max-width: 720px) {
  .lib__layout {
    grid-template-columns: 1fr;
  }

  .lib__sidebar {
    flex-direction: row;
    flex-wrap: wrap;
    align-items: center;
    padding: 0.75rem 0.65rem;
    gap: 0.5rem;
  }

  .lib__sidebar-label {
    width: 100%;
    margin-bottom: 0.15rem;
  }

  .lib__nav-item {
    flex: 1 1 auto;
    min-width: calc(33.333% - 0.35rem);
    text-align: center;
    padding: 0.55rem 0.5rem;
    font-size: 0.85rem;
  }

  .lib__nav-item--active {
    box-shadow: inset 0 -3px 0 var(--teal);
  }
}
</style>
