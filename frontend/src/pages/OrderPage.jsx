import { useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { balanceApi, ordersApi, returnsApi, reviewsApi } from '../api'
import { BackLink, ErrorMessage, Loader, Modal, QuantityControl, StarInput, StatusBadge } from '../components/ui'
import { formatDate, formatDateTime, formatMoney } from '../utils/format'
import { useLoad } from '../utils/useLoad'
import styles from './OrderPage.module.css'

const RETURN_REASONS = [['defect', 'Брак'], ['wrong_item', 'Привезли не тот товар'], ['not_fit', 'Не подошёл'], ['other', 'Другое']]

/** Путь посылки: какие шаги уже пройдены */
const COURIER_STEPS = [['pending', 'Собран'], ['assigned', 'Курьер назначен'], ['in_transit', 'В пути'], ['delivered', 'Получен']]
const PICKUP_STEPS = [['pending', 'Собран'], ['in_transit', 'Едет в пункт'], ['at_pickup_point', 'В пункте выдачи'], ['delivered', 'Получен']]

function Tracking({ delivery, isPickup }) {
  if (!delivery) return <p className="muted small" style={{ margin: 0 }}>Магазин собирает заказ — доставка появится после сборки.</p>
  if (['returned', 'cancelled'].includes(delivery.status)) {
    return <div className="alert alert-error small">{delivery.status_display}</div>
  }
  const steps = isPickup ? PICKUP_STEPS : COURIER_STEPS
  const passed = new Set(delivery.history.map((h) => h.status))
  return (
    <div className="stack">
      <ol className={styles.steps}>
        {steps.map(([status, label]) => (
          <li key={status} className={passed.has(status) || delivery.status === status ? styles.stepDone : ''}>{label}</li>
        ))}
      </ol>
      {delivery.status !== 'delivered' && (
        <div className={styles.code}>
          <span className="small">Код получения — назовите его {isPickup ? 'в пункте выдачи' : 'курьеру'}:</span>
          <strong>{delivery.pickup_code}</strong>
        </div>
      )}
      {delivery.courier && delivery.status === 'in_transit' && <span className="small muted">Курьер: {delivery.courier}</span>}
      {delivery.storage_until && delivery.status === 'at_pickup_point' && (
        <span className="small">Хранится до <strong>{formatDate(delivery.storage_until)}</strong></span>
      )}
      {delivery.delivered_at && <span className="small muted">Получен {formatDateTime(delivery.delivered_at)}</span>}
    </div>
  )
}

function ReviewModal({ item, onClose }) {
  const [rating, setRating] = useState(5)
  const [text, setText] = useState('')
  const [state, setState] = useState({ busy: false, error: '', done: false })
  const onSubmit = async (e) => {
    e.preventDefault()
    setState({ busy: true, error: '', done: false })
    try {
      await reviewsApi.create({ product_id: item.product_id, rating, text })
      setState({ busy: false, error: '', done: true })
    } catch (err) {
      setState({ busy: false, error: err.message, done: false })
    }
  }
  return (
    <Modal title={`Отзыв: ${item.product_name}`} onClose={onClose}>
      {state.done ? (
        <>
          <div className="alert alert-success">Спасибо! Отзыв опубликован.</div>
          <button className="btn btn-primary" onClick={onClose}>Готово</button>
        </>
      ) : (
        <form className="stack" onSubmit={onSubmit}>
          <StarInput value={rating} onChange={setRating} />
          <textarea className="textarea" placeholder="Что понравилось или нет?" value={text} onChange={(e) => setText(e.target.value)} />
          {state.error && <div className="alert alert-error">{state.error}</div>}
          <button className="btn btn-primary" disabled={state.busy}>Опубликовать</button>
          <span className="muted small">Если вы уже оставляли отзыв на этот товар, он обновится.</span>
        </form>
      )}
    </Modal>
  )
}

function ReturnModal({ item, onClose, onDone }) {
  const [quantity, setQuantity] = useState(1)
  const [reason, setReason] = useState('defect')
  const [description, setDescription] = useState('')
  const [state, setState] = useState({ busy: false, error: '' })
  const onSubmit = async (e) => {
    e.preventDefault()
    setState({ busy: true, error: '' })
    try {
      await returnsApi.create({ order_item_id: item.id, quantity, reason, description })
      onDone()
    } catch (err) {
      setState({ busy: false, error: err.message })
    }
  }
  return (
    <Modal title={`Возврат: ${item.product_name}`} onClose={onClose}>
      <form className="stack" onSubmit={onSubmit}>
        <div className="field">
          <label>Количество (можно вернуть {item.returnable_quantity})</label>
          <QuantityControl value={quantity} max={item.returnable_quantity} onChange={setQuantity} />
        </div>
        <div className="field">
          <label htmlFor="reason">Причина</label>
          <select id="reason" className="select" value={reason} onChange={(e) => setReason(e.target.value)}>
            {RETURN_REASONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </div>
        <div className="field">
          <label htmlFor="description">Опишите проблему</label>
          <textarea id="description" className="textarea" value={description} onChange={(e) => setDescription(e.target.value)} />
        </div>
        <div className="alert small">
          К возврату: <strong>{formatMoney(Number(item.price) * quantity)}</strong>. Деньги придут на баланс после того,
          как менеджер одобрит заявку и склад примет товар.
        </div>
        {state.error && <div className="alert alert-error">{state.error}</div>}
        <button className="btn btn-primary" disabled={state.busy}>Отправить заявку</button>
      </form>
    </Modal>
  )
}

export default function OrderPage() {
  const { id } = useParams()
  const location = useLocation()
  const { data: order, loading, error, reload, setData } = useLoad(() => ordersApi.get(id), [id])
  const balance = useLoad(() => balanceApi.get(), [id])
  const [action, setAction] = useState({ busy: false, error: '' })
  const [modal, setModal] = useState(null) // { type: 'review' | 'return', item }
  const [notice, setNotice] = useState(location.state?.justPlaced ? 'Заказ оформлен! Осталось оплатить.' : '')

  if (loading && !order) return <Loader />
  if (error) return <div className="container page"><ErrorMessage error={error} onRetry={reload} /></div>

  /** Действие с заказом: API возвращает заказ целиком — просто показываем ответ */
  const run = async (request, successText) => {
    setAction({ busy: true, error: '' })
    setNotice('')
    try {
      setData(await request())
      balance.reload()
      setNotice(successText)
      setAction({ busy: false, error: '' })
    } catch (err) {
      setAction({ busy: false, error: err.message })
      reload() // например, неудачная оплата меняет статус платежа
      balance.reload()
    }
  }

  const confirmCancel = (text) => window.confirm(text)
  // В истории есть и статусы всего заказа, и статусы посылок отдельных магазинов — подписываем магазин
  const sellerNames = Object.fromEntries(order.seller_orders.map((so) => [so.id, so.seller]))
  const isPickup = order.delivery_type === 'pickup'
  const canCancelAll = ['new', 'paid'].includes(order.status) && order.seller_orders.every((so) => so.can_cancel || so.status === 'cancelled')
  const enough = balance.data && Number(balance.data.balance) >= Number(order.payment?.amount || 0)

  return (
    <div className="container page">
      <BackLink to="/orders">Мои заказы</BackLink>
      <div className="row" style={{ marginBottom: 16 }}>
        <h1 style={{ margin: 0 }}>Заказ №{order.id}</h1>
        <StatusBadge status={order.status} label={order.status_display} />
        <span className="muted">от {formatDateTime(order.created_at)}</span>
      </div>
      {notice && <div className="alert alert-success" style={{ marginBottom: 16 }}>{notice}</div>}
      {action.error && <div className="alert alert-error" style={{ marginBottom: 16 }}>{action.error}</div>}

      <div className={styles.layout}>
        <div className="stack">
          {order.seller_orders.map((so) => (
            <section key={so.id} className="card stack">
              <div className="row">
                <h3 style={{ margin: 0 }}>🏪 {so.seller}</h3>
                <StatusBadge status={so.status} label={so.status_display} />
                <span className="spacer" />
                {so.can_cancel && order.seller_orders.length > 1 && (
                  <button className="btn btn-danger btn-sm" disabled={action.busy} onClick={() =>
                    confirmCancel(`Отменить товары магазина «${so.seller}»? Если заказ оплачен, деньги вернутся на баланс.`) &&
                    run(() => ordersApi.cancelPart(order.id, so.id), 'Часть заказа отменена')}>Отменить эту часть</button>
                )}
              </div>

              <table className="table">
                <tbody>
                  {so.items.map((item) => (
                    <tr key={item.id}>
                      <td><Link to={`/products/${item.product_id}`}>{item.product_name}</Link>
                        {item.promotion && <div className="small" style={{ color: 'var(--color-sale)' }}>{item.promotion}</div>}
                      </td>
                      <td className="muted">{item.quantity} × {formatMoney(item.price)}</td>
                      <td style={{ textAlign: 'right' }}><strong>{formatMoney(item.subtotal)}</strong></td>
                      {(so.can_review || item.returnable_quantity > 0) && (
                        <td style={{ textAlign: 'right' }}>
                          <div className={styles.itemActions}>
                            {so.can_review && <button className="btn btn-outline btn-sm" onClick={() => setModal({ type: 'review', item })}>Отзыв</button>}
                            {item.returnable_quantity > 0 && <button className="btn btn-ghost btn-sm" onClick={() => setModal({ type: 'return', item })}>Вернуть</button>}
                          </div>
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
              {so.status !== 'cancelled' && order.status !== 'new' && <Tracking delivery={so.delivery} isPickup={isPickup} />}
            </section>
          ))}

          <section className="card">
            <h3>История заказа</h3>
            <ul className={styles.history}>
              {order.history.map((h, i) => (
                <li key={i}>
                  <span className="muted small">{formatDateTime(h.changed_at)}</span>
                  <span>
                    {h.seller_order_id && <strong>{sellerNames[h.seller_order_id]}: </strong>}
                    {h.status_display}{h.comment && <span className="muted"> — {h.comment}</span>}
                  </span>
                </li>
              ))}
            </ul>
          </section>
        </div>

        <aside className="stack">
          <section className="card stack">
            <h3 style={{ margin: 0 }}>Оплата</h3>
            <div className="row"><span className="muted">Сумма</span><span className="spacer" /><strong>{formatMoney(order.payment?.amount)}</strong></div>
            {Number(order.payment?.refunded_amount) > 0 && (
              <div className="row"><span className="muted">Возвращено</span><span className="spacer" />{formatMoney(order.payment.refunded_amount)}</div>
            )}
            {order.payment && <StatusBadge status={order.payment.status} label={order.payment.status_display} />}
            {order.status === 'new' && (
              <>
                {order.payment?.error_message && <div className="alert alert-error small">{order.payment.error_message}</div>}
                <span className="small muted">На балансе: {balance.data ? formatMoney(balance.data.balance) : '…'}</span>
                <button className="btn btn-primary btn-lg" disabled={action.busy || !enough}
                        onClick={() => run(() => ordersApi.pay(order.id), 'Заказ оплачен! Магазины начали его собирать.')}>
                  Оплатить {formatMoney(order.payment?.amount)}
                </button>
                {balance.data && !enough && (
                  <span className="small field-error">Не хватает {formatMoney(Number(order.payment.amount) - Number(balance.data.balance))}. Баланс пополняет администратор.</span>
                )}
              </>
            )}
          </section>

          <section className="card stack">
            <h3 style={{ margin: 0 }}>Получение</h3>
            <span>{isPickup ? '🏬 Пункт выдачи' : '🚚 Курьер'}</span>
            {isPickup && order.pickup_point ? (
              <span className="small">
                <strong>{order.pickup_point.name}</strong><br />{order.pickup_point.city}, {order.pickup_point.address}<br />
                <span className="muted">{order.pickup_point.working_hours}</span>
              </span>
            ) : <span className="small">{order.delivery_address}</span>}
          </section>

          {canCancelAll && (
            <button className="btn btn-danger" disabled={action.busy} onClick={() =>
              confirmCancel('Отменить весь заказ? Если он оплачен, деньги вернутся на баланс.') &&
              run(() => ordersApi.cancel(order.id), 'Заказ отменён')}>Отменить заказ</button>
          )}
        </aside>
      </div>

      {modal?.type === 'review' && <ReviewModal item={modal.item} onClose={() => setModal(null)} />}
      {modal?.type === 'return' && (
        <ReturnModal item={modal.item} onClose={() => setModal(null)} onDone={() => {
          setModal(null)
          setNotice('Заявка на возврат отправлена. Статус — в разделе «Мои возвраты».')
          reload()
        }} />
      )}
    </div>
  )
}
