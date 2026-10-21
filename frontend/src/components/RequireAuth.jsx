import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { STAFF_ROLES } from '../pages/staff/StaffLayout'
import { Loader } from './ui'

/**
 * Защита страниц: гостя отправляет на вход (а после входа — обратно),
 * пользователя без нужной роли — на главную.
 */
export default function RequireAuth({ children, customer = false, seller = false, staff = false }) {
  const { user, loading, isCustomer, isSeller } = useAuth()
  const location = useLocation()
  if (loading) return <Loader />
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
  if (customer && !isCustomer) return <Navigate to="/cabinet" replace />
  if (seller && !isSeller) return <Navigate to="/" replace />
  if (staff && !STAFF_ROLES.includes(user.role)) return <Navigate to="/" replace />
  return children
}
