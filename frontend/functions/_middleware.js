/**
 * Cloudflare Pages Function: прокси к серверу Django и карта сайта для поисковиков.
 *
 * Cloudflare Pages хранит только собранный фронтенд (HTML/JS/CSS) и не умеет запускать Django.
 * Этот код выполняется на Cloudflare для каждого запроса:
 *   /api/*, /media/* — пересылаются на сервер (Render); во фронтенде адреса остаются относительными (/api/...),
 *                      как при разработке с прокси Vite, а CORS не нужен — для браузера это один и тот же сайт;
 *   /sitemap.xml     — карта сайта: главная, категории и все товары (список берётся из API);
 *   остальное        — файлы фронтенда без изменений.
 *
 * Адрес сервера можно поменять без правки кода: переменная BACKEND_URL в настройках проекта Cloudflare Pages.
 */
const DEFAULT_BACKEND = 'https://marketplace-or-smt-idk.onrender.com'
const PROXIED = ['/api/', '/media/']
const SITEMAP_TIMEOUT_MS = 8000 // сервер на бесплатном тарифе «просыпается» до минуты — столько поисковик ждать не станет
const SITEMAP_MAX_PAGES = 50 // страниц API по 20 товаров — до 1000 товаров в карте

// Файлы подтверждения владения сайтом (Google Search Console). Отдаются отсюда, а не из public/:
// Cloudflare Pages перенаправляет адреса *.html на адрес без .html, а проверка Google ждёт файл ровно по своему адресу
const VERIFICATION_FILES = {
  '/googlec461adada234c760.html': 'google-site-verification: googlec461adada234c760.html',
}

export async function onRequest({ request, env, next }) {
  const url = new URL(request.url)
  const backend = (env.BACKEND_URL || DEFAULT_BACKEND).replace(/\/+$/, '')

  if (VERIFICATION_FILES[url.pathname]) {
    return new Response(VERIFICATION_FILES[url.pathname], { headers: { 'Content-Type': 'text/html; charset=utf-8' } })
  }
  if (url.pathname === '/sitemap.xml') return sitemap(url.origin, backend)
  if (!PROXIED.some((prefix) => url.pathname.startsWith(prefix))) {
    return next() // страницы и файлы фронтенда — без изменений
  }

  const headers = new Headers(request.headers)
  // Django строит ссылки (например, на фото товаров) на адрес фронтенда, а не на внутренний адрес Render
  headers.set('X-Forwarded-Host', url.host)
  headers.set('X-Forwarded-Proto', 'https')

  // Тело пересылаем целиком (JSON или фото товара — до нескольких МБ): так код одинаково работает на Cloudflare и в Node
  const hasBody = !['GET', 'HEAD'].includes(request.method)
  const response = await fetch(backend + url.pathname + url.search, {
    method: request.method,
    headers,
    body: hasBody ? await request.arrayBuffer() : undefined,
    redirect: 'manual', // перенаправления сервера отдаём браузеру как есть
  })
  if (!url.pathname.startsWith('/api/')) return response
  // Ответы API (JSON) поисковик может читать, отрисовывая страницы, но в выдачу они попадать не должны
  const result = new Response(response.body, response)
  result.headers.set('X-Robots-Tag', 'noindex')
  return result
}

/** Карта сайта. Если сервер спит и не ответил вовремя — только основные страницы, но файл всегда корректный */
async function sitemap(origin, backend) {
  const urls = [`${origin}/`, `${origin}/terms`]
  const deadline = AbortSignal.timeout(SITEMAP_TIMEOUT_MS)
  try {
    const categories = await (await fetch(`${backend}/api/categories/`, { signal: deadline })).json()
    const walk = (nodes) => nodes.forEach((c) => { urls.push(`${origin}/?category=${c.id}`); walk(c.children || []) })
    walk(Array.isArray(categories) ? categories : categories.results || [])

    let page = `${backend}/api/products/`
    for (let i = 0; page && i < SITEMAP_MAX_PAGES; i++) {
      const data = await (await fetch(page, { signal: deadline })).json()
      data.results.forEach((p) => urls.push(`${origin}/products/${p.id}`))
      page = data.next
    }
  } catch {
    // сервер «спит» или недоступен — отдаём то, что успели собрать
  }
  const escape = (s) => s.replace(/&/g, '&amp;')
  const xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    + '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    + urls.map((u) => `  <url><loc>${escape(u)}</loc></url>`).join('\n')
    + '\n</urlset>\n'
  return new Response(xml, {
    headers: { 'Content-Type': 'application/xml; charset=utf-8', 'Cache-Control': 'public, max-age=3600' },
  })
}
