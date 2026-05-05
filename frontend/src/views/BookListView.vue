<script setup>
import { onMounted, ref, watch } from 'vue'
import { listBooks, listCategories } from '../api/books'

const items = ref([])
const count = ref(0)
const hasNext = ref(false)
const loading = ref(false)
const err = ref('')
const q = ref('')

const categories = ref([])
const selectedCategory = ref(null)

const page = ref(1)
const pageSize = ref(10)
const pageSizeOptions = [10, 20, 50]

function buildParams() {
  const p = {
    page: page.value,
    page_size: pageSize.value,
    search: q.value || undefined,
  }
  if (selectedCategory.value != null) {
    p.category = selectedCategory.value
  }
  return p
}

async function load() {
  loading.value = true
  err.value = ''
  try {
    const { data } = await listBooks(buildParams())
    if (data.results) {
      items.value = data.results
      count.value = data.count ?? 0
      hasNext.value = Boolean(data.next)
    } else {
      items.value = data
      count.value = data.length
      hasNext.value = false
    }
  } catch (e) {
    err.value = e?.response?.data?.detail || e?.message || '加载失败'
  } finally {
    loading.value = false
  }
}

async function loadCategories() {
  try {
    const { data } = await listCategories()
    const raw = data.results != null ? data.results : data
    categories.value = Array.isArray(raw) ? raw : []
  } catch {
    categories.value = []
  }
}

onMounted(async () => {
  await loadCategories()
  load()
})

let t
watch(q, () => {
  page.value = 1
})
watch(pageSize, () => {
  page.value = 1
})
watch(selectedCategory, () => {
  page.value = 1
})
watch(
  [q, page, pageSize, selectedCategory],
  () => {
    clearTimeout(t)
    t = setTimeout(load, 300)
  },
  { deep: true }
)
</script>

