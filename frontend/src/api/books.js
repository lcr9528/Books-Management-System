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
