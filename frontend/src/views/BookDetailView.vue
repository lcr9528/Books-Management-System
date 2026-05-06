<script setup>
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  reactive,
  ref,
  watch,
} from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  getBook,
  borrowBook,
  listBookChapters,
  listBookReviews,
  getMyBookReview,
  createBookReview,
  createBookReviewComment,
  deleteMyBookReview,
  deleteBookReviewAsLibrarian,
  listBookReviewComments,
  toggleBookReviewLike,
  toggleBookReviewCommentLike,
  deleteBookReviewComment,
} from '../api/books'
import ReviewCommentItem from '../components/ReviewCommentItem.vue'
import { useUser, isLibrarian } from '../auth'
import { showToast } from '../composables/useToast'

const route = useRoute()
const router = useRouter()
const { isLoggedIn, user } = useUser()
const id = computed(() => Number(route.params.id))
const book = ref(null)
const err = ref('')

/** 无在架、或本人已在借本书时不可再借（后端亦限制一人一书一条在借） */
const borrowDisabled = computed(() => {
  const b = book.value
  if (!b) return true
  if (b.available_copies < 1) return true
  if (isLoggedIn.value && b.has_my_active_borrow) return true
  return false
})

/** 点击章节时因未借阅被拦截：弹窗提示（须手动点「知道了」关闭） */
const readBlockModalVisible = ref(false)
const borrowModalVisible = ref(false)
const borrowDueAt = ref('')
const borrowLoading = ref(false)
const borrowDueAtInput = ref(null)

const chapters = ref([])
const chaptersErr = ref('')

const reviews = ref([])
const reviewsLoading = ref(false)
const reviewsErr = ref('')
const myReview = ref(null)
/** 书评评分：null 表示不选星，1～5 为星数 */
const reviewRatingStars = ref(null)
const reviewContent = ref('')
const reviewSubmitting = ref(false)
const reviewErr = ref('')
/** 删除书评确认弹窗（mine：本人；staff：管理员删任意一条） */
const reviewDeleteModalVisible = ref(false)
const reviewDeleteMode = ref('mine')
const staffDeleteReviewId = ref(null)
const reviewDeleteLoading = ref(false)
/** 是否展开「撰写书评」表单（默认收起，点标题栏「发表书评」展开） */
const reviewComposeOpen = ref(false)
/** 目录每行列数（随窗口变化，与 tocRows 分块一致） */
const tocCols = ref(3)

/** 书评点赞 / 评论区 */
const commentsExpanded = reactive({})
const commentsByReview = reactive({})
const commentsLoading = reactive({})
const commentDraftTop = reactive({})
const replyDraft = reactive({})
/** 顶层评论「查看更多」：默认展示 3 条线程 */
const visibleTopLimit = reactive({})
/** 当前书评下正在回复哪条评论 id */
const replyingToComment = reactive({})
/** 书评层「回复」打开的顶层输入框（不依赖展开评论区） */
const topReplyOpen = reactive({})

const reviewDeleteMessage = computed(() =>
  reviewDeleteMode.value === 'staff'
    ? '确定删除该条书评？（管理员操作）'
    : '确定删除我的书评？'
)

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

function starsText(rating) {
  if (rating == null || rating < 1) return ''
  const r = Math.min(5, Math.max(1, Math.floor(Number(rating))))
  return '★'.repeat(r)
}

async function loadReviews() {
  reviewsErr.value = ''
  reviewsLoading.value = true
  try {
    const lr = await listBookReviews(id.value, { page_size: 100 })
    const raw = lr.data
    reviews.value = Array.isArray(raw) ? raw : raw?.results ?? []
    myReview.value = null
    reviewRatingStars.value = null
    reviewContent.value = ''
    reviewErr.value = ''
    if (isLoggedIn.value) {
      try {
        const mr = await getMyBookReview(id.value)
        myReview.value = mr.data
      } catch (e) {
        if (e?.response?.status !== 404) {
          reviewsErr.value =
            e?.response?.data?.detail || e?.message || '我的书评加载失败'
        }
      }
    }
  } catch (e) {
    reviewsErr.value = e?.response?.data?.detail || e?.message || '书评列表加载失败'
    reviews.value = []
  } finally {
    reviewsLoading.value = false
  }
}

function clearReviewSocialState() {
  for (const k of Object.keys(commentsExpanded)) delete commentsExpanded[k]
  for (const k of Object.keys(commentsByReview)) delete commentsByReview[k]
  for (const k of Object.keys(commentsLoading)) delete commentsLoading[k]
  for (const k of Object.keys(commentDraftTop)) delete commentDraftTop[k]
  for (const k of Object.keys(replyDraft)) delete replyDraft[k]
  for (const k of Object.keys(visibleTopLimit)) delete visibleTopLimit[k]
  for (const k of Object.keys(replyingToComment)) delete replyingToComment[k]
  for (const k of Object.keys(topReplyOpen)) delete topReplyOpen[k]
}

/** 收起全部回复输入（书评顶层 + 所有评论下的回复框） */
function closeAllReplyDrafts() {
  for (const k of Object.keys(replyingToComment)) delete replyingToComment[k]
  for (const k of Object.keys(topReplyOpen)) delete topReplyOpen[k]
}

function onDocumentPointerDown(ev) {
  const t = ev.target
  if (t.closest?.('[data-bd-reply-ui]')) return
  if (t.closest?.('.bd__rev-reply-trigger')) return
  closeAllReplyDrafts()
}

/** 点击评论区（展开列表）以外处收起评论列表；不关闭回复输入区 */
function onDocumentClickCollapseComments(ev) {
  const t = ev.target
  if (t.closest?.('.bd__rev-comments')) return
  if (t.closest?.('.bd__rev-cmt-toggle')) return
  if (t.closest?.('[data-bd-reply-ui]')) return
  for (const k of Object.keys(commentsExpanded)) {
    if (commentsExpanded[k]) commentsExpanded[k] = false
  }

  if (reviewComposeOpen.value) {
    if (t.closest?.('.bd__rev-form-wrap')) return
    if (t.closest?.('[data-bd-rev-compose-toggle]')) return
    reviewComposeOpen.value = false
  }
}

