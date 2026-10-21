import { useMemo, useState } from 'react'
import { catalogApi, sellerApi } from '../../api'
import { EmptyState, ErrorMessage, Loader, Modal } from '../../components/ui'
import { allCategories, formatDateTime, fromLocalInput, toLocalInput } from '../../utils/format'
import { useLoad } from '../../utils/useLoad'
import styles from '../cabinet.module.css'

function emptyPromotion() {
  const week = new Date(Date.now() + 7 * 24 * 3600 * 1000)
  // starts_at: null — «сразу»: время начала подставит сервер по своим часам
  return { name: '', discount_type: 'percent', value: '', starts_at: null, ends_at: week.toISOString(),
           is_active: true, product_ids: [], category_ids: [] }
}

function CheckList({ items, selected, onChange }) {
  const toggle = (id) => onChange(selected.includes(id) ? selected.filter((x) => x !== id) : [...selected, id])
  return (
    <div className={styles.checkList}>
      {items.length === 0 && <span className="muted small">Пусто</span>}
      {items.map((item) => (
        <label key={item.id} className="checkbox small">
          <input type="checkbox" checked={selected.includes(item.id)} onChange={() => toggle(item.id)} /> {item.label}
        </label>
      ))}
    </div>
  )
}

function PromotionForm({ api, initial, products, categories, emptyScope, onClose, onSaved }) {
  const [form, setForm] = useState(initial)
  const [state, setState] = useState({ busy: false, errors: null, error: '' })
  const set = (name) => (e) => setForm({ ...form, [name]: e.target.type === 'checkbox' ? e.target.checked : e.target.value })

  const onSubmit = async (e) => {
    e.preventDefault()
    setState({ busy: true, errors: null, error: '' })
    const { id, is_running, created_at, ...data } = form // eslint-disable-line no-unused-vars
    if (!data.starts_at) delete data.starts_at // пусто — сервер начнёт акцию сразу
    try {
      onSaved(id ? await api.update(id, data) : await api.create(data))
    } catch (err) {
      const errors = err.data || {}
      setState({ busy: false, errors, error: errors.detail || Object.values(errors).flat().join(' ') || err.message })
    }
  }

  return (
    <Modal title={form.id ? 'Акция' : 'Новая акция'} onClose={onClose}>
      <form className="stack" onSubmit={onSubmit}>
        <div className="field"><label htmlFor="pr-name">Название</label>
          <input id="pr-name" className="input" required value={form.name} onChange={set('name')} placeholder="Например: Неделя скидок" /></div>
        <div className={styles.formGrid}>
          <div className="field"><label htmlFor="pr-type">Тип скидки</label>
            <select id="pr-type" className="select" value={form.discount_type} onChange={set('discount_type')}>
              <option value="percent">Процент</option><option value="fixed">Сумма, ₽</option>
            </select></div>
          <div className="field"><label htmlFor="pr-value">Размер</label>
            <input id="pr-value" className="input" type="number" min="0.01" step="0.01" required value={form.value} onChange={set('value')} /></div>
          <div className="field"><label htmlFor="pr-start">Начало</label>
            <input id="pr-start" className="input" type="datetime-local" required={Boolean(form.id)}
                   value={toLocalInput(form.starts_at)}
                   onChange={(e) => setForm({ ...form, starts_at: fromLocalInput(e.target.value) })} />
            {!form.id && <span className="muted small">Пусто — начнётся сразу</span>}</div>
          <div className="field"><label htmlFor="pr-end">Окончание</label>
            <input id="pr-end" className="input" type="datetime-local" required value={toLocalInput(form.ends_at)}
                   onChange={(e) => setForm({ ...form, ends_at: fromLocalInput(e.target.value) })} /></div>
        </div>
        <div className="field">
          <label>Товары</label>
          <CheckList items={products} selected={form.product_ids} onChange={(ids) => setForm({ ...form, product_ids: ids })} />
        </div>
        <div className="field">
          <label>Категории (вместе с подкатегориями)</label>
          <CheckList items={categories} selected={form.category_ids} onChange={(ids) => setForm({ ...form, category_ids: ids })} />
          <span className="muted small">Ничего не выбрано — {emptyScope.toLowerCase()}</span>
        </div>
        <label className="checkbox"><input type="checkbox" checked={form.is_active} onChange={set('is_active')} /> Включена</label>
        {state.error && <div className="alert alert-error">{state.error}</div>}
        <button className="btn btn-primary" disabled={state.busy}>Сохранить</button>
      </form>
    </Modal>
  )
}

