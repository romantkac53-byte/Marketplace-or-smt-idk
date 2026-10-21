/**
 * «Вы недавно смотрели» — номера последних открытых товаров, в браузере (работает и без входа).
 * Это необязательное хранение: между визитами — только после согласия с cookie.
 * Без согласия список живёт, пока открыта вкладка (в памяти), и пропадает после закрытия.
 */
import { getConsent } from './preferences'

const KEY = 'marketplace_recent'
const LIMIT = 12
let memory = []

function read() {
  if (getConsent() !== 'accepted') return memory
  try { return JSON.parse(localStorage.getItem(KEY)) || [] } catch { return [] }
}

export function recentProducts() {
  return read()
}

export function rememberProduct(id) {
  const list = [id, ...read().filter((x) => x !== id)].slice(0, LIMIT) // свежий — первым, без повторов
  memory = list
  if (getConsent() === 'accepted') {
    try { localStorage.setItem(KEY, JSON.stringify(list)) } catch { /* приватный режим */ }
  }
}

export function forgetRecent() {
  memory = []
  try { localStorage.removeItem(KEY) } catch { /* приватный режим */ }
}
