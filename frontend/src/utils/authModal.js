import { useCallback } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

/**
 * Открыть окно входа/регистрации поверх текущей страницы:
 *   const openAuth = useOpenAuth();  openAuth()  или  openAuth('register', '/cart')
 * background — страница «под окном» (её и видно под затемнением); from — куда вести после входа.
 */
export function useOpenAuth() {
  const navigate = useNavigate()
  const location = useLocation()
  return useCallback((mode = 'login', from) => {
    navigate(mode === 'register' ? '/register' : '/login', {
      state: { background: location, from: from ?? location.pathname + location.search },
    })
  }, [navigate, location])
}

export const AUTH_PATHS = ['/login', '/register']
