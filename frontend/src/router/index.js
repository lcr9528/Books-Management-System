import { createRouter, createWebHistory } from 'vue-router'
import { refreshUser, user } from '../auth'
import HomeView from '../views/HomeView.vue'
import BookListView from '../views/BookListView.vue'
import BookDetailView from '../views/BookDetailView.vue'
import BookChapterReadView from '../views/BookChapterReadView.vue'
import AuthView from '../views/AuthView.vue'
import ForgotPasswordView from '../views/ForgotPasswordView.vue'
import MyBorrowsView from '../views/MyBorrowsView.vue'
import LibrarianView from '../views/LibrarianView.vue'
import ProfileView from '../views/ProfileView.vue'

const routes = [
  { path: '/', name: 'home', component: HomeView },
  { path: '/books', name: 'books', component: BookListView },
  {
    path: '/books/:id/chapters/:chapterId',
    name: 'book-chapter-read',
    component: BookChapterReadView,
    props: true,
  },
  { path: '/books/:id', name: 'book-detail', component: BookDetailView, props: true },
  { path: '/login', name: 'login', component: AuthView },
  { path: '/register', name: 'register', component: AuthView },
  { path: '/forgot-password', name: 'forgot-password', component: ForgotPasswordView },
  { path: '/me/profile', name: 'profile', component: ProfileView, meta: { requiresAuth: true } },
  { path: '/me/borrows', name: 'my-borrows', component: MyBorrowsView, meta: { requiresAuth: true } },
  { path: '/librarian', name: 'librarian', component: LibrarianView, meta: { requiresAuth: true, librarian: true } },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach(async (to) => {
  await refreshUser()
  if (to.meta?.requiresAuth && !localStorage.getItem('access')) {
    return { name: 'login', query: { next: to.fullPath } }
  }
  if (to.meta?.librarian) {
    if (!user.value?.is_librarian) {
      return { name: 'home' }
    }
  }
  return true
})

export default router
