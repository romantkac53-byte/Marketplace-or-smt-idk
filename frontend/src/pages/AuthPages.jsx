/**
 * Вход и регистрация — окно поверх сайта (страница под ним затемнена и недоступна).
 * Открывается по адресам /login и /register; что лежит «под окном», решает App.jsx (state.background).
 */
import { useEffect, useRef, useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { Modal, PasswordInput } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { cabinetPath } from './MiscPages'
import { TermsText } from './TermsPage'
import styles from './AuthPages.module.css'

function FieldError({ errors, name }) {
  const messages = errors?.[name]
  return messages ? <span className="field-error">{[].concat(messages).join(' ')}</span> : null
}

// Логин: как на сервере (users/models.py) — латиница, цифры, точка, дефис, подчёркивание; 3–30 символов
const LOGIN_PATTERN = '[A-Za-z0-9_.\\-]{3,30}'
const LOGIN_HINT = '3–30 символов: латинские буквы, цифры, точка, дефис, подчёркивание'

/** Поле «чем входить»: email или логин. Значения хранятся отдельно — при переключении туда-обратно не стираются */
function IdentifierField({ byLogin, form, setForm, idPrefix = '', autoFocusMode, errors, showHint }) {
  const set = (name) => (e) => setForm({ ...form, [name]: e.target.value })
  return byLogin ? (
    <div className="field">
      <label htmlFor={`${idPrefix}login`}>Логин</label>
      <input id={`${idPrefix}login`} className="input" autoComplete="username" required autoCapitalize="none" spellCheck={false}
             pattern={LOGIN_PATTERN} title={LOGIN_HINT} data-autofocus={autoFocusMode}
             value={form.login} onChange={set('login')} />
      <FieldError errors={errors} name="login" />
      {showHint && !errors?.login && <span className="muted small">{LOGIN_HINT}</span>}
    </div>
  ) : (
    <div className="field">
      <label htmlFor={`${idPrefix}email`}>Email</label>
      <input id={`${idPrefix}email`} className="input" type="email" autoComplete="email" required data-autofocus={autoFocusMode}
             value={form.email} onChange={set('email')} />
      <FieldError errors={errors} name="email" />
    </div>
  )
}

/** Кнопка «по логину ⇄ по email»; после переключения курсор сразу в новом поле */
function MethodToggle({ byLogin, setByLogin, formRef, children }) {
  const toggled = useRef(false)
  useEffect(() => {
    // Фокус переносим после отрисовки нового поля и только после нажатия (не при открытии окна)
    if (toggled.current) formRef.current?.querySelector('#login, #email, #reg-login, #reg-email')?.focus()
  }, [byLogin, formRef])
  const toggle = () => {
    toggled.current = true
    setByLogin(!byLogin)
  }
  return <button type="button" className="btn btn-outline btn-block" onClick={toggle}>{children(byLogin)}</button>
}

function LoginForm({ onSuccess, onSwitch }) {
  const { login } = useAuth()
  const formRef = useRef(null)
  const [byLogin, setByLogin] = useState(false)
  const [form, setForm] = useState({ email: '', login: '', password: '' })
  const [state, setState] = useState({ busy: false, error: '' })

  const onSubmit = async (e) => {
    e.preventDefault()
    setState({ busy: true, error: '' })
    // Серверу отправляем только выбранное: { email, password } или { login, password }
    const credentials = byLogin ? { login: form.login, password: form.password } : { email: form.email, password: form.password }
    try {
      onSuccess(await login(credentials))
    } catch (err) {
      const wrong = byLogin ? 'Неверный логин или пароль' : 'Неверный email или пароль'
      setState({ busy: false, error: err.status === 401 ? wrong : err.message })
    }
  }

  return (
    <form ref={formRef} className="stack" onSubmit={onSubmit} style={{ gap: 16 }}>
      {state.error && <div className="alert alert-error">{state.error}</div>}
      <IdentifierField byLogin={byLogin} form={form} setForm={setForm} autoFocusMode="login" />
      <div className="field">
        <label htmlFor="password">Пароль</label>
        <PasswordInput id="password" autoComplete="current-password" required
                       value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
      </div>
      <div className="stack" style={{ gap: 8 }}>
        <MethodToggle byLogin={byLogin} setByLogin={setByLogin} formRef={formRef}>
          {(on) => (on ? 'Вход по email' : 'Вход по логину')}
        </MethodToggle>
        <button className="btn btn-primary btn-lg" disabled={state.busy}>{state.busy ? 'Входим…' : 'Войти'}</button>
      </div>
      <p className="muted" style={{ textAlign: 'center', margin: 0 }}>
        Нет аккаунта? <button type="button" className={styles.linkButton} onClick={onSwitch}>Зарегистрироваться</button>
      </p>
    </form>
  )
}

function RegisterForm({ onSuccess, onSwitch }) {
  const { register } = useAuth()
  const formRef = useRef(null)
  const [kind, setKind] = useState('customer')
  const [byLogin, setByLogin] = useState(false)
  const [form, setForm] = useState({ email: '', login: '', password: '', first_name: '', last_name: '', phone: '', address: '', store_name: '' })
  const [state, setState] = useState({ busy: false, errors: null, error: '' })
  const [acceptTerms, setAcceptTerms] = useState(false)
  const [termsOpen, setTermsOpen] = useState(false)

  const set = (name) => (e) => setForm({ ...form, [name]: e.target.value })

  const onSubmit = async (e) => {
    e.preventDefault()
    setState({ busy: true, errors: null, error: '' })
    const { phone, address, store_name, email, login, ...common } = form
    // Регистрируемся либо по email, либо по логину — второе поле не отправляем
    const base = { ...common, ...(byLogin ? { login } : { email }), accept_terms: acceptTerms } // сервер тоже проверяет согласие — обойти галочку нельзя
    const data = kind === 'seller' ? { ...base, store_name } : { ...base, phone, address }
    try {
      onSuccess(await register(kind, data))
    } catch (err) {
      setState({ busy: false, errors: err.data, error: err.data?.detail || (err.data ? '' : err.message) })
    }
  }

  return (
    <form ref={formRef} className="stack" onSubmit={onSubmit} style={{ gap: 16 }}>
      <div className={styles.tabs} role="tablist" aria-label="Тип аккаунта">
        <button type="button" role="tab" aria-selected={kind === 'customer'}
                className={kind === 'customer' ? styles.tabActive : ''} onClick={() => setKind('customer')}>Я покупатель</button>
        <button type="button" role="tab" aria-selected={kind === 'seller'}
                className={kind === 'seller' ? styles.tabActive : ''} onClick={() => setKind('seller')}>Я продавец</button>
      </div>
      {kind === 'seller' && (
        <div className="alert small">После регистрации магазин проверит менеджер. Товары можно добавлять сразу — покупатели увидят их после одобрения.</div>
      )}
      {state.error && <div className="alert alert-error">{state.error}</div>}

      {kind === 'seller' && (
        <div className="field">
          <label htmlFor="store_name">Название магазина</label>
          <input id="store_name" className="input" required value={form.store_name} onChange={set('store_name')} />
          <FieldError errors={state.errors} name="store_name" />
        </div>
      )}
      <div className={styles.twoCols}>
        <div className="field">
          <label htmlFor="first_name">Имя</label>
          <input id="first_name" className="input" autoComplete="given-name" data-autofocus="register"
                 value={form.first_name} onChange={set('first_name')} />
        </div>
        <div className="field">
          <label htmlFor="last_name">Фамилия</label>
          <input id="last_name" className="input" autoComplete="family-name" value={form.last_name} onChange={set('last_name')} />
        </div>
      </div>
      <IdentifierField byLogin={byLogin} form={form} setForm={setForm} idPrefix="reg-" errors={state.errors} showHint />
      <div className="field">
        <label htmlFor="reg-password">Пароль</label>
        <PasswordInput id="reg-password" autoComplete="new-password" required minLength={8}
                       value={form.password} onChange={set('password')} />
        <FieldError errors={state.errors} name="password" />
        {!state.errors?.password && <span className="muted small">Не короче 8 символов, не только цифры</span>}
      </div>
      {kind === 'customer' && (
        <>
          <div className="field">
            <label htmlFor="phone">Телефон</label>
            <input id="phone" className="input" type="tel" autoComplete="tel" placeholder="+7 900 123-45-67" value={form.phone} onChange={set('phone')} />
            <FieldError errors={state.errors} name="phone" />
          </div>
          <div className="field">
            <label htmlFor="address">Адрес доставки</label>
            <input id="address" className="input" autoComplete="street-address" value={form.address} onChange={set('address')} />
            <span className="muted small">Можно указать позже или выбрать пункт выдачи при заказе</span>
          </div>
        </>
      )}
      <div className="field">
        <label className="checkbox" style={{ alignItems: 'flex-start', fontWeight: 400, color: 'var(--color-text)', fontSize: 14 }}>
          <input type="checkbox" required checked={acceptTerms} onChange={(e) => setAcceptTerms(e.target.checked)}
                 style={{ marginTop: 3 }} />
          <span>
            Я принимаю{' '}
            <button type="button" className={styles.linkButton} onClick={() => setTermsOpen(true)}>пользовательское соглашение</button>
          </span>
        </label>
        <FieldError errors={state.errors} name="accept_terms" />
      </div>
      <div className="stack" style={{ gap: 8 }}>
        <MethodToggle byLogin={byLogin} setByLogin={setByLogin} formRef={formRef}>
          {(on) => (on ? 'Регистрация по email' : 'Регистрация по логину')}
        </MethodToggle>
        <button className="btn btn-primary btn-lg" disabled={state.busy || !acceptTerms}
                title={acceptTerms ? undefined : 'Сначала примите пользовательское соглашение'}>
          {state.busy ? 'Создаём аккаунт…' : 'Зарегистрироваться'}
        </button>
      </div>
      {termsOpen && (
        <Modal title="Пользовательское соглашение" onClose={() => setTermsOpen(false)}>
          <TermsText />
          {/* Кнопка прилипает к низу окна — видна, даже пока текст ещё не дочитан до конца */}
          <div style={{ position: 'sticky', bottom: -24, padding: '12px 0', background: 'var(--color-surface)' }}>
            <button type="button" className="btn btn-primary btn-block" onClick={() => { setAcceptTerms(true); setTermsOpen(false) }}>
              Принимаю
            </button>
          </div>
        </Modal>
      )}
      <p className="muted" style={{ textAlign: 'center', margin: 0 }}>
        Уже есть аккаунт? <button type="button" className={styles.linkButton} onClick={onSwitch}>Войти</button>
      </p>
    </form>
  )
}

export default function AuthModal({ mode }) {
  const { user } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const dialogRef = useRef(null)
  const background = location.state?.background
  // Уже был в аккаунте, когда открыл окно (например, зашёл на /login по ссылке) — сразу в свой раздел.
  // Запоминаем на момент открытия: сразу после входа user тоже появится, но тогда ведём туда, куда шёл (onSuccess)
  const loggedInOnOpen = useRef(Boolean(user)).current

  // Закрыть: вернуться на страницу «под окном». Если окно открыли кнопкой — это шаг назад по истории
  // (тогда и кнопка «Назад» в браузере работает так же); если по прямой ссылке — на главную.
  const close = () => (background ? navigate(-1) : navigate('/', { replace: true }))

  // Переключение вкладок — без новой записи в истории, с теми же background и from
  const switchTo = (next) => navigate(next === 'register' ? '/register' : '/login', { replace: true, state: location.state })

  const onSuccess = (me) => {
    const from = location.state?.from
    const target = me.customer && from && from !== '/login' && from !== '/register' ? from : cabinetPath(me)
    navigate(target, { replace: true })
  }

  useEffect(() => {
    // Страница под окном недоступна: ни мышью, ни клавишей Tab (атрибут inert), и не прокручивается
    const behind = [document.querySelector('header'), document.querySelector('main')].filter(Boolean)
    behind.forEach((el) => { el.inert = true })
    document.body.style.overflow = 'hidden'
    return () => {
      behind.forEach((el) => { el.inert = false })
      document.body.style.overflow = ''
    }
  }, [])

  useEffect(() => {
    dialogRef.current?.querySelector(`[data-autofocus="${mode}"]`)?.focus()
  }, [mode])

  useEffect(() => {
    const onKey = (e) => {
      // Esc закрывает окно входа, но не тогда, когда поверх открыто окно соглашения (его закрывает свой Esc)
      if (e.key === 'Escape' && document.querySelectorAll('[role="dialog"]').length === 1) close()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }) // eslint-disable-line react-hooks/exhaustive-deps

  if (loggedInOnOpen) return <Navigate to={cabinetPath(user)} replace />
  if (user) return null // только что вошёл — onSuccess уже ведёт на нужную страницу

  return (
    <div className={styles.overlay} onMouseDown={(e) => e.target === e.currentTarget && close()}>
      <div ref={dialogRef} className={styles.dialog} role="dialog" aria-modal="true"
           aria-label={mode === 'register' ? 'Регистрация' : 'Вход'}>
        <div className={styles.dialogHead}>
          <div className={styles.modeTabs} role="tablist">
            <button type="button" role="tab" aria-selected={mode === 'login'} onClick={() => switchTo('login')}
                    className={mode === 'login' ? styles.modeActive : ''}>Вход</button>
            <button type="button" role="tab" aria-selected={mode === 'register'} onClick={() => switchTo('register')}
                    className={mode === 'register' ? styles.modeActive : ''}>Регистрация</button>
          </div>
          <button type="button" className={styles.close} onClick={close} aria-label="Закрыть">✕</button>
        </div>
        {/* Обе формы живут одновременно (неактивная скрыта) — при переключении введённое не теряется */}
        <div hidden={mode !== 'login'}><LoginForm onSuccess={onSuccess} onSwitch={() => switchTo('register')} /></div>
        <div hidden={mode !== 'register'}><RegisterForm onSuccess={onSuccess} onSwitch={() => switchTo('login')} /></div>
      </div>
    </div>
  )
}
