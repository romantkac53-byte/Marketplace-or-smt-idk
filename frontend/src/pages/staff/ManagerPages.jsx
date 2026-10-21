/** Кабинет менеджера: магазины, доставки, модерация отзывов, возвраты, акции площадки. */
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { catalogApi, managerApi } from '../../api'
import { EmptyState, ErrorMessage, Loader, Modal, Pagination, Rating, StatusBadge } from '../../components/ui'
import { formatDate, formatDateTime, formatMoney } from '../../utils/format'
import { useLoad } from '../../utils/useLoad'
import { PromotionsBoard } from '../seller/SellerPromotionsPage'
import styles from '../cabinet.module.css'

/** Вкладки-фильтры над списком */
function Tabs({ items, value, onChange }) {
  return (
    <div className={styles.toolbar}>
      {items.map(([v, label]) => (
        <button key={v} className={`btn btn-sm ${value === v ? 'btn-primary' : 'btn-outline'}`} onClick={() => onChange(v)}>{label}</button>
      ))}
    </div>
  )
}

/** Список с фильтром-вкладками и страницами: { data, loading, error, reload, tab, setTab, page, setPage } */
function useFilteredList(loader, initialTab) {
  const [tab, setTab] = useState(initialTab)
  const [page, setPage] = useState(1)
  const list = useLoad(() => loader(tab, page), [tab, page])
  return { ...list, tab, setTab: (v) => { setTab(v); setPage(1) }, page, setPage }
}

function Notice({ notice }) {
  return notice.text ? <div className={`alert ${notice.error ? 'alert-error' : 'alert-success'}`}>{notice.text}</div> : null
}

/** Действие → сообщение + перезагрузка списка */
function useAct(reload) {
  const [notice, setNotice] = useState({ text: '', error: false })
  const act = async (request, text) => {
    setNotice({ text: '', error: false })
    try { await request(); setNotice({ text, error: false }); reload() } catch (e) { setNotice({ text: e.message, error: true }) }
  }
  return { notice, act }
}

// ---------- Магазины ----------

const SELLER_ACTIONS = {
  pending: [['active', 'Одобрить', 'btn-primary']],
  active: [['suspended', 'Приостановить', 'btn-outline'], ['blocked', 'Заблокировать', 'btn-danger']],
  suspended: [['active', 'Возобновить', 'btn-primary'], ['blocked', 'Заблокировать', 'btn-danger']],
  blocked: [['active', 'Разблокировать', 'btn-outline']],
}
const SELLER_TONE = { pending: 'warning', active: 'success', suspended: 'warning', blocked: 'danger' }
const SELLER_STATUS = { active: 'Активен', suspended: 'Приостановлен', blocked: 'Заблокирован' }

