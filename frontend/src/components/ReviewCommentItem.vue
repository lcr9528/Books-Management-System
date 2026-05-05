<script setup>
import { computed } from 'vue'
import ReviewCommentItem from './ReviewCommentItem.vue'

const props = defineProps({
  node: { type: Object, required: true },
  bookId: { type: Number, required: true },
  reviewId: { type: Number, required: true },
  depth: { type: Number, default: 0 },
  replyDraft: { type: Object, required: true },
  replyingToId: { type: [Number, null], default: null },
  currentUserId: { type: [Number, null], default: null },
  isLoggedIn: { type: Boolean, default: false },
  isLibrarian: { type: Boolean, default: false },
})

const emit = defineEmits([
  'like',
  'toggle-reply',
  'delete',
  'update-draft',
  'submit-reply',
])

/** 避免 props 为字符串时 depth+1 变成 "01" 等拼接错误 */
const depthN = computed(() => {
  const d = Number(props.depth)
  return Number.isFinite(d) && d >= 0 ? Math.floor(d) : 0
})

const replyKey = computed(() => `${props.reviewId}-${props.node.id}`)

const directReplyCount = computed(() => (props.node.replies || []).length)

const canDelete = computed(() => {
  const uid = props.currentUserId
  if (uid == null) return false
  return props.node.user === uid || props.isLibrarian
})

