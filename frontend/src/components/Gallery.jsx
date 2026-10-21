/** Сердечко «в избранное» и галерея фото товара. */
import { useState } from 'react'
import { useAuth } from '../context/AuthContext'
import { useFavorites } from '../context/FavoritesContext'
import { useOpenAuth } from '../utils/authModal'
import { ProductImage } from './ui'
import styles from './Gallery.module.css'

/** ♡ — для покупателей и гостей (гостя отправит на вход). Продавцу и персоналу не показывается. */
export function FavoriteButton({ productId, className = '' }) {
  const { user, isCustomer } = useAuth()
  const favorites = useFavorites()
  const openAuth = useOpenAuth()
  if (user && !isCustomer) return null
  const active = favorites.has(productId)
  const onClick = () => {
    if (!user) { openAuth(); return }
    favorites.toggle(productId)
  }
  return (
    <button type="button" className={`${styles.heart} ${active ? styles.heartActive : ''} ${className}`} onClick={onClick}
            aria-pressed={active} aria-label={active ? 'Убрать из избранного' : 'Добавить в избранное'}
            title={active ? 'Убрать из избранного' : 'В избранное'}>
      <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
        <path d="M12 20.5s-7.5-4.6-7.5-10.2A4.3 4.3 0 0 1 12 7.6a4.3 4.3 0 0 1 7.5 2.7c0 5.6-7.5 10.2-7.5 10.2Z"
              strokeWidth="1.8" strokeLinejoin="round" />
      </svg>
    </button>
  )
}

/** Главное фото + миниатюры; листается стрелками ‹ › и клавишами ← → */
export function Gallery({ images, alt, children }) {
  const [index, setIndex] = useState(0)
  const count = images.length
  const go = (step) => setIndex((i) => (i + step + count) % count)
  if (count === 0) return <div className={styles.main}><ProductImage alt={alt} />{children}</div>

  return (
    <div className={styles.gallery}>
      <div className={styles.main} tabIndex={count > 1 ? 0 : undefined} aria-label={`Фото ${index + 1} из ${count}`}
           onKeyDown={(e) => { if (e.key === 'ArrowRight') go(1); if (e.key === 'ArrowLeft') go(-1) }}>
        <ProductImage src={images[index]} alt={`${alt} — фото ${index + 1}`} />
        {children}
        {count > 1 && (
          <>
            <button type="button" className={`${styles.arrow} ${styles.prev}`} onClick={() => go(-1)} aria-label="Предыдущее фото">‹</button>
            <button type="button" className={`${styles.arrow} ${styles.next}`} onClick={() => go(1)} aria-label="Следующее фото">›</button>
            <span className={styles.counter}>{index + 1} / {count}</span>
          </>
        )}
      </div>
      {count > 1 && (
        <div className={styles.thumbs}>
          {images.map((src, i) => (
            <button key={src} type="button" className={`${styles.thumb} ${i === index ? styles.thumbActive : ''}`}
                    onClick={() => setIndex(i)} aria-label={`Фото ${i + 1}`} aria-current={i === index}>
              <img src={src} alt="" loading="lazy" />
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
