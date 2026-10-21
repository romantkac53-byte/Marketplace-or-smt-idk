/** Кабинет сотрудника склада: сборка, остатки и операции, журнал, приёмка возвратов. */
import { useState } from 'react'
import { warehouseApi } from '../../api'
import { EmptyState, ErrorMessage, Loader, Modal, Pagination, StatusBadge } from '../../components/ui'
import { formatDateTime, formatMoney } from '../../utils/format'
import { useLoad } from '../../utils/useLoad'
import styles from '../cabinet.module.css'

/** Кнопка действия над одной записью: блокируется на время запроса, показывает ошибку */
function useAction(onDone) {
  const [busy, setBusy] = useState(null)
  const [error, setError] = useState('')
  const run = async (id, request) => {
    setBusy(id)
    setError('')
    try { onDone(await request()) } catch (e) { setError(e.message) } finally { setBusy(null) }
  }
  return { busy, error, run }
}

// ---------- Сборка ----------

const ASSEMBLY_FILTERS = [['', 'В работе'], ['confirmed', 'Ждут сборки'], ['assembling', 'Собираются'], ['ready', 'Собраны, ждут курьера']]

export function AssemblyPage() {
  const [status, setStatus] = useState('')
  const [page, setPage] = useState(1)
  const { data, loading, error, reload } = useLoad(() => warehouseApi.assembly({ status, page }), [status, page])
  const action = useAction(() => reload())

  return (
    <>
      <div className={styles.head}><h1>Сборка заказов</h1></div>
      <p className="muted small" style={{ margin: 0 }}>Очередь — по времени оплаты: сначала то, что оплатили раньше. Цены и данные покупателя сборщику не нужны.</p>
      <div className={styles.toolbar}>
        {ASSEMBLY_FILTERS.map(([value, label]) => (
          <button key={value} className={`btn btn-sm ${status === value ? 'btn-primary' : 'btn-outline'}`}
                  onClick={() => { setStatus(value); setPage(1) }}>{label}</button>
        ))}
      </div>
      <ErrorMessage error={error || (action.error && new Error(action.error))} onRetry={error ? reload : undefined} />
      {loading && !data ? <Loader /> : data && (
        data.count === 0 ? <EmptyState icon="📋" title="Очередь пуста" text="Подтверждённые продавцами заказы появятся здесь" /> : (
          <div className="stack">
            {data.results.map((so) => (
              <article key={so.id} className="card stack" style={{ opacity: action.busy === so.id ? 0.6 : 1 }}>
                <div className="row">
                  <strong>Заказ №{so.order_id}</strong>
                  <StatusBadge status={so.status} label={so.status_display} />
                  <span className="muted small">{so.seller}</span>
                  <span className="spacer" />
                  <span className="small">{so.delivery_type}{so.pickup_point && `: ${so.pickup_point}`}</span>
                </div>
                <table className="table">
                  <tbody>
                    {so.items.map((i) => (
                      <tr key={i.product_id}><td>{i.product_name}</td><td className={styles.num}><strong>× {i.quantity}</strong></td></tr>
                    ))}
                  </tbody>
                </table>
                <div className="row">
                  <span className="muted small">Оплачен {formatDateTime(so.paid_at)}</span>
                  <span className="spacer" />
                  {so.status === 'confirmed' && (
                    <button className="btn btn-primary" disabled={action.busy === so.id}
                            onClick={() => action.run(so.id, () => warehouseApi.start(so.id))}>Начать сборку</button>
                  )}
                  {so.status === 'assembling' && (
                    <button className="btn btn-primary" disabled={action.busy === so.id}
                            onClick={() => action.run(so.id, () => warehouseApi.ready(so.id))}>Собран — передать курьерам</button>
                  )}
                  {so.status === 'ready' && <span className="badge badge-muted">Ждёт курьера</span>}
                </div>
              </article>
            ))}
            <Pagination page={page} count={data.count} onChange={setPage} />
          </div>
        )
      )}
    </>
  )
}

// ---------- Остатки и операции ----------

const OPERATIONS = [['receipt', 'Приход (поставка)'], ['write_off', 'Списание'], ['inventory', 'Инвентаризация']]

