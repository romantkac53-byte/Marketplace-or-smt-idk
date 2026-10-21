/**
 * Все адреса API в одном месте — страницы вызывают эти функции, а не пишут URL сами.
 * Описание каждого запроса: http://127.0.0.1:8000/api/docs/
 */
import { api } from './client'

export const authApi = {
  login: (credentials) => api.post('/auth/login/', credentials), // { email, password } или { login, password }
  registerCustomer: (data) => api.post('/auth/register/customer/', data),
  registerSeller: (data) => api.post('/auth/register/seller/', data),
  logout: (refresh) => api.post('/auth/logout/', { refresh }),
  me: () => api.get('/me/'),
  updateMe: (data) => api.patch('/me/', data),
  changePassword: (data) => api.post('/me/password/', data),
}

export const catalogApi = {
  categories: () => api.get('/categories/'),
  products: (params) => api.get('/products/', params),
  product: (id) => api.get(`/products/${id}/`),
  productReviews: (id, page) => api.get(`/products/${id}/reviews/`, { page }),
}

export const cartApi = {
  get: () => api.get('/cart/'),
  add: (productId, quantity = 1) => api.post('/cart/items/', { product_id: productId, quantity }),
  setQuantity: (itemId, quantity) => api.patch(`/cart/items/${itemId}/`, { quantity }),
  remove: (itemId) => api.delete(`/cart/items/${itemId}/`),
  clear: () => api.delete('/cart/'),
}

export const ordersApi = {
  list: (params) => api.get('/orders/', params),
  get: (id) => api.get(`/orders/${id}/`),
  place: (data) => api.post('/orders/', data),
  pay: (id) => api.post(`/orders/${id}/pay/`),
  cancel: (id, comment) => api.post(`/orders/${id}/cancel/`, { comment }),
  cancelPart: (id, sellerOrderId, comment) =>
    api.post(`/orders/${id}/seller-orders/${sellerOrderId}/cancel/`, { comment }),
  pickupPoints: (params) => api.get('/pickup-points/', params),
}

export const balanceApi = {
  get: () => api.get('/balance/'),
  transactions: (page) => api.get('/balance/transactions/', { page }),
}

export const reviewsApi = {
  mine: () => api.get('/reviews/'),
  create: (data) => api.post('/reviews/', data),
  remove: (id) => api.delete(`/reviews/${id}/`),
}

export const returnsApi = {
  mine: (params) => api.get('/returns/', params),
  create: (data) => api.post('/returns/', data),
  cancel: (id) => api.post(`/returns/${id}/cancel/`),
}

/** Кабинет продавца — только свои товары, заказы и т.д. (чужие API не отдаёт) */
export const sellerApi = {
  products: (params) => api.get('/seller/products/', params),
  product: (id) => api.get(`/seller/products/${id}/`),
  createProduct: (data) => api.post('/seller/products/', data),
  updateProduct: (id, data) => api.patch(`/seller/products/${id}/`, data),
  deleteProduct: (id) => api.delete(`/seller/products/${id}/`),
  uploadImage: (id, file) => {
    const form = new FormData()
    form.append('image', file)
    return api.post(`/seller/products/${id}/image/`, form)
  },
  addPhotos: (id, files) => {
    const form = new FormData()
    files.forEach((file) => form.append('images', file))
    return api.post(`/seller/products/${id}/photos/`, form)
  },
  deletePhoto: (id, photoId) => api.delete(`/seller/products/${id}/photos/${photoId}/`),
  makeCover: (id, photoId) => api.post(`/seller/products/${id}/photos/${photoId}/cover/`),
  characteristics: () => api.get('/characteristics/'),
  createCharacteristic: (data) => api.post('/characteristics/', data),

  orders: (params) => api.get('/seller/orders/', params),
  confirmOrder: (id) => api.post(`/seller/orders/${id}/confirm/`),
  cancelOrder: (id, comment) => api.post(`/seller/orders/${id}/cancel/`, { comment }),

  promotions: (params) => api.get('/seller/promotions/', params),
  createPromotion: (data) => api.post('/seller/promotions/', data),
  updatePromotion: (id, data) => api.patch(`/seller/promotions/${id}/`, data),
  deletePromotion: (id) => api.delete(`/seller/promotions/${id}/`),

  reviews: (params) => api.get('/seller/reviews/', params),
  reply: (id, text) => api.post(`/seller/reviews/${id}/reply/`, { text }),
  returns: (params) => api.get('/seller/returns/', params),
  stockMovements: (params) => api.get('/seller/stock-movements/', params),
  stats: (params) => api.get('/seller/stats/', params),
}

