<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUser, clearSession, refreshUser } from './auth'
import { getUnreadNotificationCount } from './api/notifications'
import AppToast from './components/AppToast.vue'

const navRouter = useRouter()
const route = useRoute()
const { user, isLoggedIn, loading } = useUser()
const unreadCount = ref(0)
let unreadPollTimer = null

const isAuthPage = computed(() => ['login', 'register', 'forgot-password'].includes(route.name))
/** 仅首页套图书馆背景图（顶栏+主体）；登录类页面由各自 .auth-page 铺图 */
const isHomePage = computed(() => route.name === 'home')

const DEFAULT_AVATAR = '/toux.png'
const avatarSrc = computed(() => user.value?.avatar || DEFAULT_AVATAR)

async function pollUnread() {
  if (!localStorage.getItem('access')) {
    unreadCount.value = 0
    return
  }
  try {
    const { data } = await getUnreadNotificationCount()
    unreadCount.value = data?.count ?? 0
  } catch {
    unreadCount.value = 0
  }
}

function onUnreadRefreshEvent() {
  pollUnread()
}

onMounted(() => {
  refreshUser({ force: true })
  pollUnread()
  unreadPollTimer = setInterval(pollUnread, 45000)
  window.addEventListener('app:poll-unread', onUnreadRefreshEvent)
})

onUnmounted(() => {
  window.removeEventListener('app:poll-unread', onUnreadRefreshEvent)
  if (unreadPollTimer) {
    clearInterval(unreadPollTimer)
    unreadPollTimer = null
  }
})

watch(
  () => [route.path, isLoggedIn.value],
  () => {
    pollUnread()
  }
)

function logout() {
  clearSession()
  navRouter.push({ name: 'home' })
}
</script>

<template>
  <div
    class="layout"
    :class="{ 'layout--auth': isAuthPage, 'layout--home-bg': isHomePage }"
  >
    <header
      v-show="!isAuthPage"
      class="header"
      :class="{ 'header--on-photo': isHomePage }"
    >
      <h2 class="brand" @click="navRouter.push({ name: 'home' })">图书管理系统</h2>
      <nav class="header__center" aria-label="主导航">
        <router-link :to="{ name: 'books' }" class="nav-books">图书列表</router-link>
      </nav>
      <nav v-if="!loading" class="header__right">
        <template v-if="isLoggedIn">
          <router-link
            :to="{ name: 'notifications' }"
            class="nav-msg"
            aria-label="消息通知"
          >
            <span class="nav-msg__wrap">
              <img
                class="nav-msg__icon"
                src="/xiaoxi.svg"
                alt=""
                width="22"
                height="22"
              />
              <span
                v-if="unreadCount > 0"
                class="nav-msg__badge"
                aria-hidden="true"
                >{{ unreadCount > 99 ? '99+' : unreadCount }}</span
              >
            </span>
          </router-link>
          <a href="#" @click.prevent="navRouter.push({ name: 'my-borrows' })">我的借阅</a>
          <a v-if="user?.is_librarian" href="#" @click.prevent="navRouter.push({ name: 'librarian' })"
            >管理</a
          >
          <router-link :to="{ name: 'profile' }" class="nav-user">
            <img class="nav-avatar" :src="avatarSrc" alt="" width="32" height="32" />
            <span class="u nav-user__name">{{ user?.username }}</span>
          </router-link>
          <a href="#" @click.prevent="logout">退出</a>
        </template>
        <template v-else>
          <a
            href="#"
            @click.prevent="
              navRouter.push({ name: 'login', query: { next: route.fullPath } })
            "
            >登录</a
          >
        </template>
      </nav>
      <div v-else class="header__right header__right--placeholder" aria-hidden="true" />
    </header>
    <main class="app-main" :class="{ 'app-main--auth': isAuthPage }">
      <router-view />
    </main>
    <AppToast />
  </div>
</template>

<style>
.layout {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: #f7f2e8;
}
/* 仅首页：public/1.png 铺满顶栏与下方内容区 */
.layout--home-bg {
  background: #e2e8f0 url('/1.png') center / cover no-repeat;
  /* fixed 易在路由切换/重绘时触发整页合成层开销；scroll 可减轻「从详情回首页」卡顿 */
  background-attachment: scroll;
}
.layout--auth {
  min-height: 100vh;
  background: transparent;
}
.app-main {
  flex: 1;
  width: 100%;
  min-height: 0;
}
.app-main--auth {
  display: flex;
  flex-direction: column;
  padding: 0;
}
</style>

<style scoped>
.header {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  align-items: center;
  gap: 0.5rem 1rem;
  padding: 0.5rem 1.25rem;
  background: #fffaf2;
  border-bottom: 1px solid #eadfcd;
  box-shadow: 0 1px 0 rgba(15, 23, 42, 0.04);
}

.header__center {
  justify-self: center;
}

