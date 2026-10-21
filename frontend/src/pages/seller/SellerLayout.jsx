import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import styles from '../cabinet.module.css'

/** Пункты меню. onlyActive — раздел доступен только одобренному магазину (так решает API). */
const MENU = [
  ['/seller/stats', '📊', 'Сводка', false],
  ['/seller/products', '📦', 'Товары', false],
  ['/seller/orders', '🧾', 'Заказы', true],
  ['/seller/promotions', '🏷️', 'Акции', true],
  ['/seller/reviews', '⭐', 'Отзывы', true],
  ['/seller/returns', '↩️', 'Возвраты', true],
  ['/seller/stock', '🏬', 'Склад', false],
]

const STATUS_TEXT = {
  pending: ['warning', 'Магазин на проверке у менеджера. Можно заранее добавить товары — покупатели увидят их после одобрения.'],
  suspended: ['danger', 'Магазин приостановлен. Товары скрыты из каталога, изменения недоступны — свяжитесь с менеджером.'],
  blocked: ['danger', 'Магазин заблокирован. Товары скрыты из каталога, изменения недоступны.'],
}

export default function SellerLayout() {
  const { user } = useAuth()
  const status = user.seller.status
  const active = status === 'active'
  const notice = STATUS_TEXT[status]

  return (
    <div className="container page">
      <div className={styles.layout}>
        <aside className={styles.sidebar}>
          <div className={styles.shop}>
            <span className={styles.shopIcon} aria-hidden="true">🏪</span>
            <div>
              <strong>{user.seller.store_name}</strong>
              <div className="small muted">Кабинет продавца</div>
            </div>
          </div>
          <nav className={styles.menu}>
            {MENU.map(([to, icon, label, onlyActive]) => (
              onlyActive && !active ? (
                <span key={to} className={`${styles.menuItem} ${styles.menuDisabled}`} title="Доступно после одобрения магазина">
                  <span aria-hidden="true">{icon}</span>{label}
                </span>
              ) : (
                <NavLink key={to} to={to} className={({ isActive }) => `${styles.menuItem} ${isActive ? styles.menuActive : ''}`}>
                  <span aria-hidden="true">{icon}</span>{label}
                </NavLink>
              )
            ))}
          </nav>
        </aside>

        <section className={styles.content}>
          {notice && <div className={`alert ${notice[0] === 'danger' ? 'alert-error' : ''} ${styles.notice}`}>{notice[1]}</div>}
          <Outlet />
        </section>
      </div>
    </div>
  )
}
