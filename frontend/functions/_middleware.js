/**
 * Cloudflare Pages Function: прокси к серверу Django.
 *
 * Cloudflare Pages хранит только собранный фронтенд (HTML/JS/CSS) и не умеет запускать Django.
 * Этот код выполняется на Cloudflare для каждого запроса: адреса /api/* и /media/* он пересылает на сервер
 * (Render), а всё остальное отдаёт как обычно. Поэтому во фронтенде адреса остаются относительными (/api/...),
 * как при разработке с прокси Vite, а настраивать CORS не нужно — для браузера это один и тот же сайт.
 *
 * Адрес сервера можно поменять без правки кода: переменная BACKEND_URL в настройках проекта Cloudflare Pages.
 */
const DEFAULT_BACKEND = 'https://marketplace-or-smt-idk.onrender.com'
const PROXIED = ['/api/', '/media/']

export async function onRequest({ request, env, next }) {
  const url = new URL(request.url)
  if (!PROXIED.some((prefix) => url.pathname.startsWith(prefix))) {
    return next() // страницы и файлы фронтенда — без изменений
  }

  const backend = (env.BACKEND_URL || DEFAULT_BACKEND).replace(/\/+$/, '')
  const target = backend + url.pathname + url.search

  const headers = new Headers(request.headers)
  // Django строит ссылки (например, на фото товаров) на адрес фронтенда, а не на внутренний адрес Render
  headers.set('X-Forwarded-Host', url.host)
  headers.set('X-Forwarded-Proto', 'https')

  // Тело пересылаем целиком (JSON или фото товара — до нескольких МБ): так код одинаково работает на Cloudflare и в Node
  const hasBody = !['GET', 'HEAD'].includes(request.method)
  return fetch(target, {
    method: request.method,
    headers,
    body: hasBody ? await request.arrayBuffer() : undefined,
    redirect: 'manual', // перенаправления сервера отдаём браузеру как есть
  })
}
