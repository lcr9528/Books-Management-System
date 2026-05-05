<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  listNotifications,
  markNotificationRead,
  markAllNotificationsRead,
} from '../api/notifications'

const router = useRouter()
const items = ref([])
const loading = ref(true)
const err = ref('')
const markingAll = ref(false)

const kindText = {
  review_liked: '书评被点赞',
  review_commented: '书评被评论',
  comment_replied: '评论被回复',
}

function formatTime(dt) {
  if (!dt) return '—'
  const raw = String(dt).replace('T', ' ')
  return raw.replace(/(Z|[+-]\d{2}:?\d{2})$/, '').split('.')[0]
}

async function load() {
  err.value = ''
  loading.value = true
  try {
    const { data } = await listNotifications({ page_size: 50 })
    const raw = data
    items.value = Array.isArray(raw) ? raw : raw?.results ?? []
  } catch (e) {
    err.value = e?.response?.data?.detail || e?.message || '加载失败'
    items.value = []
  } finally {
    loading.value = false
  }
}

async function onRowClick(n) {
  if (!n.is_read) {
    try {
      await markNotificationRead(n.id)
    } catch {
      /* 仍尝试跳转 */
    }
    n.is_read = true
  }
  window.dispatchEvent(new Event('app:poll-unread'))
  const bookId = n.book
  const reviewId = n.book_review
  const hash = `bd-rev-item-${reviewId}`
  const query = {}
  if (
    (n.kind === 'review_commented' || n.kind === 'comment_replied') &&
    n.comment != null &&
    n.comment !== ''
  ) {
    query.comment = String(n.comment)
  }
  await router.push({
    name: 'book-detail',
    params: { id: String(bookId) },
    hash: `#${hash}`,
    query,
  })
}

async function onMarkAll() {
  markingAll.value = true
  try {
    await markAllNotificationsRead()
    items.value = items.value.map((x) => ({ ...x, is_read: true }))
    window.dispatchEvent(new Event('app:poll-unread'))
  } catch (e) {
    err.value = e?.response?.data?.detail || e?.message || '操作失败'
  } finally {
    markingAll.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="notif container">
    <div class="notif__head">
      <h1 class="notif__title">消息通知</h1>
      <button
        type="button"
        class="notif__mark-all"
        :disabled="markingAll || items.filter((x) => !x.is_read).length === 0"
        @click="onMarkAll"
      >
        {{ markingAll ? '处理中…' : '全部已读' }}
      </button>
    </div>
    <p v-if="loading" class="muted">加载中…</p>
    <p v-else-if="err" class="err">{{ err }}</p>
    <ul v-else-if="items.length" class="notif__list">
      <li
        v-for="n in items"
        :key="n.id"
        class="notif__item"
        :class="{ 'notif__item--unread': !n.is_read }"
        role="button"
        tabindex="0"
        @click="onRowClick(n)"
        @keydown.enter="onRowClick(n)"
      >
        <div class="notif__item-top">
          <span class="notif__kind">{{ kindText[n.kind] || n.kind }}</span>
          <span class="notif__time">{{ formatTime(n.created_at) }}</span>
        </div>
        <p class="notif__preview">{{ n.preview }}</p>
        <p class="notif__book muted">{{ n.book_title }}</p>
      </li>
    </ul>
    <p v-else class="muted">暂无通知</p>
  </div>
</template>

<style scoped>
.notif {
  max-width: 720px;
  margin: 0 auto;
  padding: 1.25rem 1rem 2rem;
}
.notif__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1rem;
}
.notif__title {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 800;
  color: #1a1a2e;
}
.notif__mark-all {
  padding: 0.35rem 0.75rem;
  font-size: 0.86rem;
  border-radius: 8px;
  border: 1px solid #d9cdb9;
  background: #f5ecdf;
  color: #5b4636;
  cursor: pointer;
}
.notif__mark-all:hover:not(:disabled) {
  background: #efe3d2;
}
.notif__mark-all:disabled {
  opacity: 0.55;
  cursor: default;
}
.notif__list {
  list-style: none;
  margin: 0;
  padding: 0;
}
.notif__item {
  padding: 0.85rem 1rem;
  margin-bottom: 0.5rem;
  border-radius: 12px;
  border: 1px solid #e8dfd0;
  background: #fffefb;
  cursor: pointer;
  transition: background 0.15s ease;
}
.notif__item:hover {
  background: #fff7e8;
}
.notif__item--unread {
  border-color: #c4a574;
  box-shadow: 0 0 0 1px rgba(194, 146, 88, 0.25);
}
.notif__item-top {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 0.5rem;
  margin-bottom: 0.35rem;
}
.notif__kind {
  font-size: 0.88rem;
  font-weight: 700;
  color: #0f766e;
}
.notif__time {
  font-size: 0.78rem;
  color: #94a3b8;
}
.notif__preview {
  margin: 0;
  font-size: 0.92rem;
  line-height: 1.5;
  color: #334155;
}
.notif__book {
  margin: 0.35rem 0 0;
  font-size: 0.82rem;
}
.err {
  color: #b91c1c;
}
.muted {
  color: #64748b;
}
</style>