function countCommentsInTree(list) {
  if (!list?.length) return 0
  return list.reduce(
    (sum, c) => sum + 1 + countCommentsInTree(c.replies || []),
    0
  )
}

function patchCommentNode(reviewId, commentId, updater) {
  const list = commentsByReview[reviewId]
  if (!list) return
  function walk(arr) {
    for (const c of arr) {
      if (c.id === commentId) {
        updater(c)
        return true
      }
      if (c.replies?.length && walk(c.replies)) return true
    }
    return false
  }
  walk(list)
}

function visibleTopThreads(reviewId) {
  const all = commentsByReview[reviewId] || []
  const lim = visibleTopLimit[reviewId] ?? 3
  return all.slice(0, lim)
}

function hasMoreTopThreads(reviewId) {
  const all = commentsByReview[reviewId] || []
  const lim = visibleTopLimit[reviewId] ?? 3
  return all.length > lim
}

function showMoreTopThreads(reviewId) {
  visibleTopLimit[reviewId] = (commentsByReview[reviewId] || []).length
}

async function onCommentLike(node, reviewId) {
  reviewErr.value = ''
  if (!isLoggedIn.value) {
    reviewErr.value = '请先登录后再点赞。'
    return
  }
  try {
    const { data } = await toggleBookReviewCommentLike(
      id.value,
      reviewId,
      node.id
    )
    patchCommentNode(reviewId, node.id, (n) => {
      n.liked_by_me = data.liked
      n.like_count = data.like_count
    })
  } catch (e) {
    reviewErr.value = e?.response?.data?.detail || e?.message || '操作失败'
  }
}

function toggleCommentReplyRow(reviewId, node) {
  reviewErr.value = ''
  if (!isLoggedIn.value) {
    reviewErr.value = '请先登录后再回复。'
    return
  }
  const cur = replyingToComment[reviewId]
  const key = `${reviewId}-${node.id}`
  if (cur === node.id) {
    replyingToComment[reviewId] = null
    return
  }
  for (const k of Object.keys(topReplyOpen)) delete topReplyOpen[k]
  for (const k of Object.keys(replyingToComment)) delete replyingToComment[k]
  replyingToComment[reviewId] = node.id
  replyDraft[key] = ''
}

async function onReplyToBookReview(r) {
  reviewErr.value = ''
  if (!isLoggedIn.value) {
    reviewErr.value = '请先登录后再回复。'
    return
  }
  for (const k of Object.keys(replyingToComment)) delete replyingToComment[k]
  for (const k of Object.keys(topReplyOpen)) delete topReplyOpen[k]
  commentsExpanded[r.id] = false
  topReplyOpen[r.id] = true
  commentDraftTop[r.id] = ''
  await nextTick()
  document.getElementById(`bd-rev-top-cmt-${r.id}`)?.focus()
}

function onCommentReplyDraft({ key, text }) {
  replyDraft[key] = text
}

async function deleteCommentRow(reviewId, node) {
  reviewErr.value = ''
  try {
    await deleteBookReviewComment(id.value, reviewId, node.id)
    if (replyingToComment[reviewId] === node.id) {
      replyingToComment[reviewId] = null
    }
    delete topReplyOpen[reviewId]
    commentDraftTop[reviewId] = ''
    delete visibleTopLimit[reviewId]
    delete commentsByReview[reviewId]
    await ensureCommentsLoaded(reviewId)
    const cnt = countCommentsInTree(commentsByReview[reviewId])
    const rv = reviews.value.find((x) => x.id === reviewId)
    if (rv) rv.comment_count = cnt
    if (cnt === 0) commentsExpanded[reviewId] = false
  } catch (e) {
    reviewErr.value = e?.response?.data?.detail || e?.message || '删除失败'
  }
}

async function fetchBookPage() {
  err.value = ''
  readBlockModalVisible.value = false
  chaptersErr.value = ''
  chapters.value = []
  book.value = null
  reviews.value = []
  myReview.value = null
  reviewComposeOpen.value = false
  clearReviewSocialState()
  try {
    const { data } = await getBook(id.value)
    book.value = data
    try {
      const cr = await listBookChapters(id.value)
      chapters.value = Array.isArray(cr.data) ? cr.data : cr.data?.results ?? []
    } catch (ce) {
      chaptersErr.value = ce?.response?.data?.detail || ce?.message || '章节列表加载失败'
    }
    await loadReviews()
  } catch (e) {
    err.value = e?.response?.data?.detail || e?.message || '加载失败'
  }
}

async function scrollToReviewHash() {
  const raw = route.hash?.replace(/^#/, '')
  if (!raw || !raw.startsWith('bd-rev-item-')) return
  const reviewId = Number(raw.slice('bd-rev-item-'.length))
  if (!Number.isFinite(reviewId)) return

  const qc = route.query.comment
  const focusCmt =
    qc != null && qc !== ''
      ? Number(Array.isArray(qc) ? qc[0] : qc)
      : NaN
  const wantsComment = Number.isFinite(focusCmt)

  if (wantsComment) {
    commentsExpanded[reviewId] = true
    await ensureCommentsLoaded(reviewId, true)
    ensureCommentThreadVisible(reviewId, focusCmt)
    await nextTick()
    await nextTick()
    requestAnimationFrame(() => {
      document.getElementById(raw)?.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
      })
      requestAnimationFrame(() => {
        document
          .getElementById(`bd-rev-cmt-${focusCmt}`)
          ?.scrollIntoView({ behavior: 'smooth', block: 'center' })
      })
    })
    return
  }

  nextTick(() => {
    requestAnimationFrame(() => {
      document.getElementById(raw)?.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
      })
    })
  })
}