.header__right {
  justify-self: end;
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem 0.75rem;
  align-items: center;
  font-size: 0.95rem;
}

.header__right--placeholder {
  min-height: 1.5rem;
}

.nav-books {
  color: #0d9488;
  text-decoration: none;
  font-weight: 600;
  font-size: 0.98rem;
  text-underline-offset: 0.2em;
}

.nav-books:hover {
  color: #0f766e;
  text-decoration: underline;
}

/* 首页压在背景图上：浅色字 + 深色外晕 + 浅色光晕，深浅背景都可辨识（不加顶栏底） */
.header--on-photo {
  background: transparent;
  border-bottom: none;
  box-shadow: none;
}

.brand {
  font-size: 1.1rem;
  font-weight: 700;
  margin: 0;
  color: #0d9488;
  cursor: pointer;
  font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
  letter-spacing: -0.02em;
  justify-self: start;
}
.brand:hover {
  color: #0f766e;
}
.header--on-photo .brand {
  font-size: clamp(1.15rem, 2.6vw, 1.28rem);
  font-weight: 800;
  letter-spacing: -0.03em;
  color: #f0fdf9;
  text-shadow:
    0 1px 1px rgba(0, 35, 30, 0.95),
    0 2px 4px rgba(0, 0, 0, 0.55),
    0 3px 14px rgba(0, 0, 0, 0.45),
    0 0 18px rgba(255, 255, 255, 0.35);
}
.header--on-photo .brand:hover {
  color: #ffffff;
  text-shadow:
    0 1px 1px rgba(0, 35, 30, 0.95),
    0 2px 6px rgba(0, 0, 0, 0.55),
    0 0 22px rgba(255, 255, 255, 0.55);
}
.header__right a {
  color: #0d9488;
  text-decoration: none;
  font-weight: 500;
  text-underline-offset: 0.2em;
}
.header__right a:hover {
  color: #0f766e;
  text-decoration: underline;
}
.header--on-photo .header__right a {
  font-size: 1rem;
  font-weight: 700;
  color: #ecfdf9;
  text-shadow:
    0 1px 1px rgba(0, 35, 30, 0.9),
    0 2px 5px rgba(0, 0, 0, 0.45),
    0 0 14px rgba(255, 255, 255, 0.28);
}
.header--on-photo .header__right a:hover {
  color: #ffffff;
  text-decoration: underline;
  text-shadow:
    0 1px 2px rgba(0, 35, 30, 0.95),
    0 2px 8px rgba(0, 0, 0, 0.45),
    0 0 18px rgba(255, 255, 255, 0.45);
}
.header--on-photo .nav-books {
  font-size: 1rem;
  font-weight: 700;
  color: #ecfdf9;
  text-shadow:
    0 1px 1px rgba(0, 35, 30, 0.9),
    0 2px 5px rgba(0, 0, 0, 0.45),
    0 0 14px rgba(255, 255, 255, 0.28);
}
.header--on-photo .nav-books:hover {
  color: #ffffff;
  text-decoration: underline;
  text-shadow:
    0 1px 2px rgba(0, 35, 30, 0.95),
    0 2px 8px rgba(0, 0, 0, 0.45),
    0 0 18px rgba(255, 255, 255, 0.45);
}
.u {
  color: #374151;
  margin-right: 0.25rem;
  font-weight: 500;
}
.header--on-photo .u {
  font-size: 0.97rem;
  font-weight: 600;
  color: #e8fff9;
  text-shadow:
    0 1px 1px rgba(0, 35, 30, 0.88),
    0 2px 5px rgba(0, 0, 0, 0.42),
    0 0 12px rgba(255, 255, 255, 0.22);
}

.nav-msg {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  text-decoration: none;
  padding: 2px;
}
.nav-msg__wrap {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.nav-msg__icon {
  display: block;
  opacity: 0.92;
}
.nav-msg__badge {
  position: absolute;
  top: -4px;
  right: -8px;
  min-width: 1rem;
  padding: 0 4px;
  height: 16px;
  line-height: 16px;
  font-size: 0.68rem;
  font-weight: 800;
  text-align: center;
  border-radius: 999px;
  background: #dc2626;
  color: #fff;
  box-shadow: 0 0 0 2px #fffaf2;
}
.header--on-photo .nav-msg__badge {
  box-shadow:
    0 0 0 2px rgba(15, 23, 42, 0.35),
    0 1px 4px rgba(0, 0, 0, 0.45);
}
.header--on-photo .nav-msg__icon {
  filter: brightness(0) invert(1);
  opacity: 0.95;
}
.nav-user {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  text-decoration: none;
}
.nav-user:hover .nav-user__name {
  text-decoration: underline;
}
.nav-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  object-fit: cover;
  flex-shrink: 0;
  border: none;
  display: block;
}
.nav-user .u {
  margin-right: 0;
}
</style>
