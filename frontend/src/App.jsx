import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { CookieBanner, ScrollTopButton } from './components/Extras'
import Header from './components/Header'
import RequireAuth from './components/RequireAuth'
import AuthModal from './pages/AuthPages'
import { AUTH_PATHS } from './utils/authModal'
import CartPage from './pages/CartPage'
import CatalogPage from './pages/CatalogPage'
import CheckoutPage from './pages/CheckoutPage'
import { CabinetPage, NotFoundPage } from './pages/MiscPages'
import OrderPage from './pages/OrderPage'
import OrdersPage from './pages/OrdersPage'
import FavoritesPage from './pages/FavoritesPage'
import ProductPage from './pages/ProductPage'
import ProfilePage from './pages/ProfilePage'
import ReturnsPage from './pages/ReturnsPage'
import TermsPage from './pages/TermsPage'
import SellerLayout from './pages/seller/SellerLayout'
import SellerOrdersPage from './pages/seller/SellerOrdersPage'
import SellerProductForm from './pages/seller/SellerProductForm'
import SellerProductsPage from './pages/seller/SellerProductsPage'
import SellerPromotionsPage from './pages/seller/SellerPromotionsPage'
import SellerReturnsPage from './pages/seller/SellerReturnsPage'
import SellerReviewsPage from './pages/seller/SellerReviewsPage'
import SellerStatsPage from './pages/seller/SellerStatsPage'
import SellerStockPage from './pages/seller/SellerStockPage'
import AdminUsersPage from './pages/staff/AdminUsersPage'
import { CourierPage, PickupPage } from './pages/staff/DeliveryPages'
import { DeliveriesPage, ManagerPromotionsPage, ManagerReturnsPage, ReviewsModerationPage, SellersPage } from './pages/staff/ManagerPages'
import ReportsPage from './pages/staff/ReportsPage'
import StaffLayout from './pages/staff/StaffLayout'
import { AssemblyPage, MovementsPage, StockPage, WarehouseReturnsPage } from './pages/staff/WarehousePages'

/** Карта сайта. RequireAuth customer — только для покупателей. */
export default function App() {
  // Вход и регистрация — окно поверх страницы. Под окном показываем ту страницу, откуда его открыли
  // (state.background), а при прямом заходе на /login — каталог.
  const location = useLocation()
  const authMode = AUTH_PATHS.includes(location.pathname) ? location.pathname.slice(1) : null
  const pageLocation = authMode ? (location.state?.background || { pathname: '/', search: '', hash: '', state: null, key: 'auth-bg' }) : location

  return (
    <>
      <Header />
      <main>
        <Routes location={pageLocation}>
          <Route path="/" element={<CatalogPage />} />
          <Route path="/products/:id" element={<ProductPage />} />
          <Route path="/terms" element={<TermsPage />} />

          <Route path="/cart" element={<RequireAuth customer><CartPage /></RequireAuth>} />
          <Route path="/checkout" element={<RequireAuth customer><CheckoutPage /></RequireAuth>} />
          <Route path="/favorites" element={<RequireAuth customer><FavoritesPage /></RequireAuth>} />
          <Route path="/orders" element={<RequireAuth customer><OrdersPage /></RequireAuth>} />
          <Route path="/orders/:id" element={<RequireAuth customer><OrderPage /></RequireAuth>} />
          <Route path="/returns" element={<RequireAuth customer><ReturnsPage /></RequireAuth>} />
          <Route path="/profile" element={<RequireAuth customer><ProfilePage /></RequireAuth>} />

          {/* Кабинет продавца: общий каркас с меню, внутри — разделы */}
          <Route path="/seller" element={<RequireAuth seller><SellerLayout /></RequireAuth>}>
            <Route index element={<Navigate to="stats" replace />} />
            <Route path="stats" element={<SellerStatsPage />} />
            <Route path="products" element={<SellerProductsPage />} />
            {/* key: после создания товара форма пересоздаётся для режима редактирования */}
            <Route path="products/new" element={<SellerProductForm key="new" />} />
            <Route path="products/:id" element={<SellerProductForm />} />
            <Route path="orders" element={<SellerOrdersPage />} />
            <Route path="promotions" element={<SellerPromotionsPage />} />
            <Route path="reviews" element={<SellerReviewsPage />} />
            <Route path="returns" element={<SellerReturnsPage />} />
            <Route path="stock" element={<SellerStockPage />} />
          </Route>

          {/* Кабинет персонала: меню зависит от роли, доступ к данным проверяет сервер */}
          <Route path="/staff" element={<RequireAuth staff><StaffLayout /></RequireAuth>}>
            <Route path="reports" element={<ReportsPage />} />
            <Route path="assembly" element={<AssemblyPage />} />
            <Route path="stock" element={<StockPage />} />
            <Route path="movements" element={<MovementsPage />} />
            <Route path="warehouse-returns" element={<WarehouseReturnsPage />} />
            <Route path="courier" element={<CourierPage key="mine" />} />
            <Route path="courier/available" element={<CourierPage key="available" available />} />
            <Route path="pickup" element={<PickupPage />} />
            <Route path="sellers" element={<SellersPage />} />
            <Route path="deliveries" element={<DeliveriesPage />} />
            <Route path="reviews" element={<ReviewsModerationPage />} />
            <Route path="returns" element={<ManagerReturnsPage />} />
            <Route path="promotions" element={<ManagerPromotionsPage />} />
            <Route path="users" element={<AdminUsersPage />} />
          </Route>

          <Route path="/cabinet" element={<RequireAuth><CabinetPage /></RequireAuth>} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </main>
      {authMode && <AuthModal mode={authMode} />}
      <ScrollTopButton />
      <CookieBanner />
    </>
  )
}
