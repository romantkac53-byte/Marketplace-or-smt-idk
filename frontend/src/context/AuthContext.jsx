/**
 * Кто сейчас вошёл. Любой компонент получает пользователя через useAuth():
 *   const { user, login, logout } = useAuth()
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { authApi } from '../api'
import { tokens } from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true) // пока проверяем сохранённый токен

  const loadMe = useCallback(async () => {
    if (!tokens.get()) {
      setUser(null)
      return null
    }
    try {
      const me = await authApi.me()
      setUser(me)
      return me
    } catch {
      tokens.clear()
      setUser(null)
      return null
    }
  }, [])

  useEffect(() => {
    loadMe().finally(() => setLoading(false))
    // Модуль запросов шлёт это событие, если токен обновить не удалось
    const onLogout = () => setUser(null)
    window.addEventListener('auth:logout', onLogout)
    return () => window.removeEventListener('auth:logout', onLogout)
  }, [loadMe])

  const login = useCallback(async (credentials) => {
    tokens.set(await authApi.login(credentials))
    return loadMe()
  }, [loadMe])

  const register = useCallback(async (kind, data) => {
    const response = kind === 'seller' ? await authApi.registerSeller(data) : await authApi.registerCustomer(data)
    tokens.set(response.tokens) // после регистрации сразу входим
    setUser(response.user)
    return response.user
  }, [])

  const logout = useCallback(async () => {
    const refresh = tokens.get()?.refresh
    tokens.clear()
    setUser(null)
    if (refresh) authApi.logout(refresh).catch(() => {}) // refresh-токен — в чёрный список на сервере
  }, [])

  const value = useMemo(() => ({
    user,
    loading,
    login,
    register,
    logout,
    reload: loadMe,
    isCustomer: Boolean(user?.customer),
    isSeller: Boolean(user?.seller),
  }), [user, loading, login, register, logout, loadMe])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export const useAuth = () => useContext(AuthContext)