/** Кабинеты персонала. Доступ проверяет сервер по роли (администратору открыто всё). */
export const warehouseApi = {
  assembly: (params) => api.get('/warehouse/assembly/', params),
  start: (id) => api.post(`/warehouse/assembly/${id}/start/`),
  ready: (id) => api.post(`/warehouse/assembly/${id}/ready/`),
  stock: (params) => api.get('/warehouse/stock/', params),
  movements: (params) => api.get('/warehouse/movements/', params),
  operation: (data) => api.post('/warehouse/movements/', data),
  returns: (params) => api.get('/warehouse/returns/', params),
  acceptReturn: (id) => api.post(`/warehouse/returns/${id}/accept/`),
}

export const courierApi = {
  available: (params) => api.get('/courier/deliveries/available/', params),
  mine: (params) => api.get('/courier/deliveries/', params),
  take: (id) => api.post(`/courier/deliveries/${id}/take/`),
  pickUp: (id) => api.post(`/courier/deliveries/${id}/pick-up/`),
  handOver: (id, code) => api.post(`/courier/deliveries/${id}/hand-over/`, { code }),
  fail: (id, comment) => api.post(`/courier/deliveries/${id}/fail/`, { comment }),
}

export const pickupApi = {
  list: (params) => api.get('/pickup/deliveries/', params),
  accept: (id) => api.post(`/pickup/deliveries/${id}/accept/`),
  issue: (id, code) => api.post(`/pickup/deliveries/${id}/issue/`, { code }),
  returnExpired: () => api.post('/pickup/deliveries/return-expired/'),
}

export const managerApi = {
  sellers: (params) => api.get('/manager/sellers/', params),
  setSellerStatus: (id, status) => api.post(`/manager/sellers/${id}/set-status/`, { status }),
  deliveries: (params) => api.get('/manager/deliveries/', params),
  couriers: () => api.get('/manager/deliveries/couriers/'),
  assignCourier: (id, courierId) => api.post(`/manager/deliveries/${id}/assign/`, { courier_id: courierId }),
  reviews: (params) => api.get('/manager/reviews/', params),
  hideReview: (id) => api.post(`/manager/reviews/${id}/hide/`),
  publishReview: (id) => api.post(`/manager/reviews/${id}/publish/`),
  returns: (params) => api.get('/manager/returns/', params),
  approveReturn: (id, comment) => api.post(`/manager/returns/${id}/approve/`, { comment }),
  rejectReturn: (id, comment) => api.post(`/manager/returns/${id}/reject/`, { comment }),
  promotions: (params) => api.get('/manager/promotions/', params),
  createPromotion: (data) => api.post('/manager/promotions/', data),
  updatePromotion: (id, data) => api.patch(`/manager/promotions/${id}/`, data),
  deletePromotion: (id) => api.delete(`/manager/promotions/${id}/`),
}

export const adminApi = {
  users: (params) => api.get('/admin/users/', params),
  createUser: (data) => api.post('/admin/users/', data),
  updateUser: (id, data) => api.patch(`/admin/users/${id}/`, data),
}

/** Отчёты руководителя и администратора. export: 'sellers' | 'categories' | 'products' → CSV для Excel */
export const reportsApi = {
  dashboard: (params) => api.get('/reports/dashboard/', params),
  sellers: (params) => api.get('/reports/sellers/', params),
  categories: (params) => api.get('/reports/categories/', params),
  products: (params) => api.get('/reports/products/', params),
  exportCsv: (report, params) =>
    api.download(`/reports/${report}/`, { ...params, export: 'csv' }, `${report}_${params.date_from}_${params.date_to}.csv`),
}

export const favoritesApi = {
  list: () => api.get('/favorites/'),
  ids: () => api.get('/favorites/ids/'),
  add: (productId) => api.post('/favorites/', { product_id: productId }),
  remove: (productId) => api.delete(`/favorites/${productId}/`),
}

export const notificationsApi = {
  list: (params) => api.get('/notifications/', params),
  unreadCount: () => api.get('/notifications/unread-count/'),
  read: (id) => api.post(`/notifications/${id}/read/`),
  readAll: () => api.post('/notifications/read-all/'),
}
