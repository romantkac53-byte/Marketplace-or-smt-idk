import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useCart } from '../context/CartContext'
import { EmptyState, Price, ProductImage, QuantityControl } from '../components/ui'
import { formatMoney, plural } from '../utils/format'
import styles from './CartPage.module.css'

export default function CartPage() {
  const { cart, setQuantity, remove, clear } = useCart()
  const navigate = useNavigate()
  const [busyItem, setBusyItem] = useState(null)
  const [error, setError] = useState('')

  const run = async (itemId, action) => {
    setBusyItem(itemId)
    setError('')
    try { await action() } catch (e) { setError(e.message) } finally { setBusyItem(null) }
  }

  if (!cart.items.length) {
    return (
      <div className="container page">
        <EmptyState icon="🛒" title="Корзина пуста" text="Загляните в каталог — там много интересного"
                    action={<Link to="/" className="btn btn-primary">Перейти в каталог</Link>} />
      </div>
    )
  }

  // Группируем по магазинам: заказ потом так и разделится на подзаказы продавцов
  const bySeller = cart.items.reduce((groups, item) => {
    (groups[item.product.seller] ||= []).push(item)
    return groups
  }, {})

  return (
    <div className="container page">
      <div className="row" style={{ marginBottom: 16 }}>
        <h1 style={{ margin: 0 }}>Корзина</h1>
        <span className="muted">{plural(cart.items_count, ['товар', 'товара', 'товаров'])}</span>
        <span className="spacer" />
        <button className="btn btn-ghost btn-sm" onClick={() => run('all', clear)}>Очистить корзину</button>
      </div>
      {error && <div className="alert alert-error" style={{ marginBottom: 16 }}>{error}</div>}

      <div className={styles.layout}>
        <div className="stack">
          {Object.entries(bySeller).map(([seller, items]) => (
            <section key={seller} className="card">
              <h3>🏪 {seller}</h3>
              {items.map((item) => (
                <div key={item.id} className={styles.item} style={{ opacity: busyItem === item.id ? 0.6 : 1 }}>
                  <Link to={`/products/${item.product.id}`} className={styles.thumb}>
                    <ProductImage src={item.product.image} alt={item.product.name} />
                  </Link>
                  <div className={styles.info}>
                    <Link to={`/products/${item.product.id}`} className={styles.name}>{item.product.name}</Link>
                    <Price price={item.product.price} currentPrice={item.current_price} size="sm" />
                    {item.quantity > item.product.available && (
                      <span className="field-error">Доступно только {item.product.available} шт.</span>
                    )}
                  </div>
                  <QuantityControl value={item.quantity} max={item.product.available} disabled={busyItem === item.id}
                                   onChange={(q) => run(item.id, () => setQuantity(item.id, q))} />
                  <strong className={styles.total}>{formatMoney(item.total_price)}</strong>
                  <button className="btn btn-ghost btn-sm" aria-label="Удалить" title="Удалить"
                          onClick={() => run(item.id, () => remove(item.id))}>✕</button>
                </div>
              ))}
            </section>
          ))}
        </div>

        <aside className={`card stack ${styles.summary}`}>
          <h3 style={{ margin: 0 }}>Итого</h3>
          <div className="row"><span className="muted">Товары ({cart.items_count})</span><span className="spacer" />
            <span>{formatMoney(cart.total_price)}</span></div>
          <div className="row"><span className="muted">Доставка</span><span className="spacer" /><span>бесплатно</span></div>
          <div className={`row ${styles.grand}`}><span>К оплате</span><span className="spacer" />
            <span>{formatMoney(cart.total_price)}</span></div>
          <button className="btn btn-primary btn-lg btn-block" onClick={() => navigate('/checkout')}>Оформить заказ</button>
          {Object.keys(bySeller).length > 1 && (
            <p className="muted small" style={{ margin: 0 }}>
              Товары от {Object.keys(bySeller).length} магазинов — заказ будет собран и доставлен отдельными посылками.
            </p>
          )}
        </aside>
      </div>
    </div>
  )
}
