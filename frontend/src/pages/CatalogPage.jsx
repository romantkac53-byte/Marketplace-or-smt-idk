import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { catalogApi } from '../api'
import ProductCard from '../components/ProductCard'
import { EmptyState, ErrorMessage, Loader, Pagination } from '../components/ui'
import { plural } from '../utils/format'
import { recentProducts } from '../utils/recent'
import { useLoad } from '../utils/useLoad'
import styles from './CatalogPage.module.css'

// Тот же формат, что понимает сервер (catalog/filters.py): ID123456789, «арт. 123456789», 9 цифр
const ARTICLE_QUERY = /^\s*(?:id|ид|арт\.?|артикул)?\s*[:#№]?\s*\d{9}\s*$/i

const SORTS = [
  ['-created_at', 'Сначала новые'],
  ['-sold_count', 'Популярные'],
  ['-rating_avg', 'С высоким рейтингом'],
  ['price', 'Сначала дешёвые'],
  ['-price', 'Сначала дорогие'],
]

/** Найти категорию в дереве и путь до неё (для заголовка «Лекарства → Спреи») */
function findPath(nodes, id, path = []) {
  for (const node of nodes) {
    const current = [...path, node]
    if (String(node.id) === String(id)) return current
    const found = findPath(node.children, id, current)
    if (found) return found
  }
  return null
}

/** «Вы недавно смотрели» — товары в порядке просмотра (последний — первым) */
function RecentlyViewed() {
  const [ids] = useState(recentProducts)
  const { data } = useLoad(() => (ids.length ? catalogApi.products({ ids: ids.join(','), page_size: 12 }) : Promise.resolve(null)), [])
  if (!data?.results.length) return null
  const byId = Object.fromEntries(data.results.map((p) => [p.id, p]))
  const items = ids.map((id) => byId[id]).filter(Boolean) // снятые с продажи API не вернёт — просто пропускаем
  return (
    <section className={styles.recent}>
      <h2 className={styles.recentTitle}>Вы недавно смотрели</h2>
      <div className={styles.recentRow}>
        {items.map((p) => <div key={p.id} className={styles.recentItem}><ProductCard product={p} /></div>)}
      </div>
    </section>
  )
}

function CategoryTree({ nodes, selected, onSelect, depth = 0 }) {
  return (
    <ul className={styles.tree} style={{ paddingLeft: depth ? 14 : 0 }}>
      {nodes.map((node) => (
        <li key={node.id}>
          <button
            className={`${styles.treeItem} ${String(selected) === String(node.id) ? styles.treeActive : ''}`}
            onClick={() => onSelect(node.id)}
          >{node.name}</button>
          {node.children.length > 0 && (
            <CategoryTree nodes={node.children} selected={selected} onSelect={onSelect} depth={depth + 1} />
          )}
        </li>
      ))}
    </ul>
  )
}

export default function CatalogPage() {
  const [params, setParams] = useSearchParams()
  const navigate = useNavigate()
  const [filtersOpen, setFiltersOpen] = useState(false)
  const query = Object.fromEntries(params)
  const page = Number(query.page || 1)

  const categories = useLoad(() => catalogApi.categories(), [])
  const products = useLoad(() => catalogApi.products({ ordering: '-created_at', ...query }), [params.toString()])

  // Поиск по артикулу (ID123456789): товар один — сразу открываем его, как на маркетплейсах
  useEffect(() => {
    const results = products.data?.results
    if (ARTICLE_QUERY.test(query.search || '') && results?.length === 1) {
      navigate(`/products/${results[0].id}`, { replace: true })
    }
  }, [products.data]) // eslint-disable-line react-hooks/exhaustive-deps

  // Поля цены вводятся в форму, а в адрес попадают по кнопке «Применить»
  const [price, setPrice] = useState({ min: query.price_min || '', max: query.price_max || '' })
  useEffect(() => setPrice({ min: query.price_min || '', max: query.price_max || '' }), [query.price_min, query.price_max])

  /** Поменять фильтры в адресе страницы; любая смена фильтра возвращает на 1-ю страницу */
  const update = (changes) => {
    const next = { ...query, page: undefined, ...changes }
    setParams(Object.fromEntries(Object.entries(next).filter(([, v]) => v !== undefined && v !== '' && v !== false)))
  }

  const categoryPath = categories.data && query.category ? findPath(categories.data, query.category) : null
  const isHome = Object.keys(query).every((k) => k === 'ordering' || k === 'page') && page === 1
  const title = query.search
    ? `Поиск: «${query.search}»`
    : categoryPath ? categoryPath.map((c) => c.name).join(' → ') : 'Все товары'

  return (
    <div className="container page">
      <div className={styles.layout}>
        <aside className={`${styles.sidebar} ${filtersOpen ? styles.sidebarOpen : ''}`}>
          <section className="card">
            <h3>Категории</h3>
            <button
              className={`${styles.treeItem} ${!query.category ? styles.treeActive : ''}`}
              onClick={() => update({ category: undefined })}
            >Все товары</button>
            {categories.loading ? <Loader text="" /> : categories.data && (
              <CategoryTree nodes={categories.data} selected={query.category} onSelect={(id) => update({ category: id })} />
            )}
          </section>

          <section className="card stack">
            <h3 style={{ margin: 0 }}>Цена, ₽</h3>
            <form
              className={styles.priceRow}
              onSubmit={(e) => { e.preventDefault(); update({ price_min: price.min, price_max: price.max }) }}
            >
              <input className="input" type="number" min="0" placeholder="от" value={price.min}
                     onChange={(e) => setPrice({ ...price, min: e.target.value })} aria-label="Цена от" />
              <input className="input" type="number" min="0" placeholder="до" value={price.max}
                     onChange={(e) => setPrice({ ...price, max: e.target.value })} aria-label="Цена до" />
              <button className="btn btn-outline btn-block" type="submit">Применить</button>
            </form>
            <label className="checkbox">
              <input type="checkbox" checked={query.in_stock === 'true'}
                     onChange={(e) => update({ in_stock: e.target.checked ? 'true' : undefined })} />
              Только в наличии
            </label>
            {Object.keys(query).some((k) => k !== 'ordering' && k !== 'page') && (
              <button className="btn btn-ghost btn-sm" onClick={() => setParams({})}>Сбросить все фильтры</button>
            )}
          </section>
        </aside>

        <section className={styles.content}>
          {isHome && <RecentlyViewed />}
          <div className={styles.toolbar}>
            <div>
              <h1 style={{ marginBottom: 4 }}>{title}</h1>
              {products.data && (
                <span className="muted">{plural(products.data.count, ['товар', 'товара', 'товаров'])}</span>
              )}
            </div>
            <span className="spacer" />
            <button className={`btn btn-outline ${styles.filtersToggle}`} onClick={() => setFiltersOpen((v) => !v)}>
              Фильтры
            </button>
            <select className="select" style={{ width: 'auto' }} value={query.ordering || '-created_at'}
                    onChange={(e) => update({ ordering: e.target.value })} aria-label="Сортировка">
              {SORTS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </div>

          <ErrorMessage error={products.error} onRetry={products.reload} />
          {products.loading && !products.data ? <Loader /> : products.data && (
            products.data.results.length === 0 ? (
              <EmptyState icon="🔍" title="Ничего не нашлось"
                          text={ARTICLE_QUERY.test(query.search || '') ? 'Товара с таким артикулом нет или он снят с продажи' : 'Попробуйте изменить запрос или сбросить фильтры'}
                          action={<button className="btn btn-outline" onClick={() => setParams({})}>Сбросить фильтры</button>} />
            ) : (
              <>
                <div className={styles.grid} style={{ opacity: products.loading ? 0.6 : 1 }}>
                  {products.data.results.map((p) => <ProductCard key={p.id} product={p} />)}
                </div>
                <Pagination page={page} count={products.data.count} onChange={(p) => {
                  update({ page: p })
                  window.scrollTo({ top: 0, behavior: 'smooth' })
                }} />
              </>
            )
          )}
        </section>
      </div>
    </div>
  )
}
