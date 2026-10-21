import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useCart } from '../context/CartContext'
import { useToast } from '../context/ToastContext'
import { useOpenAuth } from '../utils/authModal'
import { FavoriteButton } from './Gallery'
import { Price, ProductImage, Rating } from './ui'
import styles from './ProductCard.module.css'

export default function ProductCard({ product }) {
  const { user, isCustomer } = useAuth()
  const { add, quantityOf } = useCart()
  const openAuth = useOpenAuth()
  const toast = useToast()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const inCart = quantityOf(product.id)
  const discount = Number(product.current_price) < Number(product.price)
    ? Math.round((1 - Number(product.current_price) / Number(product.price)) * 100)
    : 0

  const onAdd = async () => {
    if (!user) return openAuth('login', `/products/${product.id}`)
    setBusy(true)
    setError('')
    try {
      await add(product.id, 1)
      toast(`«${product.name}» в корзине`, { link: { to: '/cart', label: 'Корзина' } })
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <article className={styles.card}>
      {/* ♡ — рядом со ссылкой, а не внутри: кнопка внутри ссылки — недопустимая разметка */}
      <div className={styles.imageWrap}>
        <Link to={`/products/${product.id}`} className={styles.imageLink}>
          <ProductImage src={product.image} alt={product.name} />
          {discount > 0 && <span className={`badge badge-sale ${styles.sale}`}>−{discount}%</span>}
        </Link>
        <FavoriteButton productId={product.id} className={styles.favorite} />
      </div>
      <div className={styles.body}>
        <Price price={product.price} currentPrice={product.current_price} />
        <Link to={`/products/${product.id}`} className={styles.name}>{product.name}</Link>
        <Rating value={product.rating} count={product.reviews_count} showEmpty={false} />
        <span className="muted small">{product.seller}</span>
      </div>
      {error && <div className={`field-error ${styles.error}`}>{error}</div>}
      {(isCustomer || !user) && (
        product.available > 0 ? (
          <button className={`btn ${inCart ? 'btn-outline' : 'btn-primary'} btn-block`} onClick={onAdd} disabled={busy}>
            {inCart ? `В корзине: ${inCart} · ещё` : 'В корзину'}
          </button>
        ) : (
          <button className="btn btn-outline btn-block" disabled>Нет в наличии</button>
        )
      )}
    </article>
  )
}
