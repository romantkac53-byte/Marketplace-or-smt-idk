const money = new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'RUB', maximumFractionDigits: 2 })
const dateTime = new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' })
const dateOnly = new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })

/** «1 234,50 ₽» — API отдаёт деньги строкой ("1234.50"), чтобы не терять копейки */
export const formatMoney = (value) => money.format(Number(value || 0))
export const formatDateTime = (value) => (value ? dateTime.format(new Date(value)) : '—')
export const formatDate = (value) => (value ? dateOnly.format(new Date(value)) : '—')

/** «1 товар», «2 товара», «5 товаров» */
// Как подписать пользователя: email, а у зарегистрированных по логину — логин
export const userLabel = (user) => user?.email || user?.login || ''

export function plural(n, [one, few, many]) {
  const mod10 = n % 10
  const mod100 = n % 100
  if (mod10 === 1 && mod100 !== 11) return `${n} ${one}`
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return `${n} ${few}`
  return `${n} ${many}`
}

/** Конечные категории дерева с полным путём — для выбора категории товара: [{id, label: 'Лекарства → Спреи'}] */
export function leafCategories(nodes, path = []) {
  return nodes.flatMap((node) => {
    const current = [...path, node.name]
    return node.children.length ? leafCategories(node.children, current) : [{ id: node.id, label: current.join(' → ') }]
  })
}

/** Все категории дерева с отступом по уровню — для выбора категорий акции */
export function allCategories(nodes, depth = 0) {
  return nodes.flatMap((node) => [{ id: node.id, label: `${'— '.repeat(depth)}${node.name}` }, ...allCategories(node.children, depth + 1)])
}

/** Поле <input type="datetime-local"> работает с местным временем без часового пояса */
export const toLocalInput = (iso) => {
  if (!iso) return ''
  const d = new Date(iso)
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16)
}
export const fromLocalInput = (value) => (value ? new Date(value).toISOString() : null)

/** Цвет бейджа для статуса заказа, подзаказа, доставки, платежа или возврата */
const STATUS_TONES = {
  success: ['paid', 'completed', 'delivered', 'refunded'],
  warning: ['new', 'pending', 'requested', 'partially_refunded', 'at_pickup_point', 'failed'],
  danger: ['cancelled', 'rejected', 'returned'],
}
export function statusTone(status) {
  for (const [tone, statuses] of Object.entries(STATUS_TONES)) {
    if (statuses.includes(status)) return tone
  }
  return 'primary' // в работе: подтверждён, собирается, в пути…
}
