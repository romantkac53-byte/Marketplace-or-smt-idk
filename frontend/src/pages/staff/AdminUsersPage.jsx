/** Администратор: пользователи и сотрудники (use case «Управление пользователями»). */
import { useState } from 'react'
import { adminApi } from '../../api'
import { useAuth } from '../../context/AuthContext'
import { EmptyState, ErrorMessage, Loader, Modal, Pagination, PasswordInput } from '../../components/ui'
import { formatDate, userLabel } from '../../utils/format'
import { useLoad } from '../../utils/useLoad'
import styles from '../cabinet.module.css'
import { ROLE_NAMES } from './StaffLayout'

// Покупатели и продавцы регистрируются сами — администратор создаёт только сотрудников
const STAFF_ROLE_OPTIONS = ['courier', 'warehouse', 'pickup', 'manager', 'director', 'admin']

function UserModal({ user, onClose, onSaved }) {
  const isNew = !user
  const [form, setForm] = useState(isNew
    ? { email: '', login: '', password: '', first_name: '', last_name: '', role: 'courier' }
    : { first_name: user.first_name, last_name: user.last_name, role: user.role, password: '' })
  const [state, setState] = useState({ busy: false, error: '' })
  const set = (name) => (e) => setForm({ ...form, [name]: e.target.value })
  const canChangeRole = isNew || !['customer', 'seller'].includes(user.role)

  const submit = async (e) => {
    e.preventDefault()
    setState({ busy: true, error: '' })
    const data = { ...form }
    if (!data.password) delete data.password // пустой пароль при редактировании — не менять
    // Роль отправляем, только если её изменили: свою роль сервер менять не даёт — даже на ту же самую
    if (!canChangeRole || (!isNew && data.role === user.role)) delete data.role
    try {
      onSaved(isNew ? await adminApi.createUser(data) : await adminApi.updateUser(user.id, data))
    } catch (err) {
      const errors = err.data || {}
      // Set — без повторов: «Укажите email или логин» приходит сразу для двух полей
      setState({ busy: false, error: errors.detail || [...new Set(Object.values(errors).flat())].join(' ') || err.message })
    }
  }

  return (
    <Modal title={isNew ? 'Новый сотрудник' : userLabel(user)} onClose={onClose}>
      <form className="stack" onSubmit={submit}>
        {isNew && (
          <>
            <div className={styles.formGrid}>
              <div className="field"><label htmlFor="u-email">Email</label>
                <input id="u-email" className="input" type="email" value={form.email} onChange={set('email')} /></div>
              <div className="field"><label htmlFor="u-login">Логин</label>
                <input id="u-login" className="input" autoComplete="off" value={form.login} onChange={set('login')} /></div>
            </div>
            <span className="muted small" style={{ marginTop: -8 }}>Достаточно одного из двух — по нему сотрудник и будет входить</span>
          </>
        )}
        <div className={styles.formGrid}>
          <div className="field"><label htmlFor="u-first">Имя</label><input id="u-first" className="input" value={form.first_name} onChange={set('first_name')} /></div>
          <div className="field"><label htmlFor="u-last">Фамилия</label><input id="u-last" className="input" value={form.last_name} onChange={set('last_name')} /></div>
        </div>
        {canChangeRole ? (
          <div className="field"><label htmlFor="u-role">Роль</label>
            <select id="u-role" className="select" value={form.role} onChange={set('role')}>
              {STAFF_ROLE_OPTIONS.map((r) => <option key={r} value={r}>{ROLE_NAMES[r]}</option>)}
            </select>
            {form.role === 'pickup' && <span className="muted small">Привяжите сотрудника к пункту выдачи в админке: «Пункты выдачи» → «Сотрудники».</span>}
          </div>
        ) : <span className="small muted">Роль: {ROLE_NAMES[user.role]} (меняется только у сотрудников)</span>}
        <div className="field"><label htmlFor="u-pass">{isNew ? 'Пароль' : 'Новый пароль'}</label>
          <PasswordInput id="u-pass" autoComplete="new-password" required={isNew} minLength={8}
                 value={form.password} onChange={set('password')} placeholder={isNew ? '' : 'Оставьте пустым, чтобы не менять'} /></div>
        {state.error && <div className="alert alert-error">{state.error}</div>}
        <button className="btn btn-primary" disabled={state.busy}>{isNew ? 'Создать' : 'Сохранить'}</button>
      </form>
    </Modal>
  )
}

