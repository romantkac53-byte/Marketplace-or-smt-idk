import { useState } from 'react'
import { authApi, balanceApi } from '../api'
import { useAuth } from '../context/AuthContext'
import { ErrorMessage, Loader, Pagination, PasswordInput } from '../components/ui'
import { formatDateTime, formatMoney } from '../utils/format'
import { useLoad } from '../utils/useLoad'
import styles from './ProfilePage.module.css'

function PersonalForm() {
  const { user, reload } = useAuth()
  const [form, setForm] = useState({
    first_name: user.first_name, last_name: user.last_name,
    phone: user.customer?.phone || '', address: user.customer?.address || '',
  })
  const [state, setState] = useState({ busy: false, error: '', saved: false })
  const set = (name) => (e) => setForm({ ...form, [name]: e.target.value })

  const onSubmit = async (e) => {
    e.preventDefault()
    setState({ busy: true, error: '', saved: false })
    try {
      await authApi.updateMe({
        first_name: form.first_name, last_name: form.last_name,
        customer: { phone: form.phone, address: form.address },
      })
      await reload()
      setState({ busy: false, error: '', saved: true })
    } catch (err) {
      setState({ busy: false, error: err.message, saved: false })
    }
  }

  return (
    <form className="card stack" onSubmit={onSubmit}>
      <h2 style={{ margin: 0 }}>Личные данные</h2>
      <div className={styles.twoCols}>
        <div className="field"><label htmlFor="p-first">Имя</label><input id="p-first" className="input" value={form.first_name} onChange={set('first_name')} /></div>
        <div className="field"><label htmlFor="p-last">Фамилия</label><input id="p-last" className="input" value={form.last_name} onChange={set('last_name')} /></div>
      </div>
      {/* Чем входит пользователь — не редактируется. У зарегистрированных по логину email нет */}
      {user.email && <div className="field"><label>Email</label><input className="input" value={user.email} disabled /></div>}
      {user.login && <div className="field"><label>Логин</label><input className="input" value={user.login} disabled /></div>}
      <div className="field"><label htmlFor="p-phone">Телефон</label><input id="p-phone" className="input" type="tel" value={form.phone} onChange={set('phone')} /></div>
      <div className="field">
        <label htmlFor="p-address">Адрес доставки по умолчанию</label>
        <input id="p-address" className="input" value={form.address} onChange={set('address')} />
      </div>
      {state.error && <div className="alert alert-error">{state.error}</div>}
      {state.saved && <div className="alert alert-success">Сохранено</div>}
      <button className="btn btn-primary" style={{ alignSelf: 'flex-start' }} disabled={state.busy}>Сохранить</button>
    </form>
  )
}

function PasswordForm() {
  const [form, setForm] = useState({ old_password: '', new_password: '' })
  const [state, setState] = useState({ busy: false, error: '', saved: false })
  const onSubmit = async (e) => {
    e.preventDefault()
    setState({ busy: true, error: '', saved: false })
    try {
      await authApi.changePassword(form)
      setForm({ old_password: '', new_password: '' })
      setState({ busy: false, error: '', saved: true })
    } catch (err) {
      setState({ busy: false, error: err.message, saved: false })
    }
  }
  return (
    <form className="card stack" onSubmit={onSubmit}>
      <h2 style={{ margin: 0 }}>Смена пароля</h2>
      <div className="field">
        <label htmlFor="old-pass">Текущий пароль</label>
        <PasswordInput id="old-pass" autoComplete="current-password" required
               value={form.old_password} onChange={(e) => setForm({ ...form, old_password: e.target.value })} />
      </div>
      <div className="field">
        <label htmlFor="new-pass">Новый пароль</label>
        <PasswordInput id="new-pass" autoComplete="new-password" required minLength={8}
               value={form.new_password} onChange={(e) => setForm({ ...form, new_password: e.target.value })} />
      </div>
      {state.error && <div className="alert alert-error">{state.error}</div>}
      {state.saved && <div className="alert alert-success">Пароль изменён</div>}
      <button className="btn btn-outline" style={{ alignSelf: 'flex-start' }} disabled={state.busy}>Изменить пароль</button>
    </form>
  )
}

function Balance() {
  const [page, setPage] = useState(1)
  const balance = useLoad(() => balanceApi.get(), [])
  const history = useLoad(() => balanceApi.transactions(page), [page])
  return (
    <section className="card stack">
      <h2 style={{ margin: 0 }}>Баланс</h2>
      <div className={styles.balance}>{balance.data ? formatMoney(balance.data.balance) : '…'}</div>
      <p className="muted small" style={{ margin: 0 }}>
        Учебная имитация оплаты: баланс пополняет администратор, заказы оплачиваются с него, возвраты приходят на него.
      </p>
      <h3 style={{ margin: '8px 0 0' }}>История операций</h3>
      <ErrorMessage error={history.error} />
      {history.loading && !history.data ? <Loader /> : history.data && (
        history.data.count === 0 ? <p className="muted">Операций пока не было</p> : (
          <>
            <ul className={styles.operations}>
              {history.data.results.map((t) => (
                <li key={t.id}>
                  <div>
                    <div>{t.type_display}{t.order_id && <span className="muted"> · заказ №{t.order_id}</span>}</div>
                    <div className="muted small">{formatDateTime(t.created_at)}</div>
                  </div>
                  <strong className={Number(t.amount) > 0 ? styles.plus : styles.minus}>
                    {Number(t.amount) > 0 ? '+' : ''}{formatMoney(t.amount)}
                  </strong>
                </li>
              ))}
            </ul>
            <Pagination page={page} count={history.data.count} onChange={setPage} />
          </>
        )
      )}
    </section>
  )
}

export default function ProfilePage() {
  return (
    <div className="container page">
      <h1>Профиль</h1>
      <div className={styles.layout}>
        <div className="stack"><PersonalForm /><PasswordForm /></div>
        <Balance />
      </div>
    </div>
  )
}
