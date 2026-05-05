import { client } from './client'

export function register(data) {
  return client.post('/auth/register/', data)
}

/** 注册前查重，可传 { username }、{ email } 或两者 */
export function checkRegisterAvailability(payload) {
  return client.post('/auth/register/check/', payload)
}

export function obtainToken(username, password) {
  return client.post('/auth/token/', { username, password })
}

export function fetchMe() {
  return client.get('/auth/me/')
}

/** PATCH /auth/me/，传 FormData 可上传头像 */
export function updateMe(data) {
  return client.patch('/auth/me/', data)
}

/** 发送密码重置 6 位数字验证码到邮箱 */
export function requestPasswordReset(email) {
  return client.post('/auth/password-reset/', { email })
}

/** 用验证码重设密码 */
export function confirmPasswordReset(payload) {
  return client.post('/auth/password-reset/confirm/', payload)
}
