import { useState } from 'react'
import { Link } from 'react-router-dom'
import { returnsApi } from '../api'
import { EmptyState, ErrorMessage, Loader, Pagination, StatusBadge } from '../components/ui'
import { formatDateTime, formatMoney } from '../utils/format'
import { useLoad } from '../utils/useLoad'

export default function ReturnsPage() {
  const [page, setPage] = useState(1)
  const { data, loading, error, reload } = useLoad(() => returnsApi.mine({ page }), [page])
  const [busy, setBusy] = useState(null)
  const [actionError, setActionError] = useState('')

  const onCancel = async (id) => {
    if (!window.confirm('Отменить заявку на возврат?')) return
    setBusy(id)
    setActionError('')
    try { await returnsApi.cancel(id); reload() } catch (e) { setActionError(e.message) } finally { setBusy(null) }
  }

  return (
    <div className="container page">
      <h1>Мои возвраты</h1>
      <ErrorMessage error={error || (actionError && new Error(actionError))} onRetry={error ? reload : undefined} />
      {loading && !data ? <Loader /> : data && (
        data.count === 0 ? (
          <EmptyState icon="↩️" title="Возвратов нет"
                      text="Вернуть полученный товар можно в течение 14 дней — кнопка «Вернуть» есть на странице заказа"
                      action={<Link to="/orders" className="btn btn-outline">Мои заказы</Link>} />
        ) : (
          <div className="stack">
            {data.results.map((r) => (
              <article key={r.id} className="card stack">
                <div className="row">
                  <strong>Возврат №{r.id}</strong>
                  <StatusBadge status={r.status} label={r.status_display} />
                  <span className="spacer" />
                  <span className="muted small">{formatDateTime(r.created_at)}</span>
                </div>
                <div>
                  {r.product_name} × {r.quantity} · <span className="muted">{r.seller}</span> ·{' '}
                  <Link to={`/orders/${r.order_id}`}>заказ №{r.order_id}</Link>
                </div>
                <div className="small">Причина: {r.reason_display}{r.description && ` — ${r.description}`}</div>
                {r.manager_comment && <div className="alert small">Комментарий менеджера: {r.manager_comment}</div>}
                <div className="row">
                  <span>{r.status === 'completed' ? 'Возвращено' : 'К возврату'}:{' '}
                    <strong>{formatMoney(r.status === 'completed' ? r.refund_amount : r.amount)}</strong></span>
                  <span className="spacer" />
                  {r.status === 'requested' && (
                    <button className="btn btn-danger btn-sm" disabled={busy === r.id} onClick={() => onCancel(r.id)}>Отменить заявку</button>
                  )}
                </div>
              </article>
            ))}
            <Pagination page={page} count={data.count} onChange={setPage} />
          </div>
        )
      )}
    </div>
  )
}
