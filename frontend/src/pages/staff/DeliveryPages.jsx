/** Кабинеты курьера и сотрудника пункта выдачи. Код получения им не показывается — его называет покупатель. */
import { useState } from 'react'
import { courierApi, pickupApi } from '../../api'
import { EmptyState, ErrorMessage, Loader, Modal, Pagination, StatusBadge } from '../../components/ui'
import { formatDate, formatDateTime } from '../../utils/format'
import { useLoad } from '../../utils/useLoad'
import styles from '../cabinet.module.css'

/** Окно ввода 6-значного кода от покупателя */
function CodeModal({ title, onClose, onSubmit }) {
  const [code, setCode] = useState('')
  const [state, setState] = useState({ busy: false, error: '' })
  const submit = async (e) => {
    e.preventDefault()
    setState({ busy: true, error: '' })
    try {
      await onSubmit(code)
    } catch (err) {
      setState({ busy: false, error: err.message })
    }
  }
  return (
    <Modal title={title} onClose={onClose}>
      <form className="stack" onSubmit={submit}>
        <div className="field">
          <label htmlFor="code">Код получения (назовёт покупатель)</label>
          <input id="code" className="input" inputMode="numeric" pattern="\d{6}" maxLength={6} required autoFocus
                 style={{ fontSize: 28, letterSpacing: 8, textAlign: 'center' }}
                 value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))} />
        </div>
        {state.error && <div className="alert alert-error">{state.error}</div>}
        <button className="btn btn-primary btn-lg" disabled={state.busy || code.length !== 6}>Подтвердить вручение</button>
      </form>
    </Modal>
  )
}

function FailModal({ onClose, onSubmit }) {
  const [comment, setComment] = useState('')
  const [state, setState] = useState({ busy: false, error: '' })
  const submit = async (e) => {
    e.preventDefault()
    setState({ busy: true, error: '' })
    try { await onSubmit(comment) } catch (err) { setState({ busy: false, error: err.message }) }
  }
  return (
    <Modal title="Не удалось вручить" onClose={onClose}>
      <form className="stack" onSubmit={submit}>
        <div className="alert small">Посылка вернётся на склад, покупателю вернутся деньги за эту часть заказа.</div>
        <textarea className="textarea" required placeholder="Что случилось? Например: не открыли дверь, телефон недоступен"
                  value={comment} onChange={(e) => setComment(e.target.value)} />
        {state.error && <div className="alert alert-error">{state.error}</div>}
        <button className="btn btn-danger" disabled={state.busy}>Вернуть на склад</button>
      </form>
    </Modal>
  )
}

/** Карточка посылки — общая для курьера и ПВЗ */
function DeliveryCard({ d, children }) {
  return (
    <article className="card stack">
      <div className="row">
        <strong>Посылка №{d.id}</strong>
        <StatusBadge status={d.status} label={d.status_display} />
        <span className="muted small">заказ №{d.order_id} · {d.seller} · {d.items_count} шт.</span>
      </div>
      <div className={styles.formGrid}>
        <div>
          <div className="small muted">{d.delivery_type === 'pickup' ? 'В пункт выдачи' : 'Адрес доставки'}</div>
          <strong>{d.delivery_type === 'pickup' ? d.pickup_point : d.address}</strong>
        </div>
        <div>
          <div className="small muted">Получатель</div>
          <strong>{d.recipient.name}</strong>
          {d.recipient.phone && <div><a href={`tel:${d.recipient.phone}`}>{d.recipient.phone}</a></div>}
        </div>
      </div>
      {d.storage_until && d.status === 'at_pickup_point' && (
        <span className="small">Хранится до <strong>{formatDate(d.storage_until)}</strong>
          {new Date(d.storage_until) < new Date() && <span className="badge badge-danger" style={{ marginLeft: 8 }}>срок истёк</span>}
        </span>
      )}
      {children && <div className="row">{children}</div>}
    </article>
  )
}

// ---------- Курьер ----------