function OperationModal({ product, onClose, onDone }) {
  const [form, setForm] = useState({ type: 'receipt', quantity: '', comment: '' })
  const [state, setState] = useState({ busy: false, error: '' })
  const onSubmit = async (e) => {
    e.preventDefault()
    setState({ busy: true, error: '' })
    try {
      onDone(await warehouseApi.operation({ product_id: product.id, type: form.type, quantity: Number(form.quantity), comment: form.comment }))
    } catch (err) {
      setState({ busy: false, error: err.message })
    }
  }
  const hint = {
    receipt: 'Сколько штук привезли — прибавится к остатку.',
    write_off: `Брак, порча, потеря. Списать можно не больше ${product.available} шт. — остальные зарезервированы под заказы.`,
    inventory: `Сколько насчитали на полке — остаток станет равен этому числу (не меньше резерва: ${product.reserved}).`,
  }[form.type]
  return (
    <Modal title={product.name} onClose={onClose}>
      <form className="stack" onSubmit={onSubmit}>
        <div className={styles.money}>
          <div className={styles.moneyItem}><span className="small muted">На складе</span><strong>{product.stock}</strong></div>
          <div className={styles.moneyItem}><span className="small muted">В резерве</span><strong>{product.reserved}</strong></div>
          <div className={styles.moneyItem}><span className="small muted">Доступно</span><strong>{product.available}</strong></div>
        </div>
        <div className="field">
          <label htmlFor="op-type">Операция</label>
          <select id="op-type" className="select" value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}>
            {OPERATIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
          <span className="muted small">{hint}</span>
        </div>
        <div className="field">
          <label htmlFor="op-qty">{form.type === 'inventory' ? 'Фактический остаток' : 'Количество'}</label>
          <input id="op-qty" className="input" type="number" min={form.type === 'inventory' ? 0 : 1} required
                 value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} />
        </div>
        <div className="field">
          <label htmlFor="op-comment">Комментарий</label>
          <input id="op-comment" className="input" placeholder="Например: накладная №15" value={form.comment}
                 onChange={(e) => setForm({ ...form, comment: e.target.value })} />
        </div>
        {state.error && <div className="alert alert-error">{state.error}</div>}
        <button className="btn btn-primary" disabled={state.busy}>Провести</button>
      </form>
    </Modal>
  )
}

