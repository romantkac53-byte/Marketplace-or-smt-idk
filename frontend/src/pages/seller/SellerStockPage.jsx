import { useState } from 'react'
import { sellerApi } from '../../api'
import { EmptyState, ErrorMessage, Loader, Pagination } from '../../components/ui'
import { formatDateTime } from '../../utils/format'
import { useLoad } from '../../utils/useLoad'
import styles from '../cabinet.module.css'

const TYPES = [
  ['', 'Все операции'], ['receipt', 'Приход'], ['reserve', 'Резерв под заказ'], ['release', 'Снятие резерва'],
  ['shipment', 'Отгрузка'], ['return', 'Возврат на склад'], ['write_off', 'Списание'], ['inventory', 'Инвентаризация'],
]

const signed = (n) => (n > 0 ? `+${n}` : n === 0 ? '—' : String(n))

export default function SellerStockPage() {
  const [filters, setFilters] = useState({ type: '', product: '', page: 1 })
  const products = useLoad(() => sellerApi.products({ page_size: 100 }), [])
  const { data, loading, error, reload } = useLoad(() => sellerApi.stockMovements(filters), [JSON.stringify(filters)])

  return (
    <>
      <div className={styles.head}><h1>Движение товаров на складе</h1></div>
      <p className="muted small" style={{ margin: 0 }}>
        Товар хранится на складе маркетплейса. Резерв — штуки, обещанные покупателям в ещё не отгруженных заказах.
      </p>
      <div className={styles.toolbar}>
        <select className="select" value={filters.product} onChange={(e) => setFilters({ ...filters, product: e.target.value, page: 1 })}
                aria-label="Товар">
          <option value="">Все товары</option>
          {(products.data?.results || []).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
        <select className="select" value={filters.type} onChange={(e) => setFilters({ ...filters, type: e.target.value, page: 1 })}
                aria-label="Операция">
          {TYPES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
      </div>
      <ErrorMessage error={error} onRetry={reload} />
      {loading && !data ? <Loader /> : data && (
        data.count === 0 ? <EmptyState icon="🏬" title="Движений нет" text="Первая запись появится, когда склад примет поставку" /> : (
          <div className={`card ${styles.tableWrap}`}>
            <table className="table">
              <thead><tr><th>Дата</th><th>Товар</th><th>Операция</th>
                <th className={styles.num}>Остаток</th><th className={styles.num}>Резерв</th>
                <th className={styles.num}>Стало (остаток / резерв)</th><th>Комментарий</th></tr></thead>
              <tbody>
                {data.results.map((m) => (
                  <tr key={m.id}>
                    <td className="small">{formatDateTime(m.created_at)}</td>
                    <td>{m.product_name}</td>
                    <td>{m.type_display}</td>
                    <td className={styles.num} style={{ color: m.stock_delta > 0 ? 'var(--color-success)' : undefined }}>{signed(m.stock_delta)}</td>
                    <td className={styles.num}>{signed(m.reserved_delta)}</td>
                    <td className={styles.num}>{m.stock_after} / {m.reserved_after}</td>
                    <td className="small muted">{m.comment}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pagination page={filters.page} count={data.count} onChange={(page) => setFilters({ ...filters, page })} />
          </div>
        )
      )}
    </>
  )
}
