import { useState } from 'react'
import { sellerApi } from '../../api'
import { EmptyState, ErrorMessage, Loader, Pagination, StatusBadge } from '../../components/ui'
import { formatDateTime, formatMoney } from '../../utils/format'
import { useLoad } from '../../utils/useLoad'
import styles from '../cabinet.module.css'

export default function SellerReturnsPage() {
  const [page, setPage] = useState(1)
  const { data, loading, error, reload } = useLoad(() => sellerApi.returns({ page }), [page])

  return (
    <>
      <div className={styles.head}><h1>Возвраты</h1></div>
      <p className="muted small" style={{ margin: 0 }}>
        Заявки рассматривает менеджер площадки, товар принимает склад. Здесь — для информации: что и почему возвращают.
      </p>
      <ErrorMessage error={error} onRetry={reload} />
      {loading && !data ? <Loader /> : data && (
        data.count === 0 ? <EmptyState icon="↩️" title="Возвратов нет" /> : (
          <div className={`card ${styles.tableWrap}`}>
            <table className="table">
              <thead><tr><th>Дата</th><th>Товар</th><th className={styles.num}>Кол-во</th><th>Причина</th>
                <th>Статус</th><th className={styles.num}>Сумма</th></tr></thead>
              <tbody>
                {data.results.map((r) => (
                  <tr key={r.id}>
                    <td className="small">{formatDateTime(r.created_at)}<div className="muted">заказ №{r.order_id}</div></td>
                    <td>{r.product_name}</td>
                    <td className={styles.num}>{r.quantity}</td>
                    <td className="small">{r.reason_display}{r.description && <div className="muted">{r.description}</div>}</td>
                    <td><StatusBadge status={r.status} label={r.status_display} />
                      {r.manager_comment && <div className="muted small">{r.manager_comment}</div>}</td>
                    <td className={styles.num}>{formatMoney(r.status === 'completed' ? r.refund_amount : r.amount)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pagination page={page} count={data.count} onChange={setPage} />
          </div>
        )
      )}
    </>
  )
}
