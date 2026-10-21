/**
 * Единая точка запросов к API.
 *  - подставляет JWT-токен в заголовок Authorization;
 *  - когда access-токен истёк (ответ 401), один раз обновляет его по refresh и повторяет запрос;
 *  - если обновить не удалось — разлогинивает (событие 'auth:logout');
 *  - ошибки сервера превращает в ApiError с понятным текстом.
 */
const TOKENS_KEY = 'marketplace_tokens'

// Токены храним в localStorage: так пользователь остаётся залогиненным после перезагрузки страницы.
export const tokens = {
  get() {
    try { return JSON.parse(localStorage.getItem(TOKENS_KEY)) || null } catch { return null }
  },
  set(value) {
    try { localStorage.setItem(TOKENS_KEY, JSON.stringify(value)) } catch { /* приватный режим */ }
  },
  clear() {
    try { localStorage.removeItem(TOKENS_KEY) } catch { /* приватный режим */ }
  },
}

export class ApiError extends Error {
  constructor(status, data) {
    super(errorText(data) || `Ошибка сервера (${status})`)
    this.status = status
    this.data = data // ошибки по полям формы: { email: ['...'], password: ['...'] }
  }
}

/** Текст ошибки из ответа DRF: {"detail": "..."}, {"поле": ["..."]} или вложенный {"профиль": {"поле": [...]}} */
function errorText(data) {
  if (!data || typeof data !== 'object') return ''
  if (typeof data.detail === 'string') return data.detail
  const first = Object.values(data)[0]
  if (Array.isArray(first)) return String(first[0])
  if (typeof first === 'string') return first
  if (first && typeof first === 'object') return errorText(first) // вложенные поля: {"customer": {"phone": ["..."]}}
  return ''
}

let refreshing = null // один общий запрос обновления, даже если 401 пришло сразу на несколько запросов

async function refreshAccess() {
  const current = tokens.get()
  if (!current?.refresh) return false
  refreshing ??= fetch('/api/auth/refresh/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh: current.refresh }),
  })
    .then(async (response) => {
      if (!response.ok) return false
      const data = await response.json()
      // Сервер выдаёт новый refresh (ротация), старый больше не действует
      tokens.set({ access: data.access, refresh: data.refresh ?? current.refresh })
      return true
    })
    .catch(() => false)
    .finally(() => { refreshing = null })
  return refreshing
}

function buildUrl(path, params) {
  const url = new URL(`/api${path}`, window.location.origin)
  Object.entries(params || {}).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') return
    if (Array.isArray(value)) value.forEach((v) => url.searchParams.append(key, v))
    else url.searchParams.set(key, value)
  })
  return url.pathname + url.search
}

async function request(path, { method = 'GET', body, params, retry = true } = {}) {
  const headers = {}
  const access = tokens.get()?.access
  if (access) headers.Authorization = `Bearer ${access}`
  const isForm = body instanceof FormData
  if (body !== undefined && !isForm) headers['Content-Type'] = 'application/json'

  const response = await fetch(buildUrl(path, params), {
    method,
    headers,
    body: body === undefined ? undefined : isForm ? body : JSON.stringify(body),
  })

  if (response.status === 401 && retry && access) {
    if (await refreshAccess()) return request(path, { method, body, params, retry: false })
    tokens.clear()
    window.dispatchEvent(new Event('auth:logout'))
  }

  const data = response.status === 204 ? null : await response.json().catch(() => null)
  if (!response.ok) throw new ApiError(response.status, data)
  return data
}

/**
 * Скачать файл (CSV-отчёт). Обычная ссылка <a href> не подойдёт: без заголовка Authorization сервер
 * ответит 401. Поэтому качаем запросом с токеном и отдаём браузеру как файл.
 */
async function download(path, params, filename) {
  const send = () => fetch(buildUrl(path, params), { headers: { Authorization: `Bearer ${tokens.get()?.access}` } })
  let response = await send()
  if (response.status === 401 && (await refreshAccess())) response = await send()
  if (!response.ok) throw new ApiError(response.status, await response.json().catch(() => null))
  const url = URL.createObjectURL(await response.blob())
  const link = Object.assign(document.createElement('a'), { href: url, download: filename })
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

export const api = {
  get: (path, params) => request(path, { params }),
  post: (path, body) => request(path, { method: 'POST', body: body ?? {} }),
  patch: (path, body) => request(path, { method: 'PATCH', body }),
  delete: (path) => request(path, { method: 'DELETE' }),
  download,
}
