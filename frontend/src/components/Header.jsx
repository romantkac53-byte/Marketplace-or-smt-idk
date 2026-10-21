import { useEffect, useState } from 'react'
import { Link, NavLink, useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useCart } from '../context/CartContext'
import { useFavorites } from '../context/FavoritesContext'
import { ThemeToggle } from './Extras'
import NotificationsBell from './NotificationsBell'
import { useOpenAuth } from '../utils/authModal'
import { userLabel } from '../utils/format'
import { STAFF_ROLES } from '../pages/staff/StaffLayout'
import styles from './Header.module.css'

export default function Header() {
  const { user, isCustomer, isSeller, logout } = useAuth()
  const { cart } = useCart()
  const favorites = useFavorites()
  const openAuth = useOpenAuth()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const [search, setSearch] = useState(params.get('search') || '')
  const [menuOpen, setMenuOpen] = useState(false)

  useEffect(() => { setSearch(params.get('search') || '') }, [params])

  const onSearch = (e) => {
    e.preventDefault()
    navigate(search.trim() ? `/?search=${encodeURIComponent(search.trim())}` : '/')
  }

  const onLogout = async () => {
    setMenuOpen(false)
    await logout()
    navigate('/')
  }

  return (
    <header className={styles.header}>
      <div className={`container ${styles.inner}`}>
        <Link to="/" className={styles.logo} aria-label="На главную">
          <img src="/favicon.svg" alt="" width="32" height="32" />
          <span>Маркет</span>
        </Link>

        <form className={styles.search} onSubmit={onSearch} role="search">
          <input
            className="input"
            type="search"
            placeholder="Товар или артикул: ID123456789"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            aria-label="Поиск товаров"
          />
          <button className="btn btn-primary" type="submit">Найти</button>
        </form>

        <nav className={styles.nav}>
          <ThemeToggle className={styles.navLink} />
          {isCustomer && (
            <>
              <NavLink to="/favorites" className={styles.navLink} aria-label={`Избранное: ${favorites.count}`}>
                <span aria-hidden="true">♡</span><span className={styles.navText}>Избранное</span>
                {favorites.count > 0 && <span className={`${styles.counter} ${styles.counterSoft}`}>{favorites.count}</span>}
              </NavLink>
              <NavLink to="/orders" className={styles.navLink}>
                <span aria-hidden="true">📦</span><span className={styles.navText}>Заказы</span>
              </NavLink>
              <NavLink to="/cart" className={styles.navLink}>
                <span aria-hidden="true">🛒</span><span className={styles.navText}>Корзина</span>
                {cart.items_count > 0 && <span className={styles.counter}>{cart.items_count}</span>}
              </NavLink>
            </>
          )}

          {isSeller && (
            <NavLink to="/seller" className={styles.navLink}>
              <span aria-hidden="true">🏪</span><span className={styles.navText}>Кабинет продавца</span>
            </NavLink>
          )}

          {user && STAFF_ROLES.includes(user.role) && (
            <NavLink to="/staff" className={styles.navLink}>
              <span aria-hidden="true">🛠️</span><span className={styles.navText}>Кабинет</span>
            </NavLink>
          )}

          {user && <NotificationsBell />}

          {user ? (
            <div className={styles.account}>
              <button className={styles.navLink} onClick={() => setMenuOpen((v) => !v)} aria-expanded={menuOpen}>
                <span aria-hidden="true">👤</span><span className={styles.navText}>{user.first_name || 'Профиль'}</span>
              </button>
              {menuOpen && (
                <div className={styles.menu} onMouseLeave={() => setMenuOpen(false)}>
                  <div className={styles.menuEmail}>{userLabel(user)}</div>
                  {isCustomer && <Link to="/profile" onClick={() => setMenuOpen(false)}>Профиль и баланс</Link>}
                  {isCustomer && <Link to="/returns" onClick={() => setMenuOpen(false)}>Мои возвраты</Link>}
                  {!isCustomer && <Link to="/cabinet" onClick={() => setMenuOpen(false)}>Личный кабинет</Link>}
                  <button onClick={onLogout}>Выйти</button>
                </div>
              )}
            </div>
          ) : (
            <button type="button" className="btn btn-primary btn-sm" onClick={() => openAuth()}>Войти</button>
          )}
        </nav>
      </div>
    </header>
  )
}
