import { useEffect } from 'react'

/**
 * Заголовок и описание страницы для вкладки браузера, поисковиков и превью ссылок в мессенджерах.
 * Сайт — одностраничное приложение (SPA): HTML у всех адресов одинаковый, поэтому каждая страница
 * сама обновляет <title>, <meta name="description">, Open Graph и canonical (адрес «главной» копии страницы).
 */
export const SITE_NAME = 'Маркет'
export const DEFAULT_TITLE = 'Маркет — учебный маркетплейс АИС Marketplace'
export const DEFAULT_DESCRIPTION =
  'Маркет (АИС Marketplace) — учебная торговая площадка: каталог товаров нескольких продавцов, корзина, '
  + 'заказ с доставкой курьером или в пункт выдачи, отзывы и возвраты.'

function setMeta(attr, key, value) {
  let el = document.head.querySelector(`meta[${attr}="${key}"]`)
  if (!el) {
    el = document.createElement('meta')
    el.setAttribute(attr, key)
    document.head.appendChild(el)
  }
  el.setAttribute('content', value)
}

function setCanonical(href) {
  let el = document.head.querySelector('link[rel="canonical"]')
  if (!el) {
    el = document.createElement('link')
    el.setAttribute('rel', 'canonical')
    document.head.appendChild(el)
  }
  el.setAttribute('href', href)
}

function apply(title, description, path) {
  const fullTitle = title ? `${title} — ${SITE_NAME}` : DEFAULT_TITLE
  const text = (description || DEFAULT_DESCRIPTION).replace(/\s+/g, ' ').trim().slice(0, 200)
  const url = window.location.origin + path
  document.title = fullTitle
  setMeta('name', 'description', text)
  setMeta('property', 'og:title', fullTitle)
  setMeta('property', 'og:description', text)
  setMeta('property', 'og:url', url)
  setCanonical(url)
}

/**
 * usePageMeta('Смартфон Nova X', 'Описание товара…') — пока страница открыта.
 * path — адрес «главной» копии страницы (без фильтров и номера страницы); по умолчанию — текущий путь.
 */
export function usePageMeta(title, description, path) {
  useEffect(() => {
    apply(title, description, path ?? window.location.pathname)
    return () => apply(null, null, '/') // ушли со страницы — значения по умолчанию
  }, [title, description, path])
}
