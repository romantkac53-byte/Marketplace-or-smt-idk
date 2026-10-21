import { Link, Navigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { EmptyState } from '../components/ui'
import { STAFF_ROLES } from './staff/StaffLayout'

/** «Личный кабинет» — ведёт в раздел своей роли. Сначала смотрим роль: у администратора
 *  могут быть и профили покупателя/продавца (тестовые), но его раздел — кабинет персонала. */
export function cabinetPath(user) {
  if (!user) return '/login'
  if (STAFF_ROLES.includes(user.role)) return '/staff'
  if (user.role === 'seller' || (user.seller && !user.customer)) return '/seller'
  return '/'
}

export function CabinetPage() {
  const { user } = useAuth()
  return <Navigate to={cabinetPath(user)} replace />
}

export function NotFoundPage() {
  return (
    <div className="container page">
      <EmptyState icon="🧭" title="Страница не найдена" text="Возможно, ссылка устарела"
                  action={<Link to="/" className="btn btn-primary">На главную</Link>} />
    </div>
  )
}
