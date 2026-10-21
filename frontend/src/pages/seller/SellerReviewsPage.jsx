import { useState } from 'react'
import { Link } from 'react-router-dom'
import { sellerApi } from '../../api'
import { EmptyState, ErrorMessage, Loader, Pagination, Rating } from '../../components/ui'
import { formatDate } from '../../utils/format'
import { useLoad } from '../../utils/useLoad'
import styles from '../cabinet.module.css'

function ReviewCard({ review, onChange }) {
  const [text, setText] = useState(review.seller_reply || '')
  const [editing, setEditing] = useState(!review.seller_reply)
  const [state, setState] = useState({ busy: false, error: '' })

  const onSubmit = async (e) => {
    e.preventDefault()
    setState({ busy: true, error: '' })
    try {
      onChange(await sellerApi.reply(review.id, text))
      setEditing(false)
      setState({ busy: false, error: '' })
    } catch (err) {
      setState({ busy: false, error: err.message })
    }
  }

  return (
    <article className="card stack">
      <div className="row">
        <Rating value={review.rating} />
        <strong>{review.author}</strong>
        <span className="muted small">о товаре <Link to={`/products/${review.product_id}`}>{review.product_name}</Link></span>
        {!review.is_published && <span className="badge badge-muted" title="Скрыт модератором — не влияет на рейтинг">Скрыт</span>}
        <span className="spacer" />
        <span className="muted small">{formatDate(review.created_at)}</span>
      </div>
      {review.text ? <p style={{ margin: 0 }}>{review.text}</p> : <span className="muted small">Без текста — только оценка</span>}

      {editing ? (
        <form className="stack" onSubmit={onSubmit}>
          <textarea className="textarea" required placeholder="Ответ увидят все покупатели" value={text}
                    onChange={(e) => setText(e.target.value)} style={{ minHeight: 70 }} />
          {state.error && <div className="alert alert-error">{state.error}</div>}
          <div className="row">
            <button className="btn btn-primary btn-sm" disabled={state.busy}>Ответить</button>
            {review.seller_reply && <button type="button" className="btn btn-ghost btn-sm" onClick={() => setEditing(false)}>Отмена</button>}
          </div>
        </form>
      ) : (
        <div className="alert small row">
          <span><strong>Ваш ответ:</strong> {review.seller_reply}</span>
          <span className="spacer" />
          <button className="btn btn-ghost btn-sm" onClick={() => setEditing(true)}>Изменить</button>
        </div>
      )}
    </article>
  )
}

export default function SellerReviewsPage() {
  const [page, setPage] = useState(1)
  const [rating, setRating] = useState('')
  const { data, loading, error, reload, setData } = useLoad(() => sellerApi.reviews({ page, rating }), [page, rating])
  const replace = (updated) => setData({ ...data, results: data.results.map((r) => (r.id === updated.id ? updated : r)) })

  return (
    <>
      <div className={styles.head}>
        <h1>Отзывы о товарах</h1><span className="spacer" />
        <select className="select" style={{ width: 'auto' }} value={rating} onChange={(e) => { setRating(e.target.value); setPage(1) }}
                aria-label="Оценка">
          <option value="">Все оценки</option>
          {[5, 4, 3, 2, 1].map((n) => <option key={n} value={n}>{'★'.repeat(n)}</option>)}
        </select>
      </div>
      <ErrorMessage error={error} onRetry={reload} />
      {loading && !data ? <Loader /> : data && (
        data.count === 0 ? <EmptyState icon="⭐" title="Отзывов пока нет" text="Покупатели могут оставить отзыв после получения товара" /> : (
          <div className="stack">
            {data.results.map((r) => <ReviewCard key={r.id} review={r} onChange={replace} />)}
            <Pagination page={page} count={data.count} onChange={setPage} />
          </div>
        )
      )}
    </>
  )
}
