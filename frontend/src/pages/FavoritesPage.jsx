import { Link } from 'react-router-dom'
import { favoritesApi } from '../api'
import ProductCard from '../components/ProductCard'
import { EmptyState, ErrorMessage, Loader } from '../components/ui'
import { useFavorites } from '../context/FavoritesContext'
import { plural } from '../utils/format'
import { useLoad } from '../utils/useLoad'
import catalogStyles from './CatalogPage.module.css'

export default function FavoritesPage() {
  const favorites = useFavorites()
  const { data, loading, error, reload } = useLoad(() => favoritesApi.list(), [])
  // Сняли ♡ на этой странице — карточка сразу исчезает, без перезагрузки
  const visible = (data || []).filter((p) => favorites.has(p.id))

  return (
    <div className="container page">
      <div className="row" style={{ marginBottom: 16 }}>
        <h1 style={{ margin: 0 }}>Избранное</h1>
        {data && <span className="muted">{plural(visible.length, ['товар', 'товара', 'товаров'])}</span>}
      </div>
      <ErrorMessage error={error} onRetry={reload} />
      {loading && !data ? <Loader /> : data && (
        visible.length === 0 ? (
          <EmptyState icon="♡" title="В избранном пусто" text="Нажмите ♡ на товаре, чтобы не потерять его"
                      action={<Link to="/" className="btn btn-primary">В каталог</Link>} />
        ) : (
          <div className={catalogStyles.grid}>
            {visible.map((p) => <ProductCard key={p.id} product={p} />)}
          </div>
        )
      )}
    </div>
  )
}
