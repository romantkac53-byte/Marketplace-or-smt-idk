import { Navigate, NavLink, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import { EmptyState } from '../../components/ui'
import styles from '../cabinet.module.css'

export const ROLE_NAMES = {
  manager: 'Менеджер', warehouse: 'Сотрудник склада', courier: 'Курьер', pickup: 'Сотрудник ПВЗ',
  admin: 'Администратор', director: 'Руководитель', customer: 'Покупатель', seller: 'Продавец',
}

/** Разделы кабинета: [адрес, значок, название, роли]. Администратору видно всё (так же решает сервер). */
const SECTIONS = [
  ['/staff/reports', '📊', 'Отчёты', ['director']],
  ['/staff/assembly', '📋', 'Сборка заказов', ['warehouse']],
  ['/staff/stock', '🏬', 'Остатки и поставки', ['warehouse']],
  ['/staff/movements', '📒', 'Журнал склада', ['warehouse']],
  ['/staff/warehouse-returns', '📥', 'Приёмка возвратов', ['warehouse']],
  ['/staff/courier', '🚚', 'Мои доставки', ['courier']],
  ['/staff/courier/available', '📦', 'Свободные посылки', ['courier']],
  ['/staff/pickup', '🏪', 'Пункт выдачи', ['pickup']],
  ['/staff/sellers', '🛍️', 'Магазины', ['manager']],
  ['/staff/deliveries', '🗺️', 'Доставки', ['manager']],
  ['/staff/reviews', '⭐', 'Модерация отзывов', ['manager']],
  ['/staff/returns', '↩️', 'Возвраты', ['manager']],
  ['/staff/promotions', '🏷️', 'Акции площадки', ['manager']],
  ['/staff/users', '👥', 'Пользователи', []],
]

export const STAFF_ROLES = ['manager', 'warehouse', 'courier', 'pickup', 'admin', 'director']

export function sectionsFor(role) {
  return SECTIONS.filter(([, , , roles]) => role === 'admin' || roles.includes(role))
}

export default function StaffLayout() {
  const { user } = useAuth()
  const location = useLocation()
  const sections = sectionsFor(user.role)

  // /staff без раздела — открываем первый доступный
  if (location.pathname.replace(/\/$/, '') === '/staff' && sections.length) {
    return <Navigate to={sections[0][0]} replace />
  }

  return (
    <div className="container page">
      <div className={styles.layout}>
        <aside className={styles.sidebar}>
          <div className={styles.shop}>
            <span className={styles.shopIcon} aria-hidden="true">🛠️</span>
            <div>
              <strong>{user.full_name}</strong>
              <div className="small muted">{ROLE_NAMES[user.role]}</div>
            </div>
          </div>
          {sections.length > 0 && (
            <nav className={styles.menu}>
              {sections.map(([to, icon, label]) => (
                <NavLink key={to} to={to} end
                         className={({ isActive }) => `${styles.menuItem} ${isActive ? styles.menuActive : ''}`}>
                  <span aria-hidden="true">{icon}</span>{label}
                </NavLink>
              ))}
            </nav>
          )}
        </aside>
        <section className={styles.content}>
          {sections.length === 0 ? (
            <EmptyState icon="🔒" title="Нет доступных разделов" text="Обратитесь к администратору" />
          ) : <Outlet />}
        </section>
      </div>
    </div>
  )
}
