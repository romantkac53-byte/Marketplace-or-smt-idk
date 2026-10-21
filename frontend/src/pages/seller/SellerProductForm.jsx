import { useEffect, useMemo, useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { catalogApi, sellerApi } from '../../api'
import { ArticleBadge } from '../../components/Extras'
import { BackLink, ErrorMessage, Loader, Modal, ProductImage } from '../../components/ui'
import { useToast } from '../../context/ToastContext'
import { leafCategories } from '../../utils/format'
import { useLoad } from '../../utils/useLoad'
import styles from '../cabinet.module.css'

const MAX_PHOTOS = 10 // как на сервере: главное + до 9 дополнительных

const EMPTY = { name: '', description: '', category_id: '', price: '', is_active: true, characteristics: [] }

function FieldError({ errors, name }) {
  const messages = errors?.[name]
  return messages ? <span className="field-error">{[].concat(messages).map((m) => (typeof m === 'string' ? m : JSON.stringify(m))).join(' ')}</span> : null
}

/** Окно «новая характеристика» — если нужной нет в справочнике */
function NewCharacteristic({ onClose, onCreated }) {
  const [form, setForm] = useState({ name: '', unit: '' })
  const [error, setError] = useState('')
  const onSubmit = async (e) => {
    e.preventDefault()
    try {
      onCreated(await sellerApi.createCharacteristic(form))
    } catch (err) {
      setError(err.message)
    }
  }
  return (
    <Modal title="Новая характеристика" onClose={onClose}>
      <form className="stack" onSubmit={onSubmit}>
        <div className="field"><label htmlFor="ch-name">Название</label>
          <input id="ch-name" className="input" required placeholder="Например: Объём" value={form.name}
                 onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
        <div className="field"><label htmlFor="ch-unit">Единица измерения</label>
          <input id="ch-unit" className="input" placeholder="мл, г, см… (необязательно)" value={form.unit}
                 onChange={(e) => setForm({ ...form, unit: e.target.value })} /></div>
        {error && <div className="alert alert-error">{error}</div>}
        <button className="btn btn-primary">Добавить в справочник</button>
      </form>
    </Modal>
  )
}

export default function SellerProductForm() {
  const { id } = useParams()
  const isNew = !id
  const navigate = useNavigate()
  const location = useLocation()
  const toast = useToast()
  const categories = useLoad(() => catalogApi.categories(), [])
  const characteristics = useLoad(() => sellerApi.characteristics(), [])
  const product = useLoad(() => (isNew ? Promise.resolve(null) : sellerApi.product(id)), [id])
  const [form, setForm] = useState(EMPTY)
  const [state, setState] = useState({
    busy: false, errors: null, error: '',
    saved: location.state?.created ? 'Товар создан. Загрузите фото — а остаток внесёт склад при поставке.' : '',
  })
  const [newCharOpen, setNewCharOpen] = useState(false)

  const leaves = useMemo(() => (categories.data ? leafCategories(categories.data) : []), [categories.data])

  // Загрузили товар — заполняем форму
  useEffect(() => {
    if (!product.data) return
    const p = product.data
    setForm({
      name: p.name, description: p.description, category_id: p.category_id, price: p.price, is_active: p.is_active,
      characteristics: p.characteristics.map((c) => ({ characteristic_id: c.characteristic_id, value: c.value })),
    })
  }, [product.data])

  if (categories.loading || characteristics.loading || product.loading) return <Loader />
  if (product.error) return <ErrorMessage error={product.error} />

  const set = (name) => (e) => setForm({ ...form, [name]: e.target.type === 'checkbox' ? e.target.checked : e.target.value })
  const setChar = (index, changes) => setForm({
    ...form, characteristics: form.characteristics.map((c, i) => (i === index ? { ...c, ...changes } : c)),
  })
  const usedChars = new Set(form.characteristics.map((c) => String(c.characteristic_id)))

  const onSubmit = async (e) => {
    e.preventDefault()
    setState({ busy: true, errors: null, error: '', saved: '' })
    const data = {
      ...form,
      category_id: Number(form.category_id),
      characteristics: form.characteristics.filter((c) => c.characteristic_id && c.value.trim())
        .map((c) => ({ characteristic_id: Number(c.characteristic_id), value: c.value.trim() })),
    }
    try {
      if (isNew) {
        const created = await sellerApi.createProduct(data)
        // Сразу на страницу редактирования — там можно загрузить фото
        navigate(`/seller/products/${created.id}`, { replace: true, state: { created: true } })
      } else {
        product.setData(await sellerApi.updateProduct(id, data))
        setState({ busy: false, errors: null, error: '', saved: '' })
        toast('Изменения сохранены')
      }
    } catch (err) {
      setState({ busy: false, errors: err.data, error: err.data?.detail || (err.data ? 'Проверьте поля формы' : err.message), saved: '' })
    }
  }

  const onImage = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    setState({ ...state, busy: true, error: '' })
    try {
      product.setData(await sellerApi.uploadImage(id, file))
      setState({ busy: false, errors: null, error: '', saved: '' })
      toast('Главное фото обновлено')
    } catch (err) {
      setState({ busy: false, errors: null, error: err.message, saved: '' })
    }
    e.target.value = ''
  }

  /** Действие с галереей: сервер возвращает товар целиком — показываем ответ и всплывающее уведомление */
  const photoAction = async (request, text) => {
    setState({ ...state, busy: true, error: '' })
    try {
      product.setData(await request())
      setState({ busy: false, errors: null, error: '', saved: '' })
      toast(text)
    } catch (err) {
      setState({ busy: false, errors: null, error: err.message, saved: '' })
    }
  }

  const onDelete = async () => {
    if (!window.confirm('Удалить товар? Это нельзя отменить.')) return
    try {
      await sellerApi.deleteProduct(id)
      navigate('/seller/products', { replace: true })
    } catch (err) {
      setState({ ...state, error: err.message, saved: '' })
    }
  }

  const p = product.data
  const photoCount = p ? (p.image ? 1 : 0) + p.gallery.length : 0
  return (
    <>
      <BackLink to="/seller/products">Мои товары</BackLink>
      <div className={styles.head}>
        <h1>{isNew ? 'Новый товар' : p.name}</h1>
        {p && <ArticleBadge article={p.article} />}
        {p && (p.in_catalog ? <span className="badge badge-success">В каталоге</span> : <span className="badge badge-muted">Не виден покупателям</span>)}
      </div>
      {state.saved && <div className="alert alert-success">{state.saved}</div>}
      {state.error && <div className="alert alert-error">{state.error}</div>}

      {p && (
        <section className="card stack">
          <div className="row">
            <h3 style={{ margin: 0 }}>Фото</h3>
            <span className="muted small">{photoCount} из {MAX_PHOTOS} · первое — главное, его видно в каталоге</span>
          </div>
          <div className={styles.photoGrid}>
            {p.image && (
              <figure className={styles.photo}>
                <ProductImage src={p.image} alt={`${p.name} — главное фото`} />
                <span className={`badge ${styles.photoBadge}`}>Главное</span>
                <label className={`btn btn-ghost btn-sm ${styles.photoAction}`}>
                  Заменить
                  <input type="file" accept="image/*" hidden onChange={onImage} disabled={state.busy} />
                </label>
              </figure>
            )}
            {p.gallery.map((photo) => (
              <figure key={photo.id} className={styles.photo}>
                <ProductImage src={photo.image} alt="" />
                <div className={styles.photoActions}>
                  <button type="button" className="btn btn-ghost btn-sm" disabled={state.busy}
                          onClick={() => photoAction(() => sellerApi.makeCover(id, photo.id), 'Главное фото изменено')}>Сделать главным</button>
                  <button type="button" className="btn btn-ghost btn-sm" disabled={state.busy} aria-label="Удалить фото"
                          onClick={() => photoAction(() => sellerApi.deletePhoto(id, photo.id), 'Фото удалено')}>✕</button>
                </div>
              </figure>
            ))}
            {photoCount < MAX_PHOTOS && (
              <label className={styles.photoAdd}>
                <span aria-hidden="true" style={{ fontSize: 28 }}>＋</span>
                <span>Добавить фото</span>
                <span className="muted small">можно несколько</span>
                <input type="file" accept="image/*" multiple hidden disabled={state.busy}
                       onChange={(e) => {
                         const files = [...e.target.files]
                         e.target.value = ''
                         if (files.length) photoAction(() => sellerApi.addPhotos(id, files), `Загружено фото: ${files.length}`)
                       }} />
              </label>
            )}
          </div>
        </section>
      )}

      {p && (
        <section className="card">
          <h3>Остатки</h3>
          <div className={styles.money}>
            <div className={styles.moneyItem}><span className="small muted">На складе</span><strong>{p.stock}</strong></div>
            <div className={styles.moneyItem}><span className="small muted">В резерве под заказы</span><strong>{p.reserved}</strong></div>
            <div className={styles.moneyItem}><span className="small muted">Доступно к покупке</span><strong>{p.available}</strong></div>
          </div>
          <p className="muted small" style={{ margin: '12px 0 0' }}>Остаток меняет склад маркетплейса: при приёмке поставки, списании и инвентаризации.</p>
        </section>
      )}

      <form className="card stack" onSubmit={onSubmit}>
        <h3 style={{ margin: 0 }}>Описание товара</h3>
        <div className={styles.formGrid}>
          <div className={`field ${styles.wide}`}>
            <label htmlFor="pf-name">Название</label>
            <input id="pf-name" className="input" required value={form.name} onChange={set('name')} />
            <FieldError errors={state.errors} name="name" />
          </div>
          <div className="field">
            <label htmlFor="pf-category">Категория</label>
            <select id="pf-category" className="select" required value={form.category_id} onChange={set('category_id')}>
              <option value="">Выберите…</option>
              {leaves.map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}
            </select>
            <FieldError errors={state.errors} name="category_id" />
          </div>
          <div className="field">
            <label htmlFor="pf-price">Цена, ₽</label>
            <input id="pf-price" className="input" type="number" min="0" step="0.01" required value={form.price} onChange={set('price')} />
            <FieldError errors={state.errors} name="price" />
          </div>
          <div className={`field ${styles.wide}`}>
            <label htmlFor="pf-desc">Описание</label>
            <textarea id="pf-desc" className="textarea" value={form.description} onChange={set('description')} />
          </div>
        </div>

        <div className="stack">
          <div className="row">
            <h3 style={{ margin: 0 }}>Характеристики</h3>
            <span className="spacer" />
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => setNewCharOpen(true)}>Нет нужной? Добавить</button>
          </div>
          {form.characteristics.map((c, index) => (
            <div key={index} className={styles.charRow}>
              <select className="select" value={c.characteristic_id} onChange={(e) => setChar(index, { characteristic_id: e.target.value })}
                      aria-label="Характеристика">
                <option value="">Характеристика…</option>
                {characteristics.data.map((ch) => (
                  <option key={ch.id} value={ch.id} disabled={usedChars.has(String(ch.id)) && String(ch.id) !== String(c.characteristic_id)}>
                    {ch.name}{ch.unit ? `, ${ch.unit}` : ''}
                  </option>
                ))}
              </select>
              <input className="input" placeholder="Значение" value={c.value} onChange={(e) => setChar(index, { value: e.target.value })}
                     aria-label="Значение" />
              <button type="button" className="btn btn-ghost btn-sm" aria-label="Убрать"
                      onClick={() => setForm({ ...form, characteristics: form.characteristics.filter((_, i) => i !== index) })}>✕</button>
            </div>
          ))}
          <FieldError errors={state.errors} name="characteristics" />
          <button type="button" className="btn btn-outline btn-sm" style={{ alignSelf: 'flex-start' }}
                  onClick={() => setForm({ ...form, characteristics: [...form.characteristics, { characteristic_id: '', value: '' }] })}>
            + Характеристика
          </button>
        </div>

        <label className="checkbox">
          <input type="checkbox" checked={form.is_active} onChange={set('is_active')} /> В продаже
        </label>

        <div className="row">
          <button className="btn btn-primary btn-lg" disabled={state.busy}>{isNew ? 'Создать товар' : 'Сохранить'}</button>
          <span className="spacer" />
          {!isNew && <button type="button" className="btn btn-danger" onClick={onDelete}>Удалить</button>}
        </div>
      </form>

      {newCharOpen && (
        <NewCharacteristic onClose={() => setNewCharOpen(false)} onCreated={(ch) => {
          characteristics.setData([...characteristics.data, ch].sort((a, b) => a.name.localeCompare(b.name)))
          setForm({ ...form, characteristics: [...form.characteristics, { characteristic_id: ch.id, value: '' }] })
          setNewCharOpen(false)
        }} />
      )}
    </>
  )
}