export function SellersPage() {
  const list = useFilteredList((status, page) => managerApi.sellers({ status, page }), 'pending')
  const { notice, act } = useAct(list.reload)
  return (
    <>
      <div className={styles.head}><h1>Магазины</h1></div>
      <Tabs value={list.tab} onChange={list.setTab}
            items={[['pending', 'Заявки на проверку'], ['active', 'Работают'], ['suspended', 'Приостановлены'], ['blocked', 'Заблокированы'], ['', 'Все']]} />
      <p className="muted small" style={{ margin: 0 }}>Товары неодобренных, приостановленных и заблокированных магазинов не показываются в каталоге.</p>
      <Notice notice={notice} />
      <ErrorMessage error={list.error} onRetry={list.reload} />
      {list.loading && !list.data ? <Loader /> : list.data && (
        list.data.count === 0 ? <EmptyState icon="🛍️" title="Магазинов нет" text={list.tab === 'pending' ? 'Новых заявок нет' : ''} /> : (
          <div className={`card ${styles.tableWrap}`}>
            <table className="table">
              <thead><tr><th>Магазин</th><th>Владелец</th><th className={styles.num}>Товаров</th><th>Статус</th><th /></tr></thead>
              <tbody>
                {list.data.results.map((s) => (
                  <tr key={s.id}>
                    <td><strong>{s.store_name}</strong></td>
                    <td className="small">{s.owner}<div className="muted">{s.email || s.login}</div></td>
                    <td className={styles.num}>{s.products_count}</td>
                    <td><span className={`badge badge-${SELLER_TONE[s.status]}`}>{s.status_display}</span></td>
                    <td><div className={styles.actions}>
                      {SELLER_ACTIONS[s.status].map(([status, label, cls]) => (
                        <button key={status} className={`btn btn-sm ${cls}`}
                                onClick={() => act(() => managerApi.setSellerStatus(s.id, status), `Магазин «${s.store_name}» теперь: ${SELLER_STATUS[status]}`)}>
                          {label}
                        </button>
                      ))}
                    </div></td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pagination page={list.page} count={list.data.count} onChange={list.setPage} />
          </div>
        )
      )}
    </>
  )
}

// ---------- Доставки и курьеры ----------

function AssignModal({ delivery, onClose, onDone }) {
  const couriers = useLoad(() => managerApi.couriers(), [])
  const [courierId, setCourierId] = useState('')
  const [error, setError] = useState('')
  const submit = async (e) => {
    e.preventDefault()
    try { await managerApi.assignCourier(delivery.id, Number(courierId)); onDone() } catch (err) { setError(err.message) }
  }
  return (
    <Modal title={`Курьер для посылки №${delivery.id}`} onClose={onClose}>
      {couriers.loading ? <Loader /> : (
        <form className="stack" onSubmit={submit}>
          <span className="small">{delivery.delivery_type === 'pickup' ? `В пункт: ${delivery.pickup_point}` : `Адрес: ${delivery.address}`}</span>
          {couriers.data?.length === 0 && <div className="alert alert-error">Курьеров нет — создайте их в разделе «Пользователи»</div>}
          <div className="stack">
            {(couriers.data || []).map((c) => (
              <label key={c.id} className="checkbox">
                <input type="radio" name="courier" required value={c.id} checked={String(courierId) === String(c.id)}
                       onChange={(e) => setCourierId(e.target.value)} />
                {c.name} <span className="muted small">· активных доставок: {c.active_deliveries}</span>
              </label>
            ))}
          </div>
          {error && <div className="alert alert-error">{error}</div>}
          <button className="btn btn-primary" disabled={!courierId}>Назначить</button>
        </form>
      )}
    </Modal>
  )
}

export function DeliveriesPage() {
  const list = useFilteredList((status, page) => managerApi.deliveries({ status, page }), 'pending')
  const [assigning, setAssigning] = useState(null)
  const { notice, act } = useAct(list.reload)
  return (
    <>
      <div className={styles.head}><h1>Доставки</h1></div>
      <Tabs value={list.tab} onChange={list.setTab}
            items={[['pending', 'Ждут курьера'], ['assigned', 'Курьер назначен'], ['in_transit', 'В пути'], ['at_pickup_point', 'В пунктах выдачи'],
                    ['delivered', 'Получены'], ['returned', 'Не получены'], ['', 'Все']]} />
      <Notice notice={notice} />
      <ErrorMessage error={list.error} onRetry={list.reload} />
      {list.loading && !list.data ? <Loader /> : list.data && (
        list.data.count === 0 ? <EmptyState icon="🗺️" title="Доставок нет" /> : (
          <div className={`card ${styles.tableWrap}`}>
            <table className="table">
              <thead><tr><th>Посылка</th><th>Куда</th><th>Получатель</th><th>Курьер</th><th>Статус</th><th /></tr></thead>
              <tbody>
                {list.data.results.map((d) => (
                  <tr key={d.id}>
                    <td>№{d.id}<div className="small muted">заказ №{d.order_id} · {d.seller}</div></td>
                    <td className="small">{d.delivery_type === 'pickup' ? `ПВЗ: ${d.pickup_point}` : d.address}</td>
                    <td className="small">{d.recipient.name}<div className="muted">{d.recipient.phone}</div></td>
                    <td className="small">{d.courier || <span className="muted">—</span>}</td>
                    <td><StatusBadge status={d.status} label={d.status_display} /></td>
                    <td><div className={styles.actions}>
                      {['pending', 'assigned'].includes(d.status) && (
                        <button className="btn btn-sm btn-outline" onClick={() => setAssigning(d)}>{d.courier ? 'Сменить курьера' : 'Назначить курьера'}</button>
                      )}
                    </div></td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pagination page={list.page} count={list.data.count} onChange={list.setPage} />
          </div>
        )
      )}
      {assigning && (
        <AssignModal delivery={assigning} onClose={() => setAssigning(null)}
                     onDone={() => { const d = assigning; setAssigning(null); act(async () => {}, `Курьер для посылки №${d.id} назначен`) }} />
      )}
    </>
  )
}

// ---------- Модерация отзывов ----------

export function ReviewsModerationPage() {
  const list = useFilteredList((published, page) => managerApi.reviews({ is_published: published, page }), '')
  const { notice, act } = useAct(list.reload)
  return (
    <>
      <div className={styles.head}><h1>Модерация отзывов</h1></div>
      <Tabs value={list.tab} onChange={list.setTab} items={[['', 'Все'], ['true', 'Опубликованы'], ['false', 'Скрыты']]} />
      <p className="muted small" style={{ margin: 0 }}>Скрытый отзыв не виден покупателям и не влияет на рейтинг товара.</p>
      <Notice notice={notice} />
      <ErrorMessage error={list.error} onRetry={list.reload} />
      {list.loading && !list.data ? <Loader /> : list.data && (
        list.data.count === 0 ? <EmptyState icon="⭐" title="Отзывов нет" /> : (
          <div className="stack">
            {list.data.results.map((r) => (
              <article key={r.id} className="card stack" style={{ opacity: r.is_published ? 1 : 0.7 }}>
                <div className="row">
                  <Rating value={r.rating} />
                  <strong>{r.author}</strong>
                  <span className="muted small">о товаре <Link to={`/products/${r.product_id}`}>{r.product_name}</Link> · {formatDate(r.created_at)}</span>
                  <span className="spacer" />
                  {r.is_published
                    ? <button className="btn btn-danger btn-sm" onClick={() => act(() => managerApi.hideReview(r.id), 'Отзыв скрыт')}>Скрыть</button>
                    : <button className="btn btn-outline btn-sm" onClick={() => act(() => managerApi.publishReview(r.id), 'Отзыв опубликован')}>Опубликовать</button>}
                </div>
                {r.text ? <p style={{ margin: 0 }}>{r.text}</p> : <span className="muted small">Без текста</span>}
                {r.seller_reply && <div className="alert small">Ответ продавца: {r.seller_reply}</div>}
              </article>
            ))}
            <Pagination page={list.page} count={list.data.count} onChange={list.setPage} />
          </div>
        )
      )}
    </>
  )
}

// ---------- Возвраты ----------

function DecisionModal({ ret, decision, onClose, onDone }) {
  const [comment, setComment] = useState('')
  const [error, setError] = useState('')
  const reject = decision === 'reject'
  const submit = async (e) => {
    e.preventDefault()
    try {
      await (reject ? managerApi.rejectReturn(ret.id, comment) : managerApi.approveReturn(ret.id, comment))
      onDone()
    } catch (err) { setError(err.message) }
  }
  return (
    <Modal title={`${reject ? 'Отклонить' : 'Одобрить'} возврат №${ret.id}`} onClose={onClose}>
      <form className="stack" onSubmit={submit}>
        <span className="small">{ret.product_name} × {ret.quantity} · {formatMoney(ret.amount)} · {ret.reason_display}</span>
        {!reject && <div className="alert small">После одобрения склад примет товар, и деньги вернутся покупателю.</div>}
        <textarea className="textarea" required={reject} value={comment} onChange={(e) => setComment(e.target.value)}
                  placeholder={reject ? 'Причина отказа — её увидит покупатель' : 'Комментарий (необязательно)'} />
        {error && <div className="alert alert-error">{error}</div>}
        <button className={`btn ${reject ? 'btn-danger' : 'btn-primary'}`}>{reject ? 'Отклонить' : 'Одобрить'}</button>
      </form>
    </Modal>
  )
}

export function ManagerReturnsPage() {
  const list = useFilteredList((status, page) => managerApi.returns({ status, page }), 'requested')
  const [deciding, setDeciding] = useState(null)
  const { notice, act } = useAct(list.reload)
  return (
    <>
      <div className={styles.head}><h1>Возвраты</h1></div>
      <Tabs value={list.tab} onChange={list.setTab}
            items={[['requested', 'Ждут решения'], ['approved', 'Одобрены (ждут склад)'], ['completed', 'Завершены'], ['rejected', 'Отклонены'], ['', 'Все']]} />
      <Notice notice={notice} />
      <ErrorMessage error={list.error} onRetry={list.reload} />
      {list.loading && !list.data ? <Loader /> : list.data && (
        list.data.count === 0 ? <EmptyState icon="↩️" title="Заявок нет" /> : (
          <div className="stack">
            {list.data.results.map((r) => (
              <article key={r.id} className="card stack">
                <div className="row">
                  <strong>Возврат №{r.id}</strong>
                  <StatusBadge status={r.status} label={r.status_display} />
                  <span className="muted small">{formatDateTime(r.created_at)}</span>
                  <span className="spacer" />
                  <strong>{formatMoney(r.amount)}</strong>
                </div>
                <span>{r.product_name} × {r.quantity} <span className="muted">· {r.seller} · заказ №{r.order_id}</span></span>
                <span className="small">Причина: <strong>{r.reason_display}</strong>{r.description && ` — ${r.description}`}</span>
                {r.manager_comment && <div className="alert small">Комментарий: {r.manager_comment}</div>}
                {r.status === 'requested' && (
                  <div className="row">
                    <button className="btn btn-primary btn-sm" onClick={() => setDeciding({ ret: r, decision: 'approve' })}>Одобрить</button>
                    <button className="btn btn-danger btn-sm" onClick={() => setDeciding({ ret: r, decision: 'reject' })}>Отклонить</button>
                  </div>
                )}
              </article>
            ))}
            <Pagination page={list.page} count={list.data.count} onChange={list.setPage} />
          </div>
        )
      )}
      {deciding && (
        <DecisionModal {...deciding} onClose={() => setDeciding(null)}
                       onDone={() => { const d = deciding; setDeciding(null); act(async () => {}, `Возврат №${d.ret.id}: ${d.decision === 'reject' ? 'отклонён' : 'одобрен'}`) }} />
      )}
    </>
  )
}

// ---------- Акции площадки ----------

const MANAGER_PROMO_API = {
  list: managerApi.promotions, create: managerApi.createPromotion,
  update: managerApi.updatePromotion, remove: managerApi.deletePromotion,
}

export function ManagerPromotionsPage() {
  return (
    <PromotionsBoard api={MANAGER_PROMO_API} loadProducts={catalogApi.products} title="Акции площадки"
                     emptyScope="На все товары площадки"
                     intro="Здесь и акции всей площадки, и акции магазинов (их можно выключить). Новая акция отсюда — на товары любых магазинов." />
  )
}
