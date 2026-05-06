import { client } from './client'

export function listBooks(params) {
  return client.get('/books/', { params })
}

export function getBook(id) {
  return client.get(`/books/${id}/`)
}

export function listBookChapters(bookId) {
  return client.get(`/books/${bookId}/chapters/`)
}

export function getBookChapter(bookId, chapterId) {
  return client.get(`/books/${bookId}/chapters/${chapterId}/`)
}

export function createCategory(name) {
  return client.post('/categories/', { name })
}

export function listCategories() {
  return client.get('/categories/')
}

export function createBook(data) {
  return client.post('/books/', data)
}

export function updateBook(id, data) {
  return client.patch(`/books/${id}/`, data)
}

export function listBorrows(params) {
  return client.get('/borrows/', { params })
}

export function borrowBook(bookId, payload = {}) {
  return client.post('/borrows/', { book: bookId, ...payload })
}

export function returnBook(borrowId) {
  return client.post(`/borrows/${borrowId}/return/`, {})
}

export function renewBorrow(borrowId, payload = {}) {
  return client.post(`/borrows/${borrowId}/renew/`, payload)
}

/** 书评：须曾借阅该书；每用户每书一条；发布后不可改，仅可删除后再发 */
export function listBookReviews(bookId, params) {
  return client.get(`/books/${bookId}/reviews/`, { params })
}

export function getMyBookReview(bookId) {
  return client.get(`/books/${bookId}/reviews/mine/`)
}

export function createBookReview(bookId, data) {
  return client.post(`/books/${bookId}/reviews/`, data)
}

export function deleteMyBookReview(bookId) {
  return client.delete(`/books/${bookId}/reviews/mine/`)
}

/** 仅图书管理员 */
export function deleteBookReviewAsLibrarian(bookId, reviewId) {
  return client.delete(`/books/${bookId}/reviews/${reviewId}/`)
}

export function toggleBookReviewLike(bookId, reviewId) {
  return client.post(`/books/${bookId}/reviews/${reviewId}/like/`)
}

export function listBookReviewComments(bookId, reviewId) {
  return client.get(`/books/${bookId}/reviews/${reviewId}/comments/`)
}

export function createBookReviewComment(bookId, reviewId, data) {
  return client.post(`/books/${bookId}/reviews/${reviewId}/comments/`, data)
}

export function toggleBookReviewCommentLike(bookId, reviewId, commentId) {
  return client.post(
    `/books/${bookId}/reviews/${reviewId}/comments/${commentId}/like/`
  )
}

export function deleteBookReviewComment(bookId, reviewId, commentId) {
  return client.delete(
    `/books/${bookId}/reviews/${reviewId}/comments/${commentId}/`
  )
}

/** GET 公开；PATCH 仅图书管理员 */
export function getSiteSettings() {
  return client.get('/site-settings/')
}

export function patchSiteSettings(data) {
  return client.patch('/site-settings/', data)
}
