/** Небольшие общие компоненты интерфейса. */
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { formatMoney, statusTone } from '../utils/format'
import styles from './ui.module.css'

export function Loader({ text = 'Загрузка…' }) {
  return (
    <div className={styles.loader} role="status">
      <span className={styles.spinner} aria-hidden="true" />
      {text}
    </div>
  )
}

export function ErrorMessage({ error, onRetry }) {
  if (!error) return null
  return (
    <div className="alert alert-error row">
      <span>{error.message || String(error)}</span>
      {onRetry && <button className="btn btn-sm btn-outline" onClick={onRetry}>Повторить</button>}
    </div>
  )
}

export function EmptyState({ icon = '📦', title, text, action }) {
  return (
    <div className={`card ${styles.empty}`}>
      <div className={styles.emptyIcon} aria-hidden="true">{icon}</div>
      <h3>{title}</h3>
      {text && <p className="muted">{text}</p>}
      {action}
    </div>
  )
}

/** Цена: со скидкой — старая зачёркнута, новая красная */
export function Price({ price, currentPrice, size = 'md' }) {
  const hasDiscount = currentPrice !== undefined && Number(currentPrice) < Number(price)
  return (
    <span className={`${styles.price} ${styles[size]}`}>
      <span className={hasDiscount ? styles.priceSale : undefined}>{formatMoney(hasDiscount ? currentPrice : price)}</span>
      {hasDiscount && <s className={styles.priceOld}>{formatMoney(price)}</s>}
    </span>
  )
}

/** Звёзды рейтинга: ★★★★☆ 4.2 (12) */
export function Rating({ value, count, showEmpty = true }) {
  if (value === null || value === undefined) {
    return showEmpty ? <span className="muted small">Нет оценок</span> : null
  }
  const full = Math.round(value)
  return (
    <span className={styles.rating} title={`Оценка ${value} из 5`}>
      <span className={styles.stars} aria-hidden="true">{'★'.repeat(full)}<span className={styles.starsEmpty}>{'★'.repeat(5 - full)}</span></span>
      <span>{Number(value).toFixed(1)}</span>
      {count !== undefined && <span className="muted">({count})</span>}
    </span>
  )
}

/** Выбор оценки звёздами (форма отзыва) */
export function StarInput({ value, onChange }) {
  return (
    <div className={styles.starInput} role="radiogroup" aria-label="Оценка">
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          type="button"
          role="radio"
          aria-checked={value === n}
          aria-label={`${n} из 5`}
          className={n <= value ? styles.starOn : styles.starOff}
          onClick={() => onChange(n)}
        >★</button>
      ))}
    </div>
  )
}

export function StatusBadge({ status, label }) {
  return <span className={`badge badge-${statusTone(status)}`}>{label}</span>
}

/** Переключатель страниц для ответов API вида {count, next, previous, results} */
export function Pagination({ page, count, pageSize = 20, onChange }) {
  const pages = Math.ceil(count / pageSize)
  if (pages <= 1) return null
  return (
    <nav className={styles.pagination} aria-label="Страницы">
      <button className="btn btn-outline btn-sm" disabled={page <= 1} onClick={() => onChange(page - 1)}>← Назад</button>
      <span className="muted">Страница {page} из {pages}</span>
      <button className="btn btn-outline btn-sm" disabled={page >= pages} onClick={() => onChange(page + 1)}>Вперёд →</button>
    </nav>
  )
}

/** Количество с кнопками − и + */
export function QuantityControl({ value, min = 1, max, onChange, disabled }) {
  return (
    <div className={styles.qty}>
      <button type="button" aria-label="Меньше" disabled={disabled || value <= min} onClick={() => onChange(value - 1)}>−</button>
      <span aria-live="polite">{value}</span>
      <button type="button" aria-label="Больше" disabled={disabled || (max !== undefined && value >= max)} onClick={() => onChange(value + 1)}>+</button>
    </div>
  )
}

export function Modal({ title, onClose, children }) {
  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = ''
    }
  }, [onClose])
  return (
    <div className={styles.backdrop} onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className={`card ${styles.modal}`} role="dialog" aria-modal="true" aria-label={title}>
        <div className="row">
          <h3 style={{ margin: 0 }}>{title}</h3>
          <span className="spacer" />
          <button className="btn btn-ghost btn-sm" onClick={onClose} aria-label="Закрыть">✕</button>
        </div>
        {children}
      </div>
    </div>
  )
}

export function ProductImage({ src, alt, className }) {
  return src
    ? <img src={src} alt={alt} className={`${styles.image} ${className || ''}`} loading="lazy" />
    : <div className={`${styles.image} ${styles.noImage} ${className || ''}`} aria-label="Нет фото">🛍️</div>
}

export function BackLink({ to, children }) {
  return <Link to={to} className={styles.back}>← {children}</Link>
}

const EYE = 'M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12Z'

/**
 * Поле пароля с «глазом»: пока кнопку удерживают (мышью, пальцем или пробелом) — пароль виден, отпустили — снова точки.
 * Остальные свойства (id, value, onChange, autoComplete, required…) передаются в сам input.
 */
export function PasswordInput({ className = '', ...props }) {
  const [visible, setVisible] = useState(false)
  const show = () => setVisible(true)
  const hide = () => setVisible(false)
  return (
    <div className={styles.password}>
      <input {...props} type={visible ? 'text' : 'password'} className={`input ${className}`} />
      <button type="button" className={styles.eye}
              aria-label="Показать пароль (удерживайте)" aria-pressed={visible}
              title="Удерживайте, чтобы увидеть пароль"
              onPointerDown={(e) => { e.preventDefault(); show() }}  // preventDefault — курсор остаётся в поле пароля
              onPointerUp={hide} onPointerLeave={hide} onPointerCancel={hide} onBlur={hide}
              onKeyDown={(e) => { if (e.key === ' ' || e.key === 'Enter') { e.preventDefault(); show() } }}
              onKeyUp={hide}
              onContextMenu={(e) => e.preventDefault()} /* долгое нажатие на телефоне не открывает меню */>
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2"
             strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d={EYE} />
          <circle cx="12" cy="12" r="3" />
          {!visible && <path d="M3 3l18 18" />}{/* перечёркнутый глаз — пароль скрыт */}
        </svg>
      </button>
    </div>
  )
}