function escapeRegExp(s) {
  return String(s).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

/** 从正文解析「回复 某人：」前缀（兼容多种冒号、首尾空白） */
function parseReplyPrefix(content) {
  const raw = String(content ?? '')
    .replace(/^\uFEFF/, '')
    .trim()
  if (!raw) return { target: null, body: '' }
  const m = raw.match(/^回复\s*(.+?)\s*[﹕∶：:]\s*([\s\S]*)$/)
  if (!m) return { target: null, body: raw }
  const target = (m[1] || '').trim()
  return { target: target || null, body: m[2] ?? '' }
}

const normalizedRawContent = computed(() =>
  String(props.node.content ?? '')
    .replace(/^\uFEFF/, '')
    .trim()
)

const parsedFromContent = computed(() => parseReplyPrefix(normalizedRawContent.value))

/** 正文是否为「回复某人：正文」结构（用于纠正 parent/depth 缺失的老数据） */
const looksLikeStructuredReply = computed(() => {
  const raw = normalizedRawContent.value
  const p = parsedFromContent.value
  return !!(p.target && /^回复\s/.test(raw) && p.body !== raw)
})

const hasParentRef = computed(() => {
  const p = props.node.parent
  return p != null && p !== ''
})

/** 被回复者展示名 */
const replyTargetLabel = computed(() => {
  const fromApi = String(props.node.parent_user_username ?? '').trim()
  if (fromApi) return fromApi
  const p = parsedFromContent.value
  if (!p.target) return ''
  if (depthN.value > 0) return p.target
  if (hasParentRef.value) return p.target
  if (looksLikeStructuredReply.value) return p.target
  return ''
})

/** 头像右侧一行展示「X 回复 Y」 */
const showReplyTarget = computed(() => !!replyTargetLabel.value)

/** 仅展示用户正文，去掉入库前缀 */
const displayContent = computed(() => {
  const raw = normalizedRawContent.value
  const label = replyTargetLabel.value
  if (label) {
    const re = new RegExp(`^回复\\s*${escapeRegExp(label)}\\s*[﹕∶：:]\\s*`)
    const cut = raw.replace(re, '')
    if (cut !== raw) return cut
  }
  const p = parseReplyPrefix(raw)
  if (p.target && p.body !== raw) return p.body
  return raw
})

function formatDateTime(dt) {
  if (!dt) return '—'
  const raw = String(dt).replace('T', ' ')
  const noTz = raw.replace(/(Z|[+-]\d{2}:?\d{2})$/, '')
  return noTz.split('.')[0]
}

function userInitial(name) {
  const s = String(name || '').trim()
  return s ? s.slice(0, 1).toUpperCase() : '?'
}

function onLike() {
  emit('like', props.node)
}

function onToggleReply() {
  emit('toggle-reply', props.node)
}

function onDelete() {
  emit('delete', props.node)
}

function onInput(e) {
  emit('update-draft', { key: replyKey.value, text: e.target.value })
}

function onSubmitReply() {
  emit('submit-reply', {
    reviewId: props.reviewId,
    parentId: props.node.id,
    replyToUsername: props.node.user_username,
  })
}
</script>

<template>
  <div class="rci" :id="'bd-rev-cmt-' + node.id">
    <div class="rci__inner">
      <div class="rci__head">
        <div class="rci__avatar-wrap">
          <img
            v-if="node.user_avatar"
            :src="node.user_avatar"
            alt=""
            class="rci__avatar-img"
            width="40"
            height="40"
          />
          <div v-else class="rci__avatar-ph" aria-hidden="true">
            {{ userInitial(node.user_username) }}
          </div>
        </div>
        <div class="rci__meta-wrap">
          <div class="rci__meta">
            <div class="rci__meta-main">
              <span class="rci__user">{{ node.user_username }}</span>
              <span
                v-if="node.is_follow_up_review"
                class="rci__follow-tag"
                title="本人追评"
                >追评</span
              >
              <template v-if="showReplyTarget">
                <span class="rci__reply-verb">回复</span>
                <span class="rci__reply-target">{{ replyTargetLabel }}</span>
              </template>
            </div>
            <button
              v-if="canDelete"
              type="button"
              class="rci__del"
              @click="onDelete"
            >
              删除
            </button>
          </div>
        </div>
      </div>
      <div class="rci__body-row">
        <p class="rci__text">{{ displayContent }}</p>
      </div>
      <div class="rci__actions-row">
        <div class="rci__actions-row__left">
          <span class="rci__time">{{ formatDateTime(node.created_at) }}</span>
          <button
            type="button"
            class="rci__reply-link--inline bd__rev-reply-trigger"
            @click="onToggleReply"
          >
            回复
          </button>
        </div>
        <div class="rci__actions-row__right">
          <button
            type="button"
            class="rci__act"
            :class="{ 'rci__act--liked': node.liked_by_me }"
            :aria-pressed="!!node.liked_by_me"
            aria-label="点赞"
            @click="onLike"
          >
            <svg
              class="rci__ico rci__ico-heart"
              viewBox="0 0 24 24"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
              aria-hidden="true"
            >
              <path
                d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"
                stroke="currentColor"
                stroke-width="1.6"
                stroke-linejoin="round"
              />
            </svg>
            <span class="rci__num">{{ node.like_count ?? 0 }}</span>
          </button>
          <button
            type="button"
            class="rci__act rci__act--ghost bd__rev-reply-trigger"
            aria-label="回复"
            @click="onToggleReply"
          >
            <svg
              class="rci__ico rci__ico-chat"
              viewBox="0 0 24 24"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
              aria-hidden="true"
            >
              <path
                d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"
                stroke="currentColor"
                stroke-width="1.6"
                stroke-linejoin="round"
              />
            </svg>
            <span class="rci__num">{{ directReplyCount }}</span>
          </button>
        </div>
      </div>
      <div
        v-if="replyingToId === node.id && isLoggedIn"
        class="rci__reply-row"
        data-bd-reply-ui
        @click.stop
      >
        <div class="rci__reply-row__field">
          <span class="rci__reply-prefix" aria-hidden="true">回复 {{ node.user_username }}：</span>
          <input
            :value="replyDraft[replyKey] || ''"
            type="text"
            class="rci__reply-input"
            maxlength="2000"
            placeholder="输入内容…"
            @input="onInput"
            @keydown.enter.prevent="onSubmitReply"
          />
        </div>
        <button type="button" class="rci__reply-send" @click="onSubmitReply">
          回复
        </button>
      </div>
    </div>
    <ReviewCommentItem
      v-for="ch in node.replies || []"
      :key="ch.id"
      :node="ch"
      :book-id="bookId"
      :review-id="reviewId"
      :depth="depthN + 1"
      :reply-draft="replyDraft"
      :replying-to-id="replyingToId"
      :current-user-id="currentUserId"
      :is-logged-in="isLoggedIn"
      :is-librarian="isLibrarian"
      @like="$emit('like', $event)"
      @toggle-reply="$emit('toggle-reply', $event)"
      @delete="$emit('delete', $event)"
      @update-draft="$emit('update-draft', $event)"
      @submit-reply="$emit('submit-reply', $event)"
    />
  </div>
</template>

<style scoped>
.rci {
  --rci-avatar-size: 40px;
  --rci-gap: 0.65rem;
  padding: 0.35rem 0 0.15rem;
}
.rci__inner {
  padding-bottom: 0.45rem;
  border-bottom: 1px dashed #e8dfd0;
}
.rci:last-child > .rci__inner {
  border-bottom: none;
}
.rci__head {
  display: flex;
  align-items: center;
  gap: var(--rci-gap);
}
.rci__avatar-wrap {
  flex-shrink: 0;
}
.rci__avatar-img {
  display: block;
  width: var(--rci-avatar-size);
  height: var(--rci-avatar-size);
  border-radius: 50%;
  object-fit: cover;
  border: 1px solid #e8dfd0;
  background: #f8fafc;
}
.rci__avatar-ph {
  width: var(--rci-avatar-size);
  height: var(--rci-avatar-size);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.95rem;
  font-weight: 800;
  color: #fffef8;
  background: linear-gradient(145deg, #0d9488, #0f766e);
  border: 1px solid #cbd5e1;
}
.rci__meta-wrap {
  flex: 1;
  min-width: 0;
}
.rci__meta {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.88rem;
  color: #475569;
  min-width: 0;
}
.rci__meta-main {
  display: inline-flex;
  align-items: center;
  flex-wrap: nowrap;
  gap: 0.35rem;
  min-width: 0;
  flex: 1;
}
.rci__meta-main .rci__user,
.rci__meta-main .rci__reply-target {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.rci__user {
  font-weight: 700;
  color: #1e293b;
}
.rci__reply-verb {
  flex-shrink: 0;
  font-weight: 500;
  font-size: 0.82rem;
  color: #94a3b8;
}
.rci__follow-tag {
  margin-left: 0.35rem;
  padding: 0.05rem 0.42rem;
  font-size: 0.72rem;
  font-weight: 700;
  color: #94a3b8;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  background: #f8fafc;
  vertical-align: middle;
  line-height: 1.25;
}
.rci__reply-target {
  font-weight: 600;
  color: #64748b;
}
.rci__time {
  font-size: 0.82rem;
  line-height: 1.45;
  color: #94a3b8;
}
.rci__del {
  flex-shrink: 0;
  margin-left: 0;
  padding: 0.15rem 0.5rem;
  font-size: 0.8rem;
  border-radius: 6px;
  border: 1px solid #fecaca;
  background: #fff1f2;
  color: #b91c1c;
  cursor: pointer;
}
.rci__del:hover {
  background: #ffe4e6;
}
.rci__body-row {
  margin-top: 0.35rem;
  padding-left: calc(var(--rci-avatar-size) + var(--rci-gap));
}
.rci__text {
  margin: 0;
  font-size: 0.9rem;
  line-height: 1.55;
  color: #334155;
  word-break: break-word;
  white-space: pre-wrap;
}
.rci__actions-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.45rem 0.65rem;
  margin-top: 0.28rem;
  padding-left: calc(var(--rci-avatar-size) + var(--rci-gap));
  min-height: 1.55rem;
}
.rci__actions-row__left {
  display: inline-flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 0 0.65em;
  min-width: 0;
  font-size: 0.82rem;
  line-height: 1.45;
}
.rci__actions-row__right {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  flex-shrink: 0;
}
.rci__act {
  display: inline-flex;
  align-items: center;
  gap: 0.2rem;
  padding: 0.12rem 0.2rem;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: #64748b;
  cursor: pointer;
  font-size: 0.82rem;
}
.rci__act:hover {
  color: #334155;
  background: rgba(148, 163, 184, 0.12);
}
.rci__act--liked {
  color: #ea580c;
}
.rci__act--liked .rci__ico-heart {
  fill: #ea580c;
  stroke: #ea580c;
}
.rci__ico {
  width: 1.1rem;
  height: 1.1rem;
  flex-shrink: 0;
}
.rci__num {
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  min-width: 0.65rem;
}
.rci__reply-link--inline {
  display: inline-flex;
  align-items: center;
  margin: 0;
  padding: 0;
  border: none;
  border-radius: 4px;
  background: transparent;
  font-size: 0.82rem;
  font-weight: 500;
  color: #94a3b8;
  cursor: pointer;
  line-height: 1.45;
}
.rci__reply-link--inline:hover {
  color: #64748b;
  text-decoration: underline;
  text-underline-offset: 0.12em;
}
.rci__reply-row {
  display: flex;
  gap: 0.35rem;
  margin-top: 0.45rem;
  padding-left: calc(var(--rci-avatar-size) + var(--rci-gap));
  align-items: center;
}
.rci__reply-row__field {
  display: flex;
  align-items: center;
  flex: 1;
  min-width: 0;
  gap: 0.15rem;
}
.rci__reply-prefix {
  flex-shrink: 0;
  font-size: 0.82rem;
  line-height: 1.45;
  color: #94a3b8;
  user-select: none;
  white-space: nowrap;
}
.rci__reply-input {
  flex: 1;
  min-width: 0;
  border: 1px solid #d7c8b2;
  border-radius: 8px;
  padding: 0.28rem 0.45rem;
  font-size: 0.82rem;
  background: #fffdf9;
  color: #334155;
  caret-color: #64748b;
}
.rci__reply-input::placeholder {
  color: #94a3b8;
  opacity: 0.9;
}
.rci__reply-send {
  flex-shrink: 0;
  padding: 0.26rem 0.5rem;
  font-size: 0.78rem;
  border-radius: 8px;
  border: 1px solid #d9cdb9;
  background: #f5ecdf;
  cursor: pointer;
}
.rci__reply-send:hover {
  background: #efe3d2;
}
</style>
