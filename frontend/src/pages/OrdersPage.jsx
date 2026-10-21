import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ordersApi } from '../api'
import { EmptyState, ErrorMessage, Loader, Pagination, StatusBadge } from '../components/ui'
import { formatDateTime, formatMoney, plural } from '../utils/format'
import { useLoad } from '../utils/useLoad'
import styles from './OrdersPage.module.css'

const FILTERS = [['', 'Все'], ['new', 'Ждут оплаты'], ['paid', 'В работе'], ['completed', 'Выполнены'], ['cancelled', 'Отменены']]

export default function OrdersPage() {
  const [status, setStatus] = useState('')
  const [page, setPage] = useState(1)
  const { data, loading, error, reload } = useLoad(() => ordersApi.list({ status, page }), [status, page])

  return (
    <div className="container page">
      <h1>Мои заказы</h1>
      <div className={styles.filters} role="tablist">
        {FILTERS.map(([value, label]) => (
          <button key={value} role="tab" aria-selected={status === value}
                  className={`btn btn-sm ${status === value ? 'btn-primary' : 'btn-outline'}`}
                  onClick={() => { setStatus(value); setPage(1) }}>{label}</button>
        ))}
      </div>

      <ErrorMessage error={error} onRetry={reload} />
      {loading && !data ? <Loader /> : data && (
        data.results.length === 0 ? (
          <EmptyState icon="📦" title="Заказов нет" text={status ? 'В этом разделе пусто' : 'Самое время что-нибудь выбрать'}
                      action={<Link to="/" className="btn btn-primary">В каталог</Link>} />
        ) : (
          <div className="stack">
            {data.results.map((order) => (
              <Link key={order.id} to={`/orders/${order.id}`} className={`card ${styles.order}`}>
                <div>
                  <strong>Заказ №{order.id}</strong>
                  <div className="muted small">{formatDateTime(order.created_at)}</div>
                </div>
                <StatusBadge status={order.status} label={order.status_display} />
                <span className="muted small">{order.delivery_type_display}</span>
                <span className="muted small">{plural(order.items_count, ['товар', 'товара', 'товаров'])}</span>
                <strong className={styles.sum}>{formatMoney(order.total_amount)}</strong>
                {order.status === 'new' && <span className="badge badge-warning">Оплатите заказ</span>}
              </Link>
            ))}
            <Pagination page={page} count={data.count} onChange={setPage} />
          </div>
        )
      )}
    </div>
  )
}