export function CourierPage({ available = false }) {
  const [status, setStatus] = useState('')
  const [page, setPage] = useState(1)
  const load = available ? () => courierApi.available({ page }) : () => courierApi.mine({ status, page })
  const { data, loading, error, reload } = useLoad(load, [available, status, page])
  const [modal, setModal] = useState(null)
  const [busy, setBusy] = useState(null)
  const [notice, setNotice] = useState({ text: '', error: false })

  const run = async (id, request, text) => {
    setBusy(id)
    setNotice({ text: '', error: false })
    try {
      await request()
      setModal(null)
      setNotice({ text, error: false })
      reload()
    } catch (e) {
      setNotice({ text: e.message, error: true })
    } finally {
      setBusy(null)
    }
  }

  return (
    <>
      <div className={styles.head}><h1>{available ? 'Свободные посылки' : 'Мои доставки'}</h1></div>
      {available
        ? <p className="muted small" style={{ margin: 0 }}>Собранные на складе посылки без курьера. Возьмите — и они появятся в «Моих доставках».</p>
        : (
          <div className={styles.toolbar}>
            {[['', 'Активные'], ['delivered', 'Доставленные'], ['returned', 'Не вручённые']].map(([value, label]) => (
              <button key={value} className={`btn btn-sm ${status === value ? 'btn-primary' : 'btn-outline'}`}
                      onClick={() => { setStatus(value); setPage(1) }}>{label}</button>
            ))}
          </div>
        )}
      {notice.text && <div className={`alert ${notice.error ? 'alert-error' : 'alert-success'}`}>{notice.text}</div>}
      <ErrorMessage error={error} onRetry={reload} />
      {loading && !data ? <Loader /> : data && (
        data.count === 0 ? <EmptyState icon="🚚" title={available ? 'Свободных посылок нет' : 'Доставок нет'} /> : (
          <div className="stack">
            {data.results.map((d) => (
              <DeliveryCard key={d.id} d={d}>
                {available && (
                  <button className="btn btn-primary" disabled={busy === d.id}
                          onClick={() => run(d.id, () => courierApi.take(d.id), `Посылка №${d.id} ваша — заберите её на складе`)}>Взять</button>
                )}
                {!available && d.status === 'assigned' && (
                  <button className="btn btn-primary" disabled={busy === d.id}
                          onClick={() => run(d.id, () => courierApi.pickUp(d.id), `Посылка №${d.id} в пути`)}>Забрал со склада</button>
                )}
                {!available && d.status === 'in_transit' && d.delivery_type === 'courier' && (
                  <>
                    <button className="btn btn-primary" onClick={() => setModal({ type: 'code', d })}>Вручить по коду</button>
                    <button className="btn btn-danger" onClick={() => setModal({ type: 'fail', d })}>Не удалось вручить</button>
                  </>
                )}
                {!available && d.status === 'in_transit' && d.delivery_type === 'pickup' && (
                  <span className="muted small">Отвезите в пункт выдачи — его сотрудник примет посылку</span>
                )}
                {d.delivered_at && <span className="muted small">Вручена {formatDateTime(d.delivered_at)}</span>}
              </DeliveryCard>
            ))}
            <Pagination page={page} count={data.count} onChange={setPage} />
          </div>
        )
      )}
      {modal?.type === 'code' && (
        <CodeModal title={`Вручение посылки №${modal.d.id}`} onClose={() => setModal(null)}
                   onSubmit={(code) => courierApi.handOver(modal.d.id, code).then(() => {
                     setModal(null); setNotice({ text: `Посылка №${modal.d.id} вручена`, error: false }); reload()
                   })} />
      )}
      {modal?.type === 'fail' && (
        <FailModal onClose={() => setModal(null)}
                   onSubmit={(comment) => run(modal.d.id, () => courierApi.fail(modal.d.id, comment), `Посылка №${modal.d.id} возвращается на склад`)} />
      )}
    </>
  )
}

// ---------- Пункт выдачи ----------

export function PickupPage() {
  const [status, setStatus] = useState('')
  const [code, setCode] = useState('')
  const [query, setQuery] = useState({})
  // Поиск по коду — без фильтра статуса (иначе на вкладке «Выданы» хранящуюся посылку не найти)
  const { data, loading, error, reload } = useLoad(() => pickupApi.list(query.code ? query : { status }), [status, JSON.stringify(query)])
  const [modal, setModal] = useState(null)
  const [notice, setNotice] = useState({ text: '', error: false })

  const act = async (request, text) => {
    setNotice({ text: '', error: false })
    try { await request(); setNotice({ text, error: false }); reload() } catch (e) { setNotice({ text: e.message, error: true }) }
  }

  return (
    <>
      <div className={styles.head}>
        <h1>Пункт выдачи</h1><span className="spacer" />
        <button className="btn btn-outline btn-sm" onClick={() => act(async () => {
          const r = await pickupApi.returnExpired()
          if (!r.returned) throw new Error('Просроченных посылок нет')
        }, 'Просроченные посылки отправлены обратно на склад')}>Вернуть просроченные</button>
      </div>
      <form className={styles.toolbar} onSubmit={(e) => { e.preventDefault(); setQuery(code ? { code } : {}) }}>
        <input className="input" inputMode="numeric" maxLength={6} placeholder="Код получения" value={code}
               onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))} aria-label="Поиск по коду" />
        <button className="btn btn-primary">Найти по коду</button>
        {query.code && <button type="button" className="btn btn-ghost" onClick={() => { setCode(''); setQuery({}) }}>Сбросить</button>}
        <span className="spacer" />
        {!query.code && [['', 'Едут и хранятся'], ['in_transit', 'Едут к нам'], ['at_pickup_point', 'Хранятся'], ['delivered', 'Выданы']].map(([value, label]) => (
          <button key={value} type="button" className={`btn btn-sm ${status === value ? 'btn-primary' : 'btn-outline'}`}
                  onClick={() => setStatus(value)}>{label}</button>
        ))}
      </form>
      {notice.text && <div className={`alert ${notice.error ? 'alert-error' : 'alert-success'}`}>{notice.text}</div>}
      <ErrorMessage error={error} onRetry={reload} />
      {loading && !data ? <Loader /> : data && (
        data.count === 0
          ? <EmptyState icon="🏪" title={query.code ? 'Посылки с таким кодом в пункте нет' : 'Посылок нет'}
                        text={query.code ? 'Проверьте код или посылка ещё не прибыла' : 'Посылки появятся, когда курьер повезёт их в ваш пункт'} />
          : (
            <div className="stack">
              {data.results.map((d) => (
                <DeliveryCard key={d.id} d={d}>
                  {d.status === 'in_transit' && (
                    <button className="btn btn-primary" onClick={() => act(() => pickupApi.accept(d.id), `Посылка №${d.id} принята на хранение`)}>
                      Посылка прибыла
                    </button>
                  )}
                  {d.status === 'at_pickup_point' && (
                    <button className="btn btn-primary" onClick={() => setModal(d)}>Выдать по коду</button>
                  )}
                </DeliveryCard>
              ))}
            </div>
          )
      )}
      {modal && (
        <CodeModal title={`Выдача посылки №${modal.id}`} onClose={() => setModal(null)}
                   onSubmit={(c) => pickupApi.issue(modal.id, c).then(() => {
                     setModal(null); setNotice({ text: `Посылка №${modal.id} выдана`, error: false }); setQuery({}); setCode(''); reload()
                   })} />
      )}
    </>
  )
}
