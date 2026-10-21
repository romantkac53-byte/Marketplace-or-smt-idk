"""Права доступа API по ролям из ТЗ."""
from rest_framework.permissions import BasePermission

from users.models import User


class IsCustomer(BasePermission):
    """Есть профиль покупателя (корзина, заказы, отзывы, возвраты)."""
    message = 'Доступно только покупателям'

    def has_permission(self, request, view):
        return request.user.is_authenticated and hasattr(request.user, 'customer')


class IsSeller(BasePermission):
    """Есть профиль продавца (любой статус — например, чтобы видеть, что заявка на проверке)."""
    message = 'Доступно только продавцам'

    def has_permission(self, request, view):
        return request.user.is_authenticated and hasattr(request.user, 'seller')


class IsActiveSeller(IsSeller):
    """Одобренный продавец — может управлять товарами и заказами."""

    def has_permission(self, request, view):
        # Не продавец — сообщение «Доступно только продавцам» (из IsSeller), а не про статус магазина
        if not super().has_permission(request, view):
            return False
        if not request.user.seller.is_active:
            self.message = 'Магазин ещё не одобрен или заблокирован'
            return False
        return True


class CanManageProducts(IsSeller):
    """Продавец «На проверке» или одобренный — может готовить витрину (товары появятся в каталоге
    только после одобрения). Приостановленный или заблокированный — не может."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.user.seller.status not in ('pending', 'active'):
            self.message = 'Магазин приостановлен или заблокирован'
            return False
        return True


def has_role(*roles):
    """Право по роли: has_role(User.Role.COURIER). Администратор проходит всегда."""

    class HasRole(BasePermission):
        message = 'Недостаточно прав для этого действия'

        def has_permission(self, request, view):
            user = request.user
            return user.is_authenticated and (user.role in roles or user.role == User.Role.ADMIN
                                              or user.is_superuser)

    return HasRole