async function ensureCommentsLoaded(reviewId, force = false) {
  if (force) {
    delete commentsByReview[reviewId]
    delete commentsLoading[reviewId]
  }
  if (reviewId in commentsByReview) return
  commentsLoading[reviewId] = true
  try {
    const { data } = await listBookReviewComments(id.value, reviewId)
    commentsByReview[reviewId] = Array.isArray(data) ? data : data?.results ?? []
  } catch {
    commentsByReview[reviewId] = []
  } finally {
    commentsLoading[reviewId] = false
  }
}

/** 展开「查看更多」直到包含目标评论所在的一级线程 */
function ensureCommentThreadVisible(reviewId, commentId) {
  const list = commentsByReview[reviewId]
  if (!list?.length) return
  function contains(node, cid) {
    if (node.id === cid) return true
    for (const ch of node.replies || []) {
      if (contains(ch, cid)) return true
    }
    return false
  }
  let idx = -1
  for (let i = 0; i < list.length; i++) {
    if (contains(list[i], commentId)) {
      idx = i
      break
    }
  }
  if (idx < 0) return
  const lim = visibleTopLimit[reviewId] ?? 3
  if (idx >= lim) visibleTopLimit[reviewId] = idx + 1
}

/** 右下角评论图标：有评论则只展开列表（不显示顶层回复框）；无评论则只打开回复框 */
async function onReviewCommentIconClick(r) {
  reviewErr.value = ''
  const n = Number(r.comment_count ?? 0)
  if (n > 0) {
    const willOpen = !commentsExpanded[r.id]
    commentsExpanded[r.id] = willOpen
    if (willOpen) {
      delete topReplyOpen[r.id]
      await ensureCommentsLoaded(r.id)
    }
    return
  }
  if (!isLoggedIn.value) {
    reviewErr.value = '请先登录后再评论。'
    return
  }
  for (const k of Object.keys(replyingToComment)) delete replyingToComment[k]
  for (const k of Object.keys(topReplyOpen)) delete topReplyOpen[k]
  topReplyOpen[r.id] = true
  commentsExpanded[r.id] = false
  commentDraftTop[r.id] = ''
  await nextTick()
  document.getElementById(`bd-rev-top-cmt-${r.id}`)?.focus()
}

async function onToggleLike(r) {
  reviewErr.value = ''
  if (!isLoggedIn.value) {
    reviewErr.value = '请先登录后再点赞。'
    return
  }
  try {
    const { data } = await toggleBookReviewLike(id.value, r.id)
    r.liked_by_me = data.liked
    r.like_count = data.like_count
  } catch (e) {
    reviewErr.value = e?.response?.data?.detail || e?.message || '操作失败'
  }
}

async function submitTopComment(reviewId) {
  reviewErr.value = ''
  const body = String(commentDraftTop[reviewId] || '').trim()
  if (!body) return
  if (!isLoggedIn.value) {
    reviewErr.value = '请先登录。'
    return
  }
  const rv = reviews.value.find((x) => x.id === reviewId)
  const prefix = rv?.user_username ? `回复 ${rv.user_username}：` : ''
  const text = `${prefix}${body}`
  try {
    await createBookReviewComment(id.value, reviewId, { content: text })
    commentDraftTop[reviewId] = ''
    delete visibleTopLimit[reviewId]
    delete commentsByReview[reviewId]
    await ensureCommentsLoaded(reviewId)
    const rv = reviews.value.find((x) => x.id === reviewId)
    if (rv) rv.comment_count = countCommentsInTree(commentsByReview[reviewId])
    delete topReplyOpen[reviewId]
    commentsExpanded[reviewId] = true
  } catch (e) {
    reviewErr.value = e?.response?.data?.detail || e?.message || '发送失败'
  }
}

async function submitReply(payload) {
  const { reviewId, parentId, replyToUsername } = payload
  reviewErr.value = ''
  const key = `${reviewId}-${parentId}`
  const body = String(replyDraft[key] || '').trim()
  if (!body) return
  if (!isLoggedIn.value) {
    reviewErr.value = '请先登录。'
    return
  }
  const uname = String(replyToUsername || '').trim()
  const prefix = uname ? `回复 ${uname}：` : ''
  const text = `${prefix}${body}`
  try {
    await createBookReviewComment(id.value, reviewId, {
      content: text,
      parent: parentId,
    })
    replyDraft[key] = ''
    replyingToComment[reviewId] = null
    delete visibleTopLimit[reviewId]
    delete commentsByReview[reviewId]
    await ensureCommentsLoaded(reviewId)
    const rv = reviews.value.find((x) => x.id === reviewId)
    if (rv) rv.comment_count = countCommentsInTree(commentsByReview[reviewId])
    commentsExpanded[reviewId] = true
  } catch (e) {
    reviewErr.value = e?.response?.data?.detail || e?.message || '回复失败'
  }
}

onMounted(async () => {
  updateTocCols()
  window.addEventListener('resize', updateTocCols)
  document.addEventListener('pointerdown', onDocumentPointerDown)
  document.addEventListener('click', onDocumentClickCollapseComments)
  await fetchBookPage()
  await scrollToReviewHash()
})

watch(id, async () => {
  await fetchBookPage()
  await scrollToReviewHash()
})

watch(
  () => `${route.hash}|${route.query.comment ?? ''}`,
  () => {
    if (book.value) scrollToReviewHash()
  }
)

function openChapter(ch) {
  if (book.value?.reading_requires_borrow && !book.value?.can_read_chapters) {
    if (!isLoggedIn.value) {
      router.push({ name: 'login', query: { next: route.fullPath } })
      return
    }
    readBlockModalVisible.value = true
    return
  }
  router.push({
    name: 'book-chapter-read',
    params: { id: String(id.value), chapterId: String(ch.id) },
  })
}

function closeReadBlockModal() {
  readBlockModalVisible.value = false
}

