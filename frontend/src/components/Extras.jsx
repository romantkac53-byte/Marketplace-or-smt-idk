/** Переключатель темы, cookie-баннер, кнопка «Наверх», кнопка «Скопировать». */
import { useEffect, useRef, useState } from 'react'
import { useToast } from '../context/ToastContext'
import { chooseTheme, currentTheme, followSystemTheme, getConsent, setConsent } from '../utils/preferences'
import styles from './Extras.module.css'

// ---------- Тема ----------

export function ThemeToggle({ className }) {
  const [theme, setTheme] = useState(currentTheme)
  useEffect(() => followSystemTheme(setTheme), [])
  const next = theme === 'dark' ? 'light' : 'dark'
  return (
    <button type="button" className={className} onClick={() => { chooseTheme(next); setTheme(next) }}
            aria-label={next === 'dark' ? 'Включить тёмную тему' : 'Включить светлую тему'}
            title={next === 'dark' ? 'Тёмная тема' : 'Светлая тема'}>
      <span aria-hidden="true">{theme === 'dark' ? '☀️' : '🌙'}</span>
    </button>
  )
}

// ---------- Cookie ----------

export function CookieBanner() {
  const [visible, setVisible] = useState(() => getConsent() === null)
  const ref = useRef(null)

  // Высота баннера — в CSS-переменную, чтобы кнопка «Наверх» поднималась над ним, а не пряталась под ним
  useEffect(() => {
    const root = document.documentElement
    if (!visible || !ref.current) {
      root.style.setProperty('--cookie-banner-h', '0px')
      return undefined
    }
    const observer = new ResizeObserver(([entry]) =>
      root.style.setProperty('--cookie-banner-h', `${entry.target.offsetHeight}px`))
    observer.observe(ref.current)
    return () => observer.disconnect()
  }, [visible])

  if (!visible) return null
  const choose = (value) => { setConsent(value); setVisible(false) }
  return (
    <div ref={ref} className={styles.banner} role="region" aria-label="Использование cookie">
      <div className={`container ${styles.bannerInner}`}>
        <p className={styles.bannerText}>
          <span aria-hidden="true">🍪 </span>
          Мы используем cookie и локальное хранилище браузера: чтобы вы оставались в аккаунте и чтобы запоминать
          настройки (например, тему оформления). Необходимое для входа работает всегда; от остального можно отказаться.
        </p>
        <div className={styles.bannerActions}>
          <button className="btn btn-outline" onClick={() => choose('declined')}>Отказаться</button>
          <button className="btn btn-primary" onClick={() => choose('accepted')}>Согласиться</button>
        </div>
      </div>
    </div>
  )
}

// ---------- Наверх ----------

export function ScrollTopButton() {
  const [visible, setVisible] = useState(false)
  useEffect(() => {
    const onScroll = () => setVisible(window.scrollY > 400)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  return (
    <button type="button" aria-label="Наверх страницы" title="Наверх"
            className={`${styles.scrollTop} ${visible ? styles.scrollTopVisible : ''}`} tabIndex={visible ? 0 : -1}
            onClick={() => window.scrollTo({ top: 0, behavior: reduceMotion ? 'auto' : 'smooth' })}>
      <svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 19V5M5 12l7-7 7 7" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </button>
  )
}

// ---------- Скопировать ----------

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text)
  } catch {
    // Запасной путь: старые браузеры и страницы без HTTPS, где clipboard API недоступен
    const area = Object.assign(document.createElement('textarea'), { value: text })
    area.style.position = 'fixed'
    area.style.opacity = '0'
    document.body.appendChild(area)
    area.select()
    document.execCommand('copy')
    area.remove()
  }
}

/** Кнопка копирования: после нажатия на 1,5 с показывает «Скопировано» */
export function CopyButton({ text, label, className = 'btn btn-ghost btn-sm', title, toastText = 'Скопировано' }) {
  const toast = useToast()
  const [copied, setCopied] = useState(false)
  useEffect(() => {
    if (!copied) return undefined
    const timer = setTimeout(() => setCopied(false), 1500)
    return () => clearTimeout(timer)
  }, [copied])
  return (
    <button type="button" className={className} title={title}
            onClick={async () => { await copyText(String(text)); setCopied(true); toast(toastText, { type: 'info' }) }}>
      <span aria-live="polite">{copied ? '✓ Скопировано' : label}</span>
    </button>
  )
}

/** «Артикул 123456789 ⧉» — номер и кнопка копирования */
export function ArticleBadge({ article, withLink = false, productId }) {
  if (!article) return null
  return (
    <span className={styles.article}>
      <span className="muted">Артикул</span> <strong>{article}</strong>
      <CopyButton text={article} label="⧉" title="Скопировать артикул" className={styles.copyIcon} toastText={`Артикул ${article} скопирован`} />
      {withLink && (
        <CopyButton text={`${window.location.origin}/products/${productId}`} label="🔗 Ссылка" title="Скопировать ссылку на товар"
                    className={styles.copyIcon} toastText="Ссылка на товар скопирована" />
      )}
    </span>
  )
}
