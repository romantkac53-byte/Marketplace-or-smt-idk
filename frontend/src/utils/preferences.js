/**
 * Согласие на cookie и тема оформления.
 *
 * Что сайт хранит в браузере:
 *  - токены входа и сам выбор по cookie — необходимое хранение, без него сайт не работает;
 *  - выбранная тема — НЕобязательное: сохраняется, только если пользователь согласился.
 * При отказе сохранённая тема удаляется, а сайт следует теме системы (Windows / телефона).
 */
const CONSENT_KEY = 'marketplace_cookie_consent'
const THEME_KEY = 'marketplace_theme'

const storage = {
  get: (key) => { try { return localStorage.getItem(key) } catch { return null } },
  set: (key, value) => { try { localStorage.setItem(key, value) } catch { /* приватный режим */ } },
  remove: (key) => { try { localStorage.removeItem(key) } catch { /* приватный режим */ } },
}

// ---------- Cookie ----------

export const getConsent = () => storage.get(CONSENT_KEY) // 'accepted' | 'declined' | null — ещё не выбрал

export function setConsent(value) {
  storage.set(CONSENT_KEY, value)
  if (value === 'accepted' && chosenTheme) storage.set(THEME_KEY, chosenTheme) // запомнить уже выбранную тему
  if (value === 'declined') {
    storage.remove(THEME_KEY)
    storage.remove('marketplace_recent') // «недавно смотрели» — тоже необязательное
  }
}

// ---------- Тема ----------

let chosenTheme = null // тема, которую пользователь выбрал в этой вкладке переключателем

const media = window.matchMedia('(prefers-color-scheme: dark)')
export const systemTheme = () => (media.matches ? 'dark' : 'light')
export const currentTheme = () => document.documentElement.dataset.theme || systemTheme()

export function applyTheme(theme) {
  document.documentElement.dataset.theme = theme
  // Цвет строки браузера на телефоне — под основной цвет темы
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', theme === 'dark' ? '#171a23' : '#2563eb')
}

export function chooseTheme(theme) {
  chosenTheme = theme
  applyTheme(theme)
  if (getConsent() === 'accepted') storage.set(THEME_KEY, theme)
}

/** Пока пользователь сам не выбрал тему — следуем за системой, даже если её переключат на ходу */
export function followSystemTheme(onChange) {
  const handler = () => {
    if (!chosenTheme && !storage.get(THEME_KEY)) {
      applyTheme(systemTheme())
      onChange(systemTheme())
    }
  }
  media.addEventListener('change', handler)
  return () => media.removeEventListener('change', handler)
}