export function StockPage() {
  const [filters, setFilters] = useState({ search: '', low: '', page: 1 })
  const [search, setSearch] = useState('')
  const { data, loading, error, reload } = useLoad(() => warehouseApi.stock(filters), [JSON.stringify(filters)])
  const [selected, setSelected] = useState(null)
  const [notice, setNotice] = useState('')

  return (
    <>
      <div className={styles.head}><h1>Остатки и поставки</h1></div>
      <form className={styles.toolbar} onSubmit={(e) => { e.preventDefault(); setFilters({ ...filters, search, page: 1 }) }}>
        <input className="input" type="search" placeholder="Товар или ID артикула" value={search} onChange={(e) => setSearch(e.target.value)} />
        <select className="select" value={filters.low} onChange={(e) => setFilters({ ...filters, low: e.target.value, page: 1 })}>
          <option value="">Все товары</option>
          <option value="5">Доступно меньше 5</option>
          <option value="20">Доступно меньше 20</option>
        </select>
        <button className="btn btn-outline">Найти</button>
      </form>
      {notice && <div className="alert alert-success">{notice}</div>}
      <ErrorMessage error={error} onRetry={reload} />
      {loading && !data ? <Loader /> : data && (
        data.count === 0 ? <EmptyState icon="🏬" title="Ничего не найдено" /> : (
          <div className={`card ${styles.tableWrap}`}>
            <table className="table">
              <thead><tr><th>Товар</th><th>Магазин</th><th className={styles.num}>На складе</th>
                <th className={styles.num}>Резерв</th><th className={styles.num}>Доступно</th><th /></tr></thead>
              <tbody>
                {data.results.map((p) => (
                  <tr key={p.id}>
                    <td>{p.name}{!p.is_active && <span className="badge badge-muted" style={{ marginLeft: 8 }}>не продаётся</span>}
                      <div className="small muted">арт. {p.article}</div></td>
                    <td className="small muted">{p.seller}</td>
                    <td className={styles.num}>{p.stock}</td>
                    <td className={styles.num}>{p.reserved}</td>
                    <td className={styles.num}><strong style={{ color: p.available < 5 ? 'var(--color-danger)' : undefined }}>{p.available}</strong></td>
                    <td><div className={styles.actions}>
                      <button className="btn btn-outline btn-sm" onClick={() => { setSelected(p); setNotice('') }}>Операция</button>
                    </div></td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pagination page={filters.page} count={data.count} onChange={(page) => setFilters({ ...filters, page })} />
          </div>
        )
      )}
      {selected && (
        <OperationModal product={selected} onClose={() => setSelected(null)} onDone={(movement) => {
          setSelected(null)
          setNotice(`${movement.type_display}: «${movement.product_name}» — теперь на складе ${movement.stock_after}, в резерве ${movement.reserved_after}`)
          reload()
        }} />
      )}
    </>
  )
}

// ---------- Журнал ----------

const TYPES = [
  ['', 'Все операции'], ['receipt', 'Приход'], ['reserve', 'Резерв'], ['release', 'Снятие резерва'], ['shipment', 'Отгрузка'],
  ['return', 'Возврат'], ['write_off', 'Списание'], ['inventory', 'Инвентаризация'],
]
const signed = (n) => (n > 0 ? `+${n}` : n === 0 ? '—' : String(n))

export function MovementsPage() {
  const [filters, setFilters] = useState({ type: '', page: 1 })
  const { data, loading, error, reload } = useLoad(() => warehouseApi.movements(filters), [JSON.stringify(filters)])
  return (
    <>
      <div className={styles.head}><h1>Журнал склада</h1><span className="spacer" />
        <select className="select" style={{ width: 'auto' }} value={filters.type} aria-label="Операция"
                onChange={(e) => setFilters({ type: e.target.value, page: 1 })}>
          {TYPES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
      </div>
      <ErrorMessage error={error} onRetry={reload} />
      {loading && !data ? <Loader /> : data && (
        <div className={`card ${styles.tableWrap}`}>
          <table className="table">
            <thead><tr><th>Дата</th><th>Товар</th><th>Операция</th><th className={styles.num}>Остаток</th>
              <th className={styles.num}>Резерв</th><th className={styles.num}>Стало</th><th>Комментарий</th></tr></thead>
            <tbody>
              {data.results.map((m) => (
                <tr key={m.id}>
                  <td className="small">{formatDateTime(m.created_at)}</td><td>{m.product_name}</td><td>{m.type_display}</td>
                  <td className={styles.num}>{signed(m.stock_delta)}</td><td className={styles.num}>{signed(m.reserved_delta)}</td>
                  <td className={styles.num}>{m.stock_after} / {m.reserved_after}</td><td className="small muted">{m.comment}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <Pagination page={filters.page} count={data.count} onChange={(page) => setFilters({ ...filters, page })} />
        </div>
      )}
    </>
  )
}

// ---------- Приёмка возвратов ----------

export function WarehouseReturnsPage() {
  const { data, loading, error, reload } = useLoad(() => warehouseApi.returns(), [])
  const [notice, setNotice] = useState('')
  const action = useAction((r) => { setNotice(`Возврат №${r.id} принят: ${formatMoney(r.refund_amount)} возвращено покупателю`); reload() })
  return (
    <>
      <div className={styles.head}><h1>Приёмка возвратов</h1></div>
      <p className="muted small" style={{ margin: 0 }}>Возвраты, одобренные менеджером. При приёмке товар возвращается на склад (брак — сразу списывается), деньги — покупателю.</p>
      {notice && <div className="alert alert-success">{notice}</div>}
      <ErrorMessage error={error || (action.error && new Error(action.error))} onRetry={error ? reload : undefined} />
      {loading && !data ? <Loader /> : data && (
        data.count === 0 ? <EmptyState icon="📥" title="Нечего принимать" /> : (
          <div className="stack">
            {data.results.map((r) => (
              <article key={r.id} className="card row">
                <div>
                  <strong>Возврат №{r.id}</strong> · {r.product_name} × {r.quantity}
                  <div className="small muted">{r.seller} · заказ №{r.order_id} · причина: {r.reason_display}{r.description && ` — ${r.description}`}</div>
                </div>
                <span className="spacer" />
                {r.reason === 'defect' && <span className="badge badge-danger">Брак — будет списан</span>}
                <button className="btn btn-primary" disabled={action.busy === r.id}
                        onClick={() => action.run(r.id, () => warehouseApi.acceptReturn(r.id))}>Товар принят</button>
              </article>
            ))}
          </div>
        )
      )}
    </>
  )
}
