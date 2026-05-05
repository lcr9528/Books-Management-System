<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

/** 星期日 0 … 星期六 6，每日一句 */
const QUOTES = [
  '书籍是人类进步的阶梯。 —— 高尔基',
  '读一本好书，就是和许多高尚的人谈话。 —— 歌德',
  '书犹药也，善读之可以医愚。 —— 刘向',
  '立身以立学为先，立学以读书为本。 —— 欧阳修',
  '读书破万卷，下笔如有神。 —— 杜甫',
  '书山有路勤为径，学海无涯苦作舟。 —— 韩愈',
  '读书不觉已春深，一寸光阴一寸金。 —— 王贞白',
]

function quoteIndexForToday() {
  return new Date().getDay()
}

const targetQuote = computed(() => QUOTES[quoteIndexForToday()] ?? QUOTES[0])

const displayedQuote = ref('')
let typeTimer = null
let pauseTimer = null

const PAUSE_MS = 3000
const TYPE_MS = 80

const typingComplete = computed(() => {
  const full = targetQuote.value
  return full.length > 0 && displayedQuote.value.length >= full.length
})

function prefersReducedMotion() {
  if (typeof window === 'undefined') return false
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

function clearTypeTimer() {
  if (typeTimer != null) {
    window.clearInterval(typeTimer)
    typeTimer = null
  }
}

function clearPauseTimer() {
  if (pauseTimer != null) {
    window.clearTimeout(pauseTimer)
    pauseTimer = null
  }
}

function clearAllTimers() {
  clearTypeTimer()
  clearPauseTimer()
}

/** 同一句名言：逐字显示 → 完整停留 PAUSE_MS → 清空再从头逐字（循环） */
function runQuoteCycle() {
  clearAllTimers()
  const full = targetQuote.value
  if (prefersReducedMotion()) {
    displayedQuote.value = full
    return
  }
  displayedQuote.value = ''
  let i = 0
  typeTimer = window.setInterval(() => {
    i += 1
    displayedQuote.value = full.slice(0, i)
    if (i >= full.length) {
      clearTypeTimer()
      pauseTimer = window.setTimeout(() => {
        pauseTimer = null
        runQuoteCycle()
      }, PAUSE_MS)
    }
  }, TYPE_MS)
}

onMounted(runQuoteCycle)

onBeforeUnmount(() => {
  clearAllTimers()
})
</script>

<template>
  <div class="home-page">
    <div class="home-center">
      <h1 class="home-welcome">欢迎使用图书管理系统</h1>
      <p class="home-quote" aria-live="polite">
        <span class="home-quote__text">{{ displayedQuote }}</span>
        <span v-show="!typingComplete" class="home-quote__caret" aria-hidden="true" />
      </p>
    </div>
  </div>
</template>

<style scoped>
.home-page {
  width: 100%;
  min-height: calc(100vh - 56px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2rem clamp(1rem, 4vw, 2rem) 3rem;
  background: transparent;
  font-family: 'Segoe UI', 'PingFang SC', system-ui, -apple-system, sans-serif;
}

.home-center {
  text-align: center;
  max-width: min(42rem, 100%);
}

.home-welcome {
  margin: 0 0 1.75rem;
  font-size: clamp(1.95rem, 5.5vw, 2.85rem);
  font-weight: 800;
  letter-spacing: -0.03em;
  line-height: 1.25;
  color: #f0fdf9;
  text-shadow:
    0 1px 2px rgba(0, 35, 30, 0.95),
    0 3px 14px rgba(0, 0, 0, 0.45),
    0 0 22px rgba(255, 255, 255, 0.25);
}

.home-quote {
  margin: 0;
  min-height: 4.5rem;
  font-size: clamp(0.95rem, 2.4vw, 1.08rem);
  line-height: 1.75;
  color: rgba(240, 253, 250, 0.96);
  text-shadow:
    0 1px 2px rgba(0, 35, 30, 0.92),
    0 2px 10px rgba(0, 0, 0, 0.4),
    0 0 16px rgba(255, 255, 255, 0.2);
}

.home-quote__text {
  white-space: pre-wrap;
  word-break: break-word;
}

.home-quote__caret {
  display: inline-block;
  width: 2px;
  height: 1.05em;
  margin-left: 2px;
  vertical-align: -0.12em;
  background: rgba(240, 253, 250, 0.95);
  box-shadow: 0 0 8px rgba(255, 255, 255, 0.5);
  animation: homeCaret 0.95s steps(1) infinite;
}

@keyframes homeCaret {
  0%,
  49% {
    opacity: 1;
  }
  50%,
  100% {
    opacity: 0;
  }
}

@media (prefers-reduced-motion: reduce) {
  .home-quote__caret {
    animation: none;
    opacity: 0.65;
  }
}
</style>
