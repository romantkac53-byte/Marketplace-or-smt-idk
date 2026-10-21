import { useState } from 'react'
import { Link } from 'react-router-dom'
import { sellerApi } from '../../api'
import { ArticleBadge } from '../../components/Extras'
import { EmptyState, ErrorMessage, Loader, Pagination, Price, ProductImage } from '../../components/ui'
import { useLoad } from '../../utils/useLoad'
import styles from '../cabinet.module.css'

export default function SellerProductsPage() {
  const [filters, setFilters] = useState({ search: '', is_active: '', page: 1 })
  const [search, setSearch] = useState('')
  const { data, loading, error, reload } = useLoad(() => sellerApi.products(filters), [JSON.stringify(filters)])
  const [busy, setBusy] = useState(null)
  const [actionError, setActionError] = useState('')

  const toggleActive = async (product) => {
    setBusy(product.id)
    setActionError('')
    try {
      await sellerApi.updateProduct(product.id, { is_active: !product.is_active })
      reload()
    } catch (e) {
      setActionError(e.message)
    } finally {
      setBusy(null)
    }
  }

  return (
    <>
      <div className={styles.head}>
        <h1>Мои товары</h1>
        <span className="spacer" />
        <Link to="/seller/products/new" className="btn btn-primary">+ Добавить товар</Link>
      </div>

      <form className={styles.toolbar} onSubmit={(e) => { e.preventDefault(); setFilters({ ...filters, search, page: 1 }) }}>
        <input className="input" type="search" placeholder="Название или ID артикула" value={search} onChange={(e) => setSearch(e.target.value)} />
        <select className="select" value={filters.is_active} onChange={(e) => setFilters({ ...filters, is_active: e.target.value, page: 1 })}>
          <option value="">Все товары</option>
          <option value="true">В продаже</option>
          <option value="false">Сняты с продажи</option>
        </select>
        <button className="btn btn-outline">Найти</button>
      </form>

      <ErrorMessage error={error || (actionError && new Error(actionError))} onRetry={error ? reload : undefined} />
      {loading && !data ? <Loader /> : data && (
        data.count === 0 ? (
          <EmptyState icon="📦" title="Товаров пока нет" text="Добавьте первый товар — остаток внесёт склад, когда примет поставку"
                      action={<Link to="/seller/products/new" className="btn btn-primary">Добавить товар</Link>} />
        ) : (
          <div className={`card ${styles.tableWrap}`}>
            <table className="table">
              <thead>
                <tr>
                  <th>Товар</th><th>Цена</th>
                  <th className={styles.num}>На складе</th><th className={styles.num}>В резерве</th><th className={styles.num}>Доступно</th>
                  <th>Статус</th><th />
                </tr>
              </thead>
              <tbody>
                {data.results.map((p) => (
                  <tr key={p.id} style={{ opacity: busy === p.id ? 0.5 : 1 }}>
                    <td>
                      <div className={styles.nameCell}>
                        <div className={styles.thumb}><ProductImage src={p.image} alt="" /></div>
                        <div>
                          <Link to={`/seller/products/${p.id}`}>{p.name}</Link>
                          <div><ArticleBadge article={p.article} /></div>
                        </div>
                      </div>
                    </td>
                    <td><Price price={p.price} currentPrice={p.current_price} size="sm" /></td>
                    <td className={styles.num}>{p.stock}</td>
                    <td className={styles.num}>{p.reserved}</td>
                    <td className={styles.num}><strong>{p.available}</strong></td>
                    <td>
                      {p.in_catalog
                        ? <span className="badge badge-success">В каталоге</span>
                        : <span className="badge badge-muted" title={p.is_active ? 'Магазин ещё не одобрен' : ''}>
                            {p.is_active ? 'Ждёт одобрения магазина' : 'Снят с продажи'}
                          </span>}
                    </td>
                    <td>
                      <div className={styles.actions}>
                        <button className="btn btn-ghost btn-sm" disabled={busy === p.id} onClick={() => toggleActive(p)}>
                          {p.is_active ? 'Снять с продажи' : 'Вернуть в продажу'}
                        </button>
                        <Link to={`/seller/products/${p.id}`} className="btn btn-outline btn-sm">Изменить</Link>
                      </div>
                    </td>
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