/**
 * Список акций с формой — общий для продавца (акции своего магазина) и менеджера (акции всей площадки).
 * api: { list, create, update, remove }; loadProducts — откуда взять товары для выбора.
 */
export function PromotionsBoard({ api, loadProducts, title, intro, emptyScope }) {
  const { data, loading, error, reload } = useLoad(() => api.list({ page_size: 100 }), [])
  const products = useLoad(() => loadProducts({ page_size: 100 }), [])
  const categories = useLoad(() => catalogApi.categories(), [])
  const [editing, setEditing] = useState(null)
  const [actionError, setActionError] = useState('')

  const productItems = useMemo(() => (products.data?.results || []).map((p) => ({ id: p.id, label: p.name })), [products.data])
  const categoryItems = useMemo(() => (categories.data ? allCategories(categories.data) : []), [categories.data])
  const productNames = Object.fromEntries(productItems.map((p) => [p.id, p.label]))
  const categoryNames = Object.fromEntries(categoryItems.map((c) => [c.id, c.label.replace(/^(— )+/, '')]))

  const onDelete = async (promo) => {
    if (!window.confirm(`Удалить акцию «${promo.name}»?`)) return
    try { await api.remove(promo.id); reload() } catch (e) { setActionError(e.message) }
  }

  return (
    <>
      <div className={styles.head}>
        <h1>{title}</h1><span className="spacer" />
        <button className="btn btn-primary" onClick={() => setEditing(emptyPromotion())}>+ Новая акция</button>
      </div>
      <p className="muted small" style={{ margin: 0 }}>{intro}</p>
      <ErrorMessage error={error || (actionError && new Error(actionError))} onRetry={error ? reload : undefined} />
      {loading && !data ? <Loader /> : data && (
        data.results.length === 0 ? (
          <EmptyState icon="🏷️" title="Акций пока нет" text="Скидка в процентах или рублях на выбранные товары или категории"
                      action={<button className="btn btn-primary" onClick={() => setEditing(emptyPromotion())}>Создать акцию</button>} />
        ) : (
          <div className="stack">
            {data.results.map((promo) => (
              <article key={promo.id} className="card stack">
                <div className="row">
                  <strong>{promo.name}</strong>
                  <span className="badge badge-sale">−{Number(promo.value)}{promo.discount_type === 'percent' ? '%' : ' ₽'}</span>
                  {promo.is_running ? <span className="badge badge-success">Действует</span>
                    : <span className="badge badge-muted">{promo.is_active ? 'Не в сроке' : 'Выключена'}</span>}
                  <span className="spacer" />
                  <button className="btn btn-outline btn-sm" onClick={() => setEditing(promo)}>Изменить</button>
                  <button className="btn btn-ghost btn-sm" onClick={() => onDelete(promo)}>Удалить</button>
                </div>
                <span className="small muted">{formatDateTime(promo.starts_at)} — {formatDateTime(promo.ends_at)}</span>
                <span className="small">
                  {promo.seller_id && <span className="badge badge-muted" style={{ marginRight: 8 }}>акция магазина</span>}
                  {promo.product_ids.length === 0 && promo.category_ids.length === 0 ? emptyScope : [
                    ...promo.product_ids.map((id) => productNames[id] || `товар #${id}`),
                    ...promo.category_ids.map((id) => `категория «${categoryNames[id] || id}»`),
                  ].join(', ')}
                </span>
              </article>
            ))}
          </div>
        )
      )}
      {editing && (
        <PromotionForm api={api} emptyScope={emptyScope} initial={editing} products={productItems} categories={categoryItems} onClose={() => setEditing(null)}
                       onSaved={() => { setEditing(null); reload() }} />
      )}
    </>
  )
}

const SELLER_API = {
  list: sellerApi.promotions, create: sellerApi.createPromotion,
  update: sellerApi.updatePromotion, remove: sellerApi.deletePromotion,
}

export default function SellerPromotionsPage() {
  return (
    <PromotionsBoard api={SELLER_API} loadProducts={sellerApi.products} title="Акции" emptyScope="На все товары магазина"
                     intro="Если на товар действует несколько акций, покупатель получает самую выгодную. Цена фиксируется в заказе в момент покупки." />
  )
}
