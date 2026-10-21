/**
 * Всплывающие уведомления: const toast = useToast(); toast('Добавлено в корзину')
 * Справа вверху, исчезают сами через 3 с. Ошибки в формах по-прежнему показываются под полями.
 */
import { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import styles from './Toast.module.css'

const ToastContext = createContext(() => {})

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const nextId = useRef(1)

  const dismiss = useCallback((id) => setToasts((list) => list.filter((t) => t.id !== id)), [])

  /** toast('текст', { type: 'success' | 'error' | 'info', link: { to, label } }) */
  const toast = useCallback((text, { type = 'success', link, duration = 3000 } = {}) => {
    const id = nextId.current++
    setToasts((list) => [...list.slice(-3), { id, text, type, link }]) // одновременно — не больше 4
    setTimeout(() => dismiss(id), duration)
  }, [dismiss])

  const value = useMemo(() => toast, [toast])
  return (
    <ToastContext.Provider value={value}>
      {children}
      {/* aria-live: экранный диктор зачитает уведомление, не уводя фокус */}
      <div className={styles.stack} aria-live="polite" role="status">
        {toasts.map((t) => (
          <div key={t.id} className={`${styles.toast} ${styles[t.type]}`}>
            <span aria-hidden="true">{t.type === 'error' ? '⚠️' : t.type === 'info' ? 'ℹ️' : '✓'}</span>
            <span className={styles.text}>{t.text}</span>
            {t.link && <Link to={t.link.to} className={styles.link} onClick={() => dismiss(t.id)}>{t.link.label}</Link>}
            <button className={styles.close} onClick={() => dismiss(t.id)} aria-label="Закрыть">✕</button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export const useToast = () => useContext(ToastContext)
