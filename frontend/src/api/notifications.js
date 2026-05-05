import { client } from './client'

export function listNotifications(params) {
  return client.get('/notifications/', { params })
}

export function getUnreadNotificationCount() {
  return client.get('/notifications/unread-count/')
}

export function markNotificationRead(id) {
  return client.post(`/notifications/${id}/read/`)
}

export function markAllNotificationsRead() {
  return client.post('/notifications/mark-all-read/')
}