export default function AdminUsersPage() {
  const { user: me } = useAuth()
  const [filters, setFilters] = useState({ role: '', search: '', page: 1 })
  const [search, setSearch] = useState('')
  const { data, loading, error, reload } = useLoad(() => adminApi.users(filters), [JSON.stringify(filters)])
  const [editing, setEditing] = useState(undefined) // undefined — закрыто, null — новый, объект — редактирование
  const [notice, setNotice] = useState({ text: '', error: false })

  const toggleActive = async (u) => {
    setNotice({ text: '', error: false })
    try {
      await adminApi.updateUser(u.id, { is_active: !u.is_active })
      setNotice({ text: `${userLabel(u)}: ${u.is_active ? 'вход заблокирован' : 'вход разрешён'}`, error: false })
      reload()
    } catch (e) { setNotice({ text: e.message, error: true }) }
  }

  return (
    <>
      <div className={styles.head}><h1>Пользователи</h1><span className="spacer" />
        <button className="btn btn-primary" onClick={() => setEditing(null)}>+ Сотрудник</button></div>
      <form className={styles.toolbar} onSubmit={(e) => { e.preventDefault(); setFilters({ ...filters, search, page: 1 }) }}>
        <input className="input" type="search" placeholder="Email или имя" value={search} onChange={(e) => setSearch(e.target.value)} />
        <select className="select" value={filters.role} onChange={(e) => setFilters({ ...filters, role: e.target.value, page: 1 })} aria-label="Роль">
          <option value="">Все роли</option>
          {Object.entries(ROLE_NAMES).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
        <button className="btn btn-outline">Найти</button>
      </form>
      <p className="muted small" style={{ margin: 0 }}>Пользователей не удаляют — у них есть история заказов и операций. Вместо удаления — блокировка входа.</p>
      {notice.text && <div className={`alert ${notice.error ? 'alert-error' : 'alert-success'}`}>{notice.text}</div>}
      <ErrorMessage error={error} onRetry={reload} />
      {loading && !data ? <Loader /> : data && (
        data.count === 0 ? <EmptyState icon="👥" title="Никого не найдено" /> : (
          <div className={`card ${styles.tableWrap}`}>
            <table className="table">
              <thead><tr><th>Пользователь</th><th>Роль</th><th>Регистрация</th><th>Вход</th><th /></tr></thead>
              <tbody>
                {data.results.map((u) => (
                  <tr key={u.id} style={{ opacity: u.is_active ? 1 : 0.55 }}>
                    <td>{u.first_name || u.last_name ? `${u.first_name} ${u.last_name}`.trim() : <span className="muted">без имени</span>}
                      <div className="small muted">{userLabel(u)}</div></td>
                    <td><span className="badge badge-muted">{ROLE_NAMES[u.role] || u.role}</span></td>
                    <td className="small">{formatDate(u.date_joined)}</td>
                    <td>{u.is_active ? <span className="badge badge-success">разрешён</span> : <span className="badge badge-danger">заблокирован</span>}</td>
                    <td><div className={styles.actions}>
                      <button className="btn btn-outline btn-sm" onClick={() => setEditing(u)}>Изменить</button>
                      {u.id !== me.id && (
                        <button className={`btn btn-sm ${u.is_active ? 'btn-danger' : 'btn-outline'}`} onClick={() => toggleActive(u)}>
                          {u.is_active ? 'Заблокировать' : 'Разблокировать'}
                        </button>
                      )}
                    </div></td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pagination page={filters.page} count={data.count} onChange={(page) => setFilters({ ...filters, page })} />
          </div>
        )
      )}
      {editing !== undefined && (
        <UserModal user={editing} onClose={() => setEditing(undefined)} onSaved={(u) => {
          setEditing(undefined)
          setNotice({ text: `${userLabel(u)}: сохранено`, error: false })
          reload()
        }} />
      )}
    </>
  )
}
