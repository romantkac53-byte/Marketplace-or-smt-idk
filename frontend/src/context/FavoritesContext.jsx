/** Избранное: номера избранных товаров — общие для всего сайта, чтобы ♡ закрашивалось сразу везде. */
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { favoritesApi } from '../api'
import { useAuth } from './AuthContext'
import { useToast } from './ToastContext'

const FavoritesContext = createContext(null)

export function FavoritesProvider({ children }) {
  const { isCustomer } = useAuth()
  const toast = useToast()
  const [ids, setIds] = useState(new Set())

  useEffect(() => {
    if (!isCustomer) { setIds(new Set()); return }
    favoritesApi.ids().then((list) => setIds(new Set(list))).catch(() => setIds(new Set()))
  }, [isCustomer])

  const toggle = useCallback(async (productId) => {
    const was = ids.has(productId)
    // Сразу перекрашиваем сердечко, не дожидаясь ответа сервера; при ошибке — откатываем
    setIds((prev) => { const next = new Set(prev); was ? next.delete(productId) : next.add(productId); return next })
    try {
      if (was) {
        await favoritesApi.remove(productId)
        toast('Удалено из избранного', { type: 'info' })
      } else {
        await favoritesApi.add(productId)
        toast('Добавлено в избранное', { link: { to: '/favorites', label: 'Открыть' } })
      }
    } catch (e) {
      setIds((prev) => { const next = new Set(prev); was ? next.add(productId) : next.delete(productId); return next })
      toast(e.message, { type: 'error' })
    }
  }, [ids, toast])

  const value = useMemo(() => ({ ids, has: (id) => ids.has(id), toggle, count: ids.size }), [ids, toggle])
  return <FavoritesContext.Provider value={value}>{children}</FavoritesContext.Provider>
}

export const useFavorites = () => useContext(FavoritesContext)
