/**
 * Корзина покупателя — общая для всего приложения, чтобы счётчик в шапке
 * обновлялся сразу после «В корзину» на любой странице.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { cartApi } from '../api'
import { useAuth } from './AuthContext'

const CartContext = createContext(null)
const EMPTY = { items: [], items_count: 0, total_price: '0' }

export function CartProvider({ children }) {
  const { isCustomer } = useAuth()
  const [cart, setCart] = useState(EMPTY)

  const refresh = useCallback(async () => {
    if (!isCustomer) {
      setCart(EMPTY)
      return
    }
    setCart(await cartApi.get())
  }, [isCustomer])

  useEffect(() => { refresh().catch(() => setCart(EMPTY)) }, [refresh])

  // Каждое изменение корзины API возвращает её целиком — просто сохраняем ответ
  const value = useMemo(() => ({
    cart,
    refresh,
    add: async (productId, quantity) => setCart(await cartApi.add(productId, quantity)),
    setQuantity: async (itemId, quantity) => setCart(await cartApi.setQuantity(itemId, quantity)),
    remove: async (itemId) => setCart(await cartApi.remove(itemId)),
    clear: async () => setCart(await cartApi.clear()),
    quantityOf: (productId) => cart.items.find((item) => item.product.id === productId)?.quantity ?? 0,
  }), [cart, refresh])

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>
}

export const useCart = () => useContext(CartContext)
