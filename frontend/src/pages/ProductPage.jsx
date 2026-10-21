import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { catalogApi } from '../api'
import { useAuth } from '../context/AuthContext'
import { useCart } from '../context/CartContext'
import { ArticleBadge } from '../components/Extras'
import { FavoriteButton, Gallery } from '../components/Gallery'
import { useToast } from '../context/ToastContext'
import { useOpenAuth } from '../utils/authModal'
import { rememberProduct } from '../utils/recent'
import { ErrorMessage, Loader, Pagination, Price, QuantityControl, Rating } from '../components/ui'
import { formatDate, plural } from '../utils/format'
import { useLoad } from '../utils/useLoad'
import styles from './ProductPage.module.css'

function Reviews({ productId }) {
  const [page, setPage] = useState(1)
  const { data, loading, error } = useLoad(() => catalogApi.productReviews(productId, page), [productId, page])
  if (loading && !data) return <Loader />
  if (error) return <ErrorMessage error={error} />
  if (!data.count) return <p className="muted">Отзывов пока нет. Отзыв можно оставить после получения товара.</p>
  return (
    <div className="stack">
      {data.results.map((review) => (
        <article key={review.id} className={styles.review}>
          <div className="row">
            <strong>{review.author}</strong>
            <Rating value={review.rating} />
            <span className="spacer" />
            <span className="muted small">{formatDate(review.created_at)}</span>
          </div>
          {review.text && <p style={{ margin: 0 }}>{review.text}</p>}
          {review.seller_reply && (
            <div className={styles.reply}>
              <span className="small muted">Ответ продавца</span>
              <p style={{ margin: 0 }}>{review.seller_reply}</p>
            </div>
          )}
        </article>
      ))}
      <Pagination page={page} count={data.count} onChange={setPage} />
    </div>
  )
}

export default function ProductPage() {
  const { id } = useParams()
  const { user, isCustomer } = useAuth()
  const { add, quantityOf } = useCart()
  const { data: product, loading, error } = useLoad(() => catalogApi.product(id), [id])
  const toast = useToast()
  const openAuth = useOpenAuth()
  // Запоминаем просмотр для блока «Вы недавно смотрели» на главной
  useEffect(() => { if (product) rememberProduct(product.id) }, [product])
  const [quantity, setQuantity] = useState(1)
  const [status, setStatus] = useState({ busy: false, error: '', added: false })

  if (loading) return <Loader />
  if (error) {
    return (
      <div className="container page">
        <ErrorMessage error={error.status === 404 ? new Error('Товар не найден или снят с продажи') : error} />
      </div>
    )
  }

  const inCart = quantityOf(product.id)
  const canAddMore = product.available - inCart

  const onAdd = async () => {
    if (!user) return openAuth()
    setStatus({ busy: true, error: '', added: false })
    try {
      await add(product.id, quantity)
      setQuantity(1)
      setStatus({ busy: false, error: '', added: true })
      toast(`${quantity} шт. «${product.name}» в корзине`, { link: { to: '/cart', label: 'Корзина' } })
    } catch (e) {
      setStatus({ busy: false, error: e.message, added: false })
    }
  }

  return (
    <div className="container page">
      <nav className={styles.crumbs} aria-label="Категории">
        <Link to="/">Каталог</Link>
        {product.category_path.map((c) => (
          <span key={c.id}> / <Link to={`/?category=${c.id}`}>{c.name}</Link></span>
        ))}
      </nav>

      <div className={styles.top}>
        <div className="card">
          <Gallery images={product.images} alt={product.name}>
            <FavoriteButton productId={product.id} className={styles.favorite} />
          </Gallery>
        </div>

        <div className="stack">
          <h1 style={{ marginBottom: 0 }}>{product.name}</h1>
          <ArticleBadge article={product.article} productId={product.id} withLink />
          <div className="row">
            <Rating value={product.rating} count={product.reviews_count} />
            {product.sold_count > 0 && <span className="muted small">Купили {plural(product.sold_count, ['раз', 'раза', 'раз'])}</span>}
          </div>

          <div className={`card stack ${styles.buyBox}`}>
            <Price price={product.price} currentPrice={product.current_price} size="lg" />
            {product.promotion && <span className="badge badge-sale" style={{ alignSelf: 'flex-start' }}>{product.promotion}</span>}
            <span className={product.available > 0 ? 'badge badge-success' : 'badge badge-muted'} style={{ alignSelf: 'flex-start' }}>
              {product.available > 0 ? `В наличии: ${product.available} шт.` : 'Нет в наличии'}
            </span>

            {(isCustomer || !user) && product.available > 0 && (
              <>
                <div className="row">
                  <QuantityControl value={quantity} max={Math.max(canAddMore, 1)} onChange={setQuantity}
                                   disabled={canAddMore <= 0} />
                  <button className="btn btn-primary btn-lg" style={{ flex: 1 }} onClick={onAdd}
                          disabled={status.busy || canAddMore <= 0}>
                    {canAddMore <= 0 ? 'Всё доступное уже в корзине' : 'Добавить в корзину'}
                  </button>
                </div>
                {inCart > 0 && (
                  <div className="alert alert-success row">
                    {status.added ? 'Добавлено! ' : ''}В корзине: {inCart} шт.
                    <span className="spacer" />
                    <Link to="/cart" className="btn btn-sm btn-outline">Перейти в корзину</Link>
                  </div>
                )}
                {status.error && <div className="alert alert-error">{status.error}</div>}
              </>
            )}
            <span className="muted small">Продавец: <strong>{product.seller}</strong></span>
          </div>
        </div>
      </div>

      <div className={styles.bottom}>
        <section className="card">
          <h2>Описание</h2>
          {product.description
            ? <p style={{ whiteSpace: 'pre-line' }}>{product.description}</p>
            : <p className="muted">Продавец не добавил описание.</p>}
          {product.characteristics.length > 0 && (
            <>
              <h3 style={{ marginTop: 24 }}>Характеристики</h3>
              <table className="table">
                <tbody>
                  {product.characteristics.map((c) => (
                    <tr key={c.id}>
                      <th scope="row">{c.name}</th>
                      <td>{c.value}{c.unit ? ` ${c.unit}` : ''}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </section>

        <section className="card">
          <h2>Отзывы</h2>
          <Reviews productId={product.id} />
        </section>
      </div>
    </div>
  )
}
