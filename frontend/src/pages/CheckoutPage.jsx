import { useMemo, useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { ordersApi } from '../api'
import { useAuth } from '../context/AuthContext'
import { useCart } from '../context/CartContext'
import { ErrorMessage, Loader } from '../components/ui'
import { formatMoney, plural } from '../utils/format'
import { useLoad } from '../utils/useLoad'
import styles from './CheckoutPage.module.css'

export default function CheckoutPage() {
  const { user } = useAuth()
  const { cart, refresh } = useCart()
  const navigate = useNavigate()
  const points = useLoad(() => ordersApi.pickupPoints(), [])
  const [deliveryType, setDeliveryType] = useState('courier')
  const [address, setAddress] = useState(user.customer?.address || '')
  const [city, setCity] = useState('')
  const [pointId, setPointId] = useState('')
  const [state, setState] = useState({ busy: false, error: '' })

  const cities = useMemo(() => [...new Set((points.data || []).map((p) => p.city))].sort(), [points.data])
  const visiblePoints = (points.data || []).filter((p) => !city || p.city === city)

  if (!cart.items.length && !state.busy) return <Navigate to="/cart" replace />

  const onSubmit = async (e) => {
    e.preventDefault()
    setState({ busy: true, error: '' })
    try {
      const order = await ordersApi.place(
        deliveryType === 'pickup'
          ? { delivery_type: 'pickup', pickup_point_id: Number(pointId) }
          : { delivery_type: 'courier', delivery_address: address },
      )
      await refresh() // корзина на сервере очищена — обновляем счётчик в шапке
      navigate(`/orders/${order.id}`, { replace: true, state: { justPlaced: true } })
    } catch (err) {
      setState({ busy: false, error: err.message })
    }
  }

  return (
    <div className="container page">
      <h1>Оформление заказа</h1>
      <form className={styles.layout} onSubmit={onSubmit}>
        <section className="card stack">
          <h2>Способ получения</h2>
          <div className={styles.options}>
            <label className={`${styles.option} ${deliveryType === 'courier' ? styles.optionActive : ''}`}>
              <input type="radio" name="delivery" checked={deliveryType === 'courier'} onChange={() => setDeliveryType('courier')} />
              <span><strong>🚚 Курьером</strong><br /><span className="muted small">Привезём по адресу</span></span>
            </label>
            <label className={`${styles.option} ${deliveryType === 'pickup' ? styles.optionActive : ''}`}>
              <input type="radio" name="delivery" checked={deliveryType === 'pickup'} onChange={() => setDeliveryType('pickup')} />
              <span><strong>🏬 В пункт выдачи</strong><br /><span className="muted small">Заберёте, когда удобно</span></span>
            </label>
          </div>

          {deliveryType === 'courier' ? (
            <div className="field">
              <label htmlFor="address">Адрес доставки</label>
              <input id="address" className="input" required value={address} onChange={(e) => setAddress(e.target.value)}
                     placeholder="Город, улица, дом, квартира" />
            </div>
          ) : points.loading ? <Loader text="Загружаем пункты выдачи…" /> : (
            <div className="stack">
              <ErrorMessage error={points.error} onRetry={points.reload} />
              {cities.length > 1 && (
                <div className="field">
                  <label htmlFor="city">Город</label>
                  <select id="city" className="select" value={city} onChange={(e) => { setCity(e.target.value); setPointId('') }}>
                    <option value="">Все города</option>
                    {cities.map((c) => <option key={c} value={c}>{c}</option>)}
                  </select>
                </div>
              )}
              {visiblePoints.length === 0 && <p className="muted">Пунктов выдачи пока нет — выберите доставку курьером.</p>}
              <div className={styles.points}>
                {visiblePoints.map((p) => (
                  <label key={p.id} className={`${styles.option} ${String(pointId) === String(p.id) ? styles.optionActive : ''}`}>
                    <input type="radio" name="point" required value={p.id} checked={String(pointId) === String(p.id)}
                           onChange={(e) => setPointId(e.target.value)} />
                    <span>
                      <strong>{p.name}</strong><br />
                      <span className="small">{p.city}, {p.address}</span><br />
                      <span className="muted small">{p.working_hours || 'Часы работы уточняйте'} · хранение {p.storage_days} дн.</span>
                    </span>
                  </label>
                ))}
              </div>
            </div>
          )}
        </section>

        <aside className={`card stack ${styles.summary}`}>
          <h3 style={{ margin: 0 }}>Ваш заказ</h3>
          {cart.items.map((item) => (
            <div key={item.id} className="row small">
              <span className={styles.itemName}>{item.product.name} × {item.quantity}</span>
              <span className="spacer" />
              <span>{formatMoney(item.total_price)}</span>
            </div>
          ))}
          <div className={`row ${styles.grand}`}>
            <span>К оплате</span><span className="spacer" /><span>{formatMoney(cart.total_price)}</span>
          </div>
          {state.error && <div className="alert alert-error">{state.error}</div>}
          <button className="btn btn-primary btn-lg btn-block" disabled={state.busy || (deliveryType === 'pickup' && !pointId)}>
            {state.busy ? 'Оформляем…' : 'Подтвердить заказ'}
          </button>
          <p className="muted small" style={{ margin: 0 }}>
            Оплата — с баланса на следующем шаге. {plural(cart.items_count, ['товар', 'товара', 'товаров'])} будут
            зарезервированы за вами. <Link to="/cart">Изменить корзину</Link>
          </p>
        </aside>
      </form>
    </div>
  )
}