<template>
  <div class="bl">
    <h1 class="bl__h">图书列表</h1>
    <p>
      <input
        v-model="q"
        class="bl__search"
        type="search"
        placeholder="按书名、作者、ISBN、出版社 搜索"
      />
    </p>
    <p v-if="err" class="bl__err">{{ err }}</p>
    <p v-else-if="loading" class="bl__hint">加载中…</p>
    <div v-else class="bl__layout">
      <aside class="bl__aside" aria-label="图书分类">
        <h2 class="bl__aside-title">分类</h2>
        <ul class="bl__cats" role="list">
          <li>
            <button
              type="button"
              class="bl__cat"
              :class="{ 'bl__cat--active': selectedCategory === null }"
              @click="selectedCategory = null"
            >
              全部
            </button>
          </li>
          <li v-for="c in categories" :key="c.id">
            <button
              type="button"
              class="bl__cat"
              :class="{ 'bl__cat--active': selectedCategory === c.id }"
              @click="selectedCategory = c.id"
            >
              {{ c.name }}
            </button>
          </li>
        </ul>
      </aside>
      <div class="bl__main">
        <ul class="bl__grid" role="list">
          <li v-for="b in items" :key="b.id" class="bl__cell">
            <router-link
              :to="{ name: 'book-detail', params: { id: b.id } }"
              class="bl__card"
            >
              <div class="bl__cover">
                <img
                  v-if="b.cover"
                  :src="b.cover"
                  :alt="b.title"
                  loading="lazy"
                  width="120"
                  height="168"
                />
                <div v-else class="bl__ph" aria-hidden="true">无封面</div>
              </div>
              <div class="bl__body">
                <h2 class="bl__title">{{ b.title }}</h2>
                <p v-if="b.category_name" class="bl__genre">{{ b.category_name }}</p>
                <p class="bl__author">{{ b.author }}</p>
                <p class="bl__isbn">ISBN {{ b.isbn }}</p>
                <p class="bl__meta">
                  在架 <strong>{{ b.available_copies }}</strong> / 总册
                  <strong>{{ b.total_copies }}</strong>
                </p>
              </div>
            </router-link>
          </li>
        </ul>
        <p v-if="!items.length" class="bl__empty">暂无数据</p>
        <div class="bl__foot">
          <p class="bl__back">
            <router-link to="/">返回首页</router-link>
          </p>
          <p class="bl__page">
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
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.bl {
  --teal: #0d9488;
  --teal-light: #f0fdfa;
  /* 分类按钮：选中 / 悬停（未选）共用同一套渐变与阴影，避免 filter 破坏渐变显示 */
  --bl-cat-grad: linear-gradient(135deg, #14b8a6 0%, #0d9488 48%, #0f766e 100%);
  --bl-cat-shadow:
    0 8px 22px -8px rgba(13, 148, 136, 0.55),
    0 3px 10px -4px rgba(15, 23, 42, 0.15),
    inset 0 1px 0 rgba(255, 255, 255, 0.22);
  --bl-cat-shadow-hover:
    0 10px 28px -8px rgba(13, 148, 136, 0.62),
    0 4px 14px -4px rgba(15, 23, 42, 0.14),
    inset 0 1px 0 rgba(255, 255, 255, 0.28);
  width: 100%;
  max-width: none;
  margin: 0;
  padding: 0.5rem clamp(1rem, 3vw, 2rem) 2rem;
}
.bl__h {
  font-size: 1.4rem;
  font-weight: 800;
  letter-spacing: -0.02em;
  color: #1a1a2e;
  margin: 0 0 0.75rem;
}
.bl__search {
  width: min(640px, 100%);
  padding: 0.5rem 0.65rem;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  font-size: 0.95rem;
}
.bl__err {
  color: #b91c1c;
  margin: 0.5rem 0 0;
}
.bl__hint {
  color: #64748b;
  margin: 0.5rem 0 0;
}
.bl__layout {
  display: grid;
  grid-template-columns: 13rem minmax(0, 1fr);
  gap: 1.5rem;
  align-items: start;
  margin-top: 0.75rem;
}
.bl__aside {
  position: sticky;
  top: 0.75rem;
  padding: 1rem 0.7rem 1.15rem;
  background: linear-gradient(165deg, #ffffff 0%, #f8fafc 100%);
  border: 1px solid rgba(226, 232, 240, 0.95);
  border-radius: 16px;
  box-shadow:
    0 4px 6px -1px rgba(15, 23, 42, 0.06),
    0 10px 28px -12px rgba(15, 23, 42, 0.1),
    inset 0 1px 0 rgba(255, 255, 255, 0.85);
}
.bl__aside-title {
  margin: 0 0 0.75rem;
  padding: 0 0.15rem 0.65rem;
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.14em;
  color: #475569;
  text-transform: uppercase;
  border-bottom: 1px solid rgba(226, 232, 240, 0.95);
  display: flex;
  align-items: center;
  gap: 0.45rem;
}
.bl__aside-title::before {
  content: '';
  width: 3px;
  height: 0.95rem;
  border-radius: 2px;
  background: linear-gradient(180deg, var(--teal) 0%, #0f766e 100%);
  flex-shrink: 0;
}
.bl__cats {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.42rem;
}
.bl__cat {
  display: block;
  width: 100%;
  text-align: left;
  padding: 0.58rem 0.72rem;
  border: 1px solid rgba(226, 232, 240, 0.9);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.72);
  font-size: 0.875rem;
  color: #334155;
  cursor: pointer;
  line-height: 1.4;
  font-weight: 500;
  transition:
    transform 0.2s cubic-bezier(0.34, 1.2, 0.64, 1),
    box-shadow 0.2s ease,
    border-color 0.2s ease,
    background 0.2s ease,
    color 0.2s ease;
}
/* 未选中项悬停：与选中态同一套渐变；阴影略加强，与选中项悬停一致 */
.bl__cat:hover:not(.bl__cat--active) {
  border-color: transparent;
  background: var(--bl-cat-grad);
  color: #fff;
  font-weight: 700;
  box-shadow: var(--bl-cat-shadow-hover);
  transform: translateX(0);
}
.bl__cat--active {
  border-color: transparent;
  background: var(--bl-cat-grad);
  color: #fff;
  font-weight: 700;
  box-shadow: var(--bl-cat-shadow);
  transform: translateX(0);
}
/* 选中项悬停：保持渐变，仅用阴影略增强；勿用 filter，否则部分浏览器会把渐变显示成纯色块 */
.bl__cat--active:hover {
  background: var(--bl-cat-grad);
  box-shadow: var(--bl-cat-shadow-hover);
}
.bl__cat:focus {
  outline: none;
}
.bl__cat:focus-visible {
  outline: 2px solid var(--teal);
  outline-offset: 2px;
}
.bl__cat:focus-visible.bl__cat--active {
  outline-color: #99f6e4;
}
.bl__main {
  min-width: 0;
}
.bl__genre {
  font-size: 0.74rem;
  color: #0d9488;
  font-weight: 600;
  margin: 0 0 0.2rem;
  display: -webkit-box;
  line-clamp: 1;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.bl__grid {
  list-style: none;
  margin: 0.75rem 0 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 1.2rem;
}
.bl__cell {
  width: 100%;
  max-width: 300px;
  justify-self: center;
}
.bl__card {
  display: block;
  height: 100%;
  text-decoration: none;
  color: inherit;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 4px 6px -1px rgba(15, 23, 42, 0.05);
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s;
}
.bl__card:hover {
  transform: translateY(-3px);
  box-shadow: 0 16px 32px -12px rgba(15, 23, 42, 0.15);
  border-color: rgba(20, 184, 166, 0.35);
}
.bl__cover {
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
}
.bl__cover img {
  width: 100%;
  height: auto;
  object-fit: contain;
  display: block;
}
.bl__ph {
  font-size: 0.8rem;
  color: #94a3b8;
}
.bl__body {
  padding: 0.62rem 0.75rem 0.8rem;
}
.bl__title {
  font-size: 0.95rem;
  font-weight: 800;
  line-height: 1.3;
  margin: 0 0 0.3rem;
  color: #1a1a2e;
  display: -webkit-box;
  line-clamp: 2;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.bl__author {
  font-size: 0.82rem;
  color: #475569;
  margin: 0 0 0.2rem;
}
.bl__isbn {
  font-size: 0.75rem;
  color: #94a3b8;
  margin: 0 0 0.35rem;
  word-break: break-all;
}
.bl__meta {
  font-size: 0.78rem;
  color: #64748b;
  margin: 0 0 0.3rem;
}
.bl__meta strong {
  color: #0d9488;
  font-weight: 700;
}
.bl__cta {
  font-size: 0.8rem;
  font-weight: 700;
  color: var(--teal);
}
.bl__empty {
  text-align: center;
  color: #64748b;
  margin: 1.5rem 0;
  font-size: 0.9rem;
}
.bl__foot {
  margin-top: 1.25rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  flex-wrap: wrap;
}
.bl__page {
  margin: 0;
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
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  color: #0f172a;
  background: #fff;
}
.bl__page button {
  border-color: #cbd5e1;
  color: #0f172a;
}
.bl__count {
  color: #6b7280;
  font-size: 0.9rem;
  margin-left: 0.25rem;
}
.bl__back {
  margin: 0;
  font-size: 0.92rem;
}
.bl__back a {
  color: var(--teal);
  font-weight: 600;
}

@media (max-width: 1400px) {
  .bl__grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}

@media (max-width: 1120px) {
  .bl__grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 820px) {
  .bl__grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 520px) {
  .bl__grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .bl__layout {
    grid-template-columns: 1fr;
  }
  .bl__aside {
    position: static;
  }
}
</style>