function openBorrowModal() {
  if (borrowDisabled.value) return
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
    showToast(`借阅成功，归还时间：${formatDateTime(data.due_at)}`)
    if (book.value) {
      book.value.available_copies = Math.max(0, book.value.available_copies - 1)
      book.value.has_my_active_borrow = true
    }
    borrowModalVisible.value = false
    try {
      const { data: bd } = await getBook(id.value)
      book.value = bd
    } catch {
      /* 忽略 */
    }
    await loadReviews()
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
  reviewDeleteModalVisible.value = false
  window.removeEventListener('resize', updateTocCols)
  document.removeEventListener('pointerdown', onDocumentPointerDown)
  document.removeEventListener('click', onDocumentClickCollapseComments)
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

function reviewPayload() {
  const r = reviewRatingStars.value
  const rating = r == null || r === '' ? null : Number(r)
  return { rating, content: reviewContent.value ?? '' }
}

/** 点第 n 颗星设分为 n；若再次点击当前星数则视为清除评分 */
function setReviewStarRating(n) {
  if (reviewSubmitting.value) return
  const next = reviewRatingStars.value === n ? null : n
  reviewRatingStars.value = next
}

function clearReviewRating() {
  if (reviewSubmitting.value) return
  reviewRatingStars.value = null
}

function reviewUserInitial(name) {
  const s = String(name || '').trim()
  return s ? s.charAt(0).toUpperCase() : '?'
}

function canDeleteReviewRow(r) {
  const u = user.value
  if (!u?.id) return false
  if (Number(u.id) === Number(r.user)) return true
  if (u.is_librarian) return true
  return false
}

function openDeleteReviewFromRow(r) {
  if (!user.value) return
  if (Number(user.value.id) === Number(r.user)) {
    openReviewDeleteModalMine()
  } else if (user.value.is_librarian) {
    openReviewDeleteModalStaff(r.id)
  }
}

function scrollToMyReview() {
  const rid = myReview.value?.id
  if (!rid) return
  nextTick(() => {
    const el = document.getElementById(`bd-rev-item-${rid}`)
    el?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  })
}

function toggleReviewCompose() {
  if (!book.value?.review_eligible || myReview.value) return
  reviewComposeOpen.value = !reviewComposeOpen.value
  if (reviewComposeOpen.value) {
    nextTick(() => {
      document.getElementById('bd-rev-compose')?.scrollIntoView({
        behavior: 'smooth',
        block: 'nearest',
      })
    })
  }
}

async function submitReview() {
  reviewErr.value = ''
  if (!isLoggedIn.value) {
    reviewErr.value = '请先登录。'
    return
  }
  if (myReview.value?.id) {
    reviewErr.value = '书评发布后不可修改，请先删除后再发表。'
    return
  }
  reviewSubmitting.value = true
  try {
    const payload = reviewPayload()
    await createBookReview(id.value, payload)
    reviewComposeOpen.value = false
    const { data: bd } = await getBook(id.value)
    book.value = bd
    await loadReviews()
  } catch (e) {
    const d = e?.response?.data
    reviewErr.value =
      d?.detail ||
      d?.non_field_errors?.[0] ||
      Object.values(d || {})[0]?.[0] ||
      e?.message ||
      '提交失败'
  } finally {
    reviewSubmitting.value = false
  }
}

function openReviewDeleteModalMine() {
  reviewDeleteMode.value = 'mine'
  staffDeleteReviewId.value = null
  reviewDeleteModalVisible.value = true
}

function openReviewDeleteModalStaff(reviewId) {
  if (!user.value?.is_librarian) return
  reviewDeleteMode.value = 'staff'
  staffDeleteReviewId.value = reviewId
  reviewDeleteModalVisible.value = true
}

function closeReviewDeleteModal() {
  if (reviewDeleteLoading.value) return
  reviewDeleteModalVisible.value = false
}

async function confirmReviewDelete() {
  reviewDeleteLoading.value = true
  try {
    if (reviewDeleteMode.value === 'mine') {
      reviewErr.value = ''
      await deleteMyBookReview(id.value)
      const { data: bd } = await getBook(id.value)
      book.value = bd
      await loadReviews()
      reviewDeleteModalVisible.value = false
    } else {
      reviewsErr.value = ''
      await deleteBookReviewAsLibrarian(id.value, staffDeleteReviewId.value)
      await loadReviews()
      const { data: bd } = await getBook(id.value)
      book.value = bd
      reviewDeleteModalVisible.value = false
    }
  } catch (e) {
    const msg = e?.response?.data?.detail || e?.message || '删除失败'
    if (reviewDeleteMode.value === 'mine') {
      reviewErr.value = msg
    } else {
      reviewsErr.value = msg
    }
  } finally {
    reviewDeleteLoading.value = false
  }
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
          <button
            type="button"
            :disabled="borrowDisabled || borrowLoading"
            @click="openBorrowModal"
          >
            借阅
          </button>
          <span v-if="book.available_copies < 1" class="muted">（无在架册）</span>
          <span
            v-else-if="book.has_my_active_borrow"
            class="muted"
          >（您已借阅本书）</span>
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
      <p
        v-if="book?.reading_requires_borrow && !book?.can_read_chapters"
        class="muted bd__toc-gate"
      >
        <template v-if="!isLoggedIn">
          阅读正文需先 <router-link to="/login">登录</router-link> 并借阅本书。
        </template>
        <!-- <template v-else>请先点击上方「借阅」成功；须在「在借」期间方可阅读章节正文。</template> -->
      </p>
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

    <section class="bd__reviews" aria-labelledby="bd-rev-h">
      <div class="bd__reviews-head-row">
        <h2 id="bd-rev-h" class="bd__reviews-h">读者书评</h2>
        <div class="bd__reviews-head-actions">
          <button
            v-if="isLoggedIn && book.review_eligible && !myReview"
            type="button"
            class="bd__reviews-head-btn"
            :class="{ 'bd__reviews-head-btn--active': reviewComposeOpen }"
            data-bd-rev-compose-toggle
            @click="toggleReviewCompose"
          >
            {{ reviewComposeOpen ? '收起撰写' : '发表书评' }}
          </button>
          <button
            v-if="isLoggedIn && myReview"
            type="button"
            class="bd__reviews-head-btn bd__reviews-head-btn--ghost"
            @click="scrollToMyReview"
          >
            我的书评
          </button>
        </div>
      </div>
      <p v-if="reviewErr" class="err bd__reviews-msg">{{ reviewErr }}</p>
      <p v-if="reviewsLoading" class="muted bd__reviews-msg">书评加载中…</p>
      <template v-else>
        <p v-if="reviewsErr" class="err bd__reviews-msg">{{ reviewsErr }}</p>
        <div v-if="reviews.length" class="bd__rev-list-scroll">
          <ul class="bd__rev-list">
          <li
            v-for="r in reviews"
            :id="'bd-rev-item-' + r.id"
            :key="r.id"
            class="bd__rev-item"
          >
            <div class="bd__rev-head">
              <div class="bd__rev-avatar-wrap">
                <img
                  v-if="r.user_avatar"
                  :src="r.user_avatar"
                  alt=""
                  class="bd__rev-avatar-img"
                  width="40"
                  height="40"
                />
                <div
                  v-else
                  class="bd__rev-avatar-ph"
                  aria-hidden="true"
                >
                  {{ reviewUserInitial(r.user_username) }}
                </div>
              </div>
              <div class="bd__rev-meta-wrap">
                <div class="bd__rev-meta">
                  <span class="bd__rev-user">{{ r.user_username }}</span>
                  <span v-if="r.rating" class="bd__rev-stars" aria-hidden="true">{{
                    starsText(r.rating)
                  }}</span>
                  <button
                    v-if="canDeleteReviewRow(r)"
                    type="button"
                    class="bd__rev-mod-del"
                    @click="openDeleteReviewFromRow(r)"
                  >
                    删除
                  </button>
                </div>
              </div>
            </div>
            <div class="bd__rev-body-row">
              <p v-if="r.content" class="bd__rev-body">{{ r.content }}</p>
              <p v-else-if="r.rating" class="bd__rev-body muted">（仅评分）</p>
            </div>
            <div class="bd__rev-actions-row">
              <div class="bd__rev-actions-row__left">
                <span class="bd__rev-time">{{ formatDateTime(r.created_at) }}</span>
                <button
                  type="button"
                  class="bd__rev-reply-link--inline bd__rev-reply-trigger"
                  @click="onReplyToBookReview(r)"
                >
                  回复
                </button>
              </div>
              <div class="bd__rev-actions-row__right">
                <button
                  type="button"
                  class="bd__rev-act"
                  :class="{ 'bd__rev-act--liked': r.liked_by_me }"
                  :aria-pressed="!!r.liked_by_me"
                  aria-label="点赞"
                  @click="onToggleLike(r)"
                >
                  <svg
                    class="bd__rev-ico bd__rev-ico-heart"
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
                  <span class="bd__rev-act-num">{{ r.like_count ?? 0 }}</span>
                </button>
                <button
                  type="button"
                  class="bd__rev-act bd__rev-act--ghost bd__rev-reply-trigger bd__rev-cmt-toggle"
                  aria-label="查看评论"
                  @click="onReviewCommentIconClick(r)"
                >
                  <svg
                    class="bd__rev-ico bd__rev-ico-chat"
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
                  <span class="bd__rev-act-num">{{ r.comment_count ?? 0 }}</span>
                </button>
              </div>
            </div>
            <div
              v-if="commentsExpanded[r.id]"
              class="bd__rev-comments"
              @click.stop
            >
              <p v-if="commentsLoading[r.id]" class="muted bd__rev-cmt-hint">评论加载中…</p>
              <template v-else>
                <ReviewCommentItem
                  v-for="c in visibleTopThreads(r.id)"
                  :key="c.id"
                  :depth="0"
                  :node="c"
                  :book-id="id"
                  :review-id="r.id"
                  :reply-draft="replyDraft"
                  :replying-to-id="replyingToComment[r.id] ?? null"
                  :current-user-id="user?.id ?? null"
                  :is-logged-in="isLoggedIn"
                  :is-librarian="isLibrarian()"
                  @like="(n) => onCommentLike(n, r.id)"
                  @toggle-reply="(n) => toggleCommentReplyRow(r.id, n)"
                  @delete="(n) => deleteCommentRow(r.id, n)"
                  @update-draft="onCommentReplyDraft"
                  @submit-reply="submitReply"
                />
                <button
                  v-if="hasMoreTopThreads(r.id)"
                  type="button"
                  class="bd__rev-more-cmt"
                  @click="showMoreTopThreads(r.id)"
                >
                  查看更多
                </button>
                <p v-if="!isLoggedIn" class="muted bd__rev-cmt-hint">
                  <router-link to="/login">登录</router-link> 后可评论
                </p>
              </template>
            </div>
            <div
              v-if="isLoggedIn && topReplyOpen[r.id]"
              class="bd__rev-cmt-compose"
              data-bd-reply-ui
              @click.stop
            >
              <div class="bd__rev-cmt-compose__field">
                <span class="bd__rev-cmt-prefix" aria-hidden="true">回复 {{ r.user_username }}：</span>
                <input
                  :id="'bd-rev-top-cmt-' + r.id"
                  :value="commentDraftTop[r.id] || ''"
                  type="text"
                  class="bd__rev-cmt-input"
                  maxlength="2000"
                  placeholder="输入内容…"
                  @input="commentDraftTop[r.id] = $event.target.value"
                  @keydown.enter.prevent="submitTopComment(r.id)"
                />
              </div>
              <button
                type="button"
                class="bd__rev-cmt-send"
                @click="submitTopComment(r.id)"
              >
                发送
              </button>
            </div>
          </li>
          </ul>
        </div>
        <p v-else class="bd__reviews-empty muted">暂无书评，欢迎借阅后发表第一条。</p>
      </template>

      <div
        v-if="reviewComposeOpen && isLoggedIn && book.review_eligible && !myReview"
        id="bd-rev-compose"
        class="bd__rev-form-wrap"
      >
        <h3 class="bd__rev-form-title">撰写书评</h3>
        <p class="muted bd__rev-form-tip">发表后不可修改，仅可删除后重新发表。</p>
        <div class="bd__rev-form-row bd__rev-form-row--stars">
          <span id="bd-rev-rating-lbl" class="bd__rev-label">评分</span>
          <div
            class="bd__rev-stars-input"
            role="group"
            aria-labelledby="bd-rev-rating-lbl"
          >
            <button
              v-for="n in 5"
              :key="n"
              type="button"
              class="bd__rev-star-btn"
              :class="{ 'bd__rev-star-btn--on': reviewRatingStars != null && reviewRatingStars >= n }"
              :aria-label="`评分 ${n} 星`"
              :disabled="reviewSubmitting"
              @click="setReviewStarRating(n)"
            >
              ★
            </button>
            <!-- <button
              type="button"
              class="bd__rev-rating-clear"
              :disabled="reviewSubmitting || reviewRatingStars == null"
              @click="clearReviewRating"
            >
              清除评分
            </button> -->
          </div>
        </div>
        <div class="bd__rev-form-row bd__rev-form-row--textarea-btn">
          <label class="bd__rev-label" for="bd-rev-content">正文</label>
          <div class="bd__rev-textarea-col">
            <textarea
              id="bd-rev-content"
              v-model="reviewContent"
              class="bd__rev-textarea"
              rows="4"
              maxlength="5000"
              placeholder="写下读后感（可与星级择一或同时填写）"
              :disabled="reviewSubmitting"
            />
            <div class="bd__rev-submit-row">
              <button
                type="button"
                class="bd-btn bd-btn--primary bd__rev-submit-btn"
                :disabled="reviewSubmitting"
                @click="submitReview"
              >
                {{ reviewSubmitting ? '提交中…' : '发表书评' }}
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- <p v-else-if="isLoggedIn && !book.review_eligible" class="bd__rev-hint muted">
        借阅过本书后即可撰写书评（归还后仍可保留书评权限）。
      </p> -->
      <!-- <p v-else-if="!isLoggedIn" class="bd__rev-hint muted">
        <router-link to="/login">登录</router-link>
        后可查看自己是否具备书评资格（须曾借阅该书）。
      </p> -->
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

    <Teleport to="body">
      <Transition name="bd-modal">
        <div
          v-if="readBlockModalVisible"
          class="bd-modal-mask bd-modal-mask--read-block"
        >
          <div
            class="bd-modal-panel bd-modal-panel--confirm"
            role="dialog"
            aria-modal="true"
            aria-labelledby="bd-read-block-title"
          >
            <h3 id="bd-read-block-title" class="bd-modal-title">暂时无法阅读章节正文</h3>
            <p class="bd-modal-alert-text">
              须借阅本书并保持「在借」状态，方可阅读正文。
            </p>
            <div class="bd-modal-actions bd-modal-actions--single">
              <button type="button" class="bd-btn bd-btn--primary" @click="closeReadBlockModal">
                知道了
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <Teleport to="body">
      <Transition name="bd-modal">
        <div
          v-if="reviewDeleteModalVisible"
          class="bd-modal-mask bd-modal-mask--confirm"
          @click.self="closeReviewDeleteModal"
        >
          <div
            class="bd-modal-panel bd-modal-panel--confirm"
            role="dialog"
            aria-modal="true"
            aria-labelledby="bd-rev-del-title"
          >
            <p id="bd-rev-del-title" class="bd-modal-confirm-text">
              {{ reviewDeleteMessage }}
            </p>
            <div class="bd-modal-actions">
              <button
                type="button"
                class="bd-btn bd-btn--ghost"
                :disabled="reviewDeleteLoading"
                @click="closeReviewDeleteModal"
              >
                取消
              </button>
              <button
                type="button"
                class="bd-btn bd-btn--primary"
                :disabled="reviewDeleteLoading"
                @click="confirmReviewDelete"
              >
                {{ reviewDeleteLoading ? '删除中…' : '确定' }}
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
.bd__toc-gate {
  margin: 0 0 0.5rem;
  font-size: 0.9rem;
  line-height: 1.5;
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
  align-content: center;
  padding: 16px;
  z-index: 1200;
}
.bd-modal-mask--confirm {
  z-index: 1210;
}
.bd-modal-mask--read-block {
  z-index: 1220;
}
.bd-modal-alert-text {
  margin: 0 0 6px;
  text-align: center;
  font-size: 0.95rem;
  line-height: 1.6;
  color: #b91c1c;
}
.bd-modal-actions--single {
  justify-content: center;
}
.bd-modal-panel {
  width: min(520px, 100%);
  background: #fffaf2;
  border: 1px solid #e6d8c1;
  border-radius: 14px;
  padding: 16px;
  box-shadow: 0 18px 40px -12px rgba(15, 23, 42, 0.45);
  margin: auto;
}
.bd-modal-panel--confirm {
  width: min(400px, calc(100vw - 32px));
  padding: 20px 18px 18px;
}
.bd-modal-confirm-text {
  margin: 0 0 4px;
  text-align: center;
  font-size: 0.95rem;
  line-height: 1.55;
  color: #334155;
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
.bd__reviews {
  margin-top: 1.25rem;
  padding: 0.85rem 1rem 1rem 1.55rem;
  background: #fffefb;
  border: 1px solid #e8dfd0;
  border-radius: 14px;
  box-shadow: 0 4px 18px -8px rgba(15, 23, 42, 0.08);
}
.bd__reviews-head-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 0.6rem;
}
.bd__reviews-h {
  font-size: 1rem;
  font-weight: 800;
  margin: 0;
  flex: 1;
  min-width: 0;
  color: #1a1a2e;
}
.bd__reviews-head-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 0.45rem;
  flex-shrink: 0;
}
.bd__reviews-head-btn {
  padding: 0.38rem 0.85rem;
  font-size: 0.86rem;
  font-weight: 600;
  border-radius: 10px;
  cursor: pointer;
  border: 1px solid #b99262;
  background: linear-gradient(135deg, #d7b17b, #c29258);
  color: #fffdf8;
}
.bd__reviews-head-btn:hover {
  background: linear-gradient(135deg, #dcb983, #c99a61);
}
.bd__reviews-head-btn--active {
  border-color: #8d6b43;
  box-shadow: inset 0 1px 3px rgba(15, 23, 42, 0.15);
}
.bd__reviews-head-btn--ghost {
  border: 1px solid #d9cdb9;
  background: #f5ecdf;
  color: #5b4636;
}
.bd__reviews-head-btn--ghost:hover {
  background: #efe3d2;
}
.bd__reviews-msg {
  margin: 0 0 0.5rem;
  font-size: 0.92rem;
}
.bd__reviews-empty {
  margin: 0 0 0.85rem;
  font-size: 0.92rem;
}
.bd__rev-list-scroll {
  max-height: min(288px, 44vh);
  overflow-y: auto;
  overflow-x: hidden;
  scroll-behavior: smooth;
  margin: 0 0 1rem;
  padding: 2px 6px 2px 2px;
  border-radius: 10px;
  outline: 1px solid #efe6d8;
  outline-offset: 0;
  background: #fffdf9;
}
.bd__rev-list-scroll .bd__rev-list {
  margin-bottom: 0;
}
.bd__rev-list {
  list-style: none;
  margin: 0 0 1rem;
  padding: 0;
}
.bd__rev-item {
  --bd-rev-avatar-size: 40px;
  --bd-rev-gap: 0.65rem;
  padding: 0.65rem 0;
  border-bottom: 1px dashed #d4ccc1;
}
.bd__rev-item:last-child {
  border-bottom: none;
}
.bd__rev-head {
  display: flex;
  align-items: center;
  gap: var(--bd-rev-gap);
}
.bd__rev-avatar-wrap {
  flex-shrink: 0;
}
.bd__rev-meta-wrap {
  flex: 1;
  min-width: 0;
}
.bd__rev-avatar-img {
  display: block;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  object-fit: cover;
  border: 1px solid #e8dfd0;
  background: #f8fafc;
}
.bd__rev-avatar-ph {
  width: 40px;
  height: 40px;
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
.bd__rev-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.35rem 0.75rem;
  font-size: 0.88rem;
  color: #475569;
}
.bd__rev-user {
  font-weight: 700;
  color: #1e293b;
}
.bd__rev-stars {
  letter-spacing: 0.06em;
  color: #ea580c;
}
.bd__rev-time {
  font-size: 0.82rem;
  color: #94a3b8;
}
.bd__rev-mod-del {
  margin-left: auto;
  padding: 0.15rem 0.5rem;
  font-size: 0.8rem;
  border-radius: 6px;
  border: 1px solid #fecaca;
  background: #fff1f2;
  color: #b91c1c;
  cursor: pointer;
}
.bd__rev-mod-del:hover {
  background: #ffe4e6;
}
.bd__rev-body-row {
  margin-top: 0.45rem;
  padding-left: calc(var(--bd-rev-avatar-size) + var(--bd-rev-gap));
}
.bd__rev-actions-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem 0.85rem;
  margin-top: 0.28rem;
  padding-left: calc(var(--bd-rev-avatar-size) + var(--bd-rev-gap));
  min-height: 1.65rem;
}
.bd__rev-actions-row__left {
  display: inline-flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 0 0.65em;
  min-width: 0;
  font-size: 0.82rem;
  line-height: 1.45;
  color: #64748b;
}
.bd__rev-actions-row__left .bd__rev-time {
  color: #94a3b8;
  line-height: 1.45;
}
.bd__rev-actions-row__right {
  display: inline-flex;
  align-items: center;
  gap: 0.55rem;
  flex-shrink: 0;
}
.bd__rev-body {
  margin: 0;
  font-size: 0.9rem;
  line-height: 1.6;
  color: #334155;
  white-space: pre-wrap;
  word-break: break-word;
}
.bd__rev-body + .bd__rev-body {
  margin-top: 0.35rem;
}
.bd__rev-form-tip {
  margin: 0 0 0.5rem;
  font-size: 0.82rem;
}
.bd__rev-form-wrap {
  margin-top: 0.25rem;
  padding-top: 0.75rem;
  border-top: 1px dashed #d4ccc1;
}
.bd__rev-form-title {
  font-size: 0.92rem;
  font-weight: 800;
  margin: 0 0 0.5rem;
  color: #1a1a2e;
}
.bd__rev-form-row {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem 0.75rem;
  margin-bottom: 0.55rem;
}
.bd__rev-form-row--stars {
  align-items: center;
  margin-bottom: 0.65rem;
}
.bd__rev-form-row--textarea-btn {
  align-items: flex-start;
  margin-bottom: 0;
}
.bd__rev-label {
  width: 48px;
  flex-shrink: 0;
  padding-top: 0.35rem;
  font-size: 0.86rem;
  color: #64748b;
}
.bd__rev-form-row--stars .bd__rev-label {
  padding-top: 0;
}
.bd__rev-stars-input {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.1rem 0.25rem;
}
.bd__rev-star-btn {
  margin: 0;
  padding: 0.15rem 0.12rem;
  border: none;
  border-radius: 6px;
  background: transparent;
  font-size: 1.45rem;
  line-height: 1;
  color: #cbd5e1;
  cursor: pointer;
  transition: color 0.15s ease, transform 0.12s ease;
}
.bd__rev-star-btn--on {
  color: #ea580c;
}
.bd__rev-star-btn:hover:not(:disabled) {
  transform: scale(1.06);
  color: #fb923c;
}
.bd__rev-star-btn:disabled {
  opacity: 0.65;
  cursor: default;
  transform: none;
}
.bd__rev-star-btn:focus-visible {
  outline: 2px solid rgba(234, 88, 12, 0.45);
  outline-offset: 2px;
}
.bd__rev-rating-clear {
  margin-left: 0.4rem;
  padding: 0.2rem 0.5rem;
  font-size: 0.8rem;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
  color: #64748b;
  cursor: pointer;
}
.bd__rev-rating-clear:hover:not(:disabled) {
  background: #f1f5f9;
  color: #475569;
}
.bd__rev-rating-clear:disabled {
  opacity: 0.45;
  cursor: default;
}
.bd__rev-textarea-col {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 0.5rem;
}
.bd__rev-submit-row {
  display: flex;
  justify-content: flex-start;
  align-items: center;
}
.bd__rev-submit-btn {
  white-space: nowrap;
}
.bd__rev-textarea {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid #d7c8b2;
  border-radius: 8px;
  padding: 0.45rem 0.55rem;
  font-size: 0.88rem;
  line-height: 1.5;
  resize: vertical;
  min-height: 104px;
  background: #fffdf8;
}
.bd__rev-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 0.35rem;
}
.bd__rev-hint {
  margin: 0.5rem 0 0;
  font-size: 0.9rem;
}
.bd__rev-act {
  display: inline-flex;
  align-items: center;
  gap: 0.22rem;
  padding: 0.14rem 0.28rem;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: #64748b;
  cursor: pointer;
  font-size: 0.84rem;
}
.bd__rev-act:hover {
  color: #334155;
  background: rgba(148, 163, 184, 0.14);
}
.bd__rev-act--ghost {
  background: transparent;
}
.bd__rev-act--liked {
  color: #ea580c;
}
.bd__rev-act--liked .bd__rev-ico-heart {
  fill: #ea580c;
  stroke: #ea580c;
}
.bd__rev-ico {
  width: 1.12rem;
  height: 1.12rem;
  flex-shrink: 0;
}
.bd__rev-act-num {
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: #64748b;
}
.bd__rev-act--liked .bd__rev-act-num {
  color: #ea580c;
}
.bd__rev-reply-link--inline {
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
.bd__rev-reply-link--inline:hover {
  color: #64748b;
  text-decoration: underline;
  text-underline-offset: 0.15em;
}
.bd__rev-more-cmt {
  display: block;
  width: 100%;
  margin: 0.35rem 0 0.15rem;
  padding: 0.28rem;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: #c29258;
  font-size: 0.84rem;
  font-weight: 600;
  cursor: pointer;
  text-align: center;
}
.bd__rev-more-cmt:hover {
  background: rgba(194, 146, 88, 0.12);
}
.bd__rev-comments {
  margin-top: 0.5rem;
  padding: 0.55rem 0.65rem 0.65rem;
  margin-left: calc(var(--bd-rev-avatar-size) + var(--bd-rev-gap));
  border-radius: 10px;
  border: 1px solid #efe6d8;
  background: #fffdf9;
}
.bd__rev-cmt-hint {
  margin: 0;
  font-size: 0.84rem;
}
.bd__rev-cmt {
  padding: 0.4rem 0;
  border-bottom: 1px dashed #e8dfd0;
}
.bd__rev-cmt:last-of-type {
  border-bottom: none;
}
.bd__rev-cmt-main,
.bd__rev-cmt-rep {
  font-size: 0.86rem;
  line-height: 1.5;
  color: #334155;
}
.bd__rev-cmt-rep {
  margin: 0.25rem 0 0 0.85rem;
  padding-left: 0.5rem;
  border-left: 2px solid #e2e8f0;
}
.bd__rev-cmt-user {
  font-weight: 700;
  color: #1e293b;
  margin-right: 0.35rem;
}
.bd__rev-reply-row {
  display: flex;
  gap: 0.35rem;
  margin-top: 0.35rem;
  align-items: center;
}
.bd__rev-reply-input {
  flex: 1;
  min-width: 0;
  border: 1px solid #d7c8b2;
  border-radius: 8px;
  padding: 0.3rem 0.45rem;
  font-size: 0.82rem;
}
.bd__rev-reply-send {
  flex-shrink: 0;
  padding: 0.28rem 0.5rem;
  font-size: 0.78rem;
  border-radius: 8px;
  border: 1px solid #d9cdb9;
  background: #f5ecdf;
  cursor: pointer;
}
.bd__rev-cmt-compose {
  display: flex;
  gap: 0.35rem;
  margin-top: 0.45rem;
  margin-left: calc(var(--bd-rev-avatar-size) + var(--bd-rev-gap));
  align-items: center;
}
.bd__rev-cmt-compose__field {
  display: flex;
  align-items: center;
  flex: 1;
  min-width: 0;
  gap: 0.2rem;
}
.bd__rev-cmt-prefix {
  flex-shrink: 0;
  font-size: 0.86rem;
  line-height: 1.45;
  color: #94a3b8;
  user-select: none;
  white-space: nowrap;
}
.bd__rev-cmt-input {
  flex: 1;
  min-width: 0;
  border: 1px solid #d7c8b2;
  border-radius: 8px;
  padding: 0.35rem 0.5rem;
  font-size: 0.86rem;
  color: #334155;
  caret-color: #64748b;
}
.bd__rev-cmt-input::placeholder {
  color: #94a3b8;
  opacity: 0.9;
}
.bd__rev-cmt-send {
  flex-shrink: 0;
  padding: 0.35rem 0.65rem;
  font-size: 0.82rem;
  border-radius: 8px;
  border: 1px solid #b99262;
  background: linear-gradient(135deg, #d7b17b, #c29258);
  color: #fffdf8;
  cursor: pointer;
}
</style>
