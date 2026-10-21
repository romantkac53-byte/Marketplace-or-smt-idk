import { useState } from 'react'
import { sellerApi } from '../../api'
import { EmptyState, ErrorMessage, Loader, Modal, Pagination, StatusBadge } from '../../components/ui'
import { formatDateTime, formatMoney } from '../../utils/format'
import { useLoad } from '../../utils/useLoad'
import styles from '../cabinet.module.css'

const FILTERS = [
  ['new', 'Новые'], ['confirmed', 'Подтверждены'], ['assembling', 'На сборке'], ['ready', 'Собраны'],
  ['shipped', 'В доставке'], ['delivered', 'Доставлены'], ['cancelled', 'Отменены'], ['', 'Все'],
]
const CANCELLABLE = ['new', 'confirmed', 'assembling', 'ready']

function CancelModal({ order, onClose, onDone }) {
  const [comment, setComment] = useState('')
  const [state, setState] = useState({ busy: false, error: '' })
  const onSubmit = async (e) => {
    e.preventDefault()
    setState({ busy: true, error: '' })
    try {
      onDone(await sellerApi.cancelOrder(order.id, comment))
    } catch (err) {
      setState({ busy: false, error: err.message })
    }
  }
  return (
    <Modal title={`Отменить заказ №${order.order_id}`} onClose={onClose}>
      <form className="stack" onSubmit={onSubmit}>
        <div className="alert small">Покупатель получит деньги обратно на баланс, товар вернётся в свободный остаток.</div>
        <div className="field">
          <label htmlFor="cancel-reason">Причина (увидит покупатель)</label>
          <textarea id="cancel-reason" className="textarea" required value={comment} onChange={(e) => setComment(e.target.value)}
                    placeholder="Например: товар закончился" />
        </div>
        {state.error && <div className="alert alert-error">{state.error}</div>}
        <button className="btn btn-danger" disabled={state.busy}>Отменить заказ</button>
      </form>
    </Modal>
  )
}

function OrderCard({ order, onChange }) {
  const [open, setOpen] = useState(order.status === 'new')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [cancelOpen, setCancelOpen] = useState(false)

  const confirm = async () => {
    setBusy(true)
    setError('')
    try { onChange(await sellerApi.confirmOrder(order.id)) } catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  return (
    <article className="card stack">
      <div className="row">
        <strong>Заказ №{order.order_id}</strong>
        <StatusBadge status={order.status} label={order.status_display} />
        {order.delivery_status && <span className="badge badge-muted">Доставка: {order.delivery_status}</span>}
        <span className="muted small">{formatDateTime(order.created_at)}</span>
        <span className="spacer" />
        <strong>{formatMoney(order.subtotal)}</strong>
        <button className="btn btn-ghost btn-sm" onClick={() => setOpen((v) => !v)} aria-expanded={open}>{open ? 'Свернуть' : 'Подробнее'}</button>
      </div>

      {open && (
        <>
          <div className={styles.tableWrap}>
            <table className="table">
              <thead><tr><th>Товар</th><th className={styles.num}>Кол-во</th><th className={styles.num}>Цена</th>
                <th className={styles.num}>Сумма</th><th className={styles.num}>Комиссия</th><th className={styles.num}>Вам</th></tr></thead>
              <tbody>
                {order.items.map((i) => (
                  <tr key={i.id}>
                    <td>{i.product_name}{i.promotion && <div className="small" style={{ color: 'var(--color-sale)' }}>{i.promotion}</div>}</td>
                    <td className={styles.num}>{i.quantity}</td>
                    <td className={styles.num}>{formatMoney(i.price)}</td>
                    <td className={styles.num}>{formatMoney(i.subtotal)}</td>
                    <td className={styles.num}>{formatMoney(i.commission)} <span className="muted small">({Number(i.commission_percent)}%)</span></td>
                    <td className={styles.num}><strong>{formatMoney(i.seller_payout)}</strong></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className={styles.money}>
            <div className={styles.moneyItem}><span className="small muted">Сумма заказа</span><strong>{formatMoney(order.subtotal)}</strong></div>
            <div className={styles.moneyItem}><span className="small muted">Комиссия площадки</span><strong>−{formatMoney(order.commission)}</strong></div>
            <div className={styles.moneyItem}><span className="small muted">К выплате вам</span><strong>{formatMoney(order.seller_payout)}</strong></div>
          </div>
          <details>
            <summary className="small muted">История статусов</summary>
            <ul className="small" style={{ margin: '8px 0 0', paddingLeft: 18 }}>
              {order.history.map((h, idx) => (
                <li key={idx}>{formatDateTime(h.changed_at)} — {h.status_display}{h.comment && ` (${h.comment})`}</li>
              ))}
            </ul>
          </details>
        </>
      )}

      {error && <div className="alert alert-error">{error}</div>}
      {(order.status === 'new' || CANCELLABLE.includes(order.status)) && (
        <div className="row">
          {order.status === 'new' && (
            <button className="btn btn-primary" disabled={busy} onClick={confirm}>Подтвердить — передать на сборку</button>
          )}
          {CANCELLABLE.includes(order.status) && (
            <button className="btn btn-danger" disabled={busy} onClick={() => setCancelOpen(true)}>Отменить</button>
          )}
        </div>
      )}
      {cancelOpen && <CancelModal order={order} onClose={() => setCancelOpen(false)} onDone={(updated) => { setCancelOpen(false); onChange(updated) }} />}
    </article>
  )
}

export default function SellerOrdersPage() {
  const [status, setStatus] = useState('new')
  const [page, setPage] = useState(1)
  const { data, loading, error, reload, setData } = useLoad(() => sellerApi.orders({ status, page }), [status, page])

  // Действие вернуло обновлённый подзаказ — заменяем его в списке без перезагрузки
  const replace = (updated) => setData({ ...data, results: data.results.map((o) => (o.id === updated.id ? updated : o)) })

  return (
    <>
      <div className={styles.head}><h1>Заказы магазина</h1></div>
      <div className={styles.toolbar} role="tablist">
        {FILTERS.map(([value, label]) => (
          <button key={value} role="tab" aria-selected={status === value}
                  className={`btn btn-sm ${status === value ? 'btn-primary' : 'btn-outline'}`}
                  onClick={() => { setStatus(value); setPage(1) }}>{label}</button>
        ))}
      </div>
      <ErrorMessage error={error} onRetry={reload} />
      {loading && !data ? <Loader /> : data && (
        data.count === 0 ? (
          <EmptyState icon="🧾" title="Заказов нет" text={status === 'new' ? 'Новые оплаченные заказы появятся здесь' : 'В этом разделе пусто'} />
        ) : (
          <div className="stack">
            {data.results.map((order) => <OrderCard key={order.id} order={order} onChange={replace} />)}
            <Pagination page={page} count={data.count} onChange={setPage} />
          </div>
        )
      )}
    </>
  )
}
