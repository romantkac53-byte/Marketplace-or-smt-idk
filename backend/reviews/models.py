from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Avg, Count
from django.utils import timezone

from catalog.models import Product
from orders.models import OrderError, OrderItem, SellerOrder
from users.models import Customer


class ReviewError(OrderError):
    """Ошибка отзыва: товар не куплен, не получен и т.п."""


class Review(models.Model):
    """Отзыв покупателя о купленном и полученном товаре."""

    product = models.ForeignKey(Product, verbose_name='Товар', on_delete=models.CASCADE, related_name='reviews')
    customer = models.ForeignKey(Customer, verbose_name='Покупатель', on_delete=models.CASCADE, related_name='reviews')
    rating = models.PositiveSmallIntegerField(
        'Оценка', validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    text = models.TextField('Текст', blank=True)
    # Модерация: менеджер может скрыть отзыв (оскорбления, спам) — он перестаёт влиять на рейтинг
    is_published = models.BooleanField('Опубликован', default=True)
    seller_reply = models.TextField('Ответ продавца', blank=True)
    replied_at = models.DateTimeField('Дата ответа', null=True, blank=True)
    created_at = models.DateTimeField('Дата', auto_now_add=True)
    updated_at = models.DateTimeField('Изменён', auto_now=True)

    class Meta:
        verbose_name = 'Отзыв'
        verbose_name_plural = 'Отзывы'
        ordering = ['-created_at']
        constraints = [
            # Один покупатель — один отзыв на товар (его можно отредактировать)
            models.UniqueConstraint(fields=['product', 'customer'], name='one_review_per_customer'),
        ]

    def __str__(self):
        return f'{self.product}: {self.rating}★ от {self.customer}'

    def reply(self, text):
        """Ответ продавца на отзыв."""
        self.seller_reply = text
        self.replied_at = timezone.now()
        self.save(update_fields=['seller_reply', 'replied_at', 'updated_at'])


def has_received(customer, product):
    """Покупатель получил этот товар хотя бы в одном заказе."""
    return OrderItem.objects.filter(
        product=product,
        seller_order__order__customer=customer,
        seller_order__status=SellerOrder.Status.DELIVERED,
    ).exists()


def leave_review(customer, product, rating, text=''):
    """«Оставление отзыва» из use case. Повторный вызов обновляет существующий отзыв."""
    if not has_received(customer, product):
        raise ReviewError('Отзыв можно оставить только на купленный и полученный товар')
    if not 1 <= int(rating) <= 5:
        raise ReviewError('Оценка должна быть от 1 до 5')
    review, _ = Review.objects.update_or_create(
        product=product, customer=customer, defaults={'rating': rating, 'text': text},
    )
    return review


def product_rating(product):
    """Средний рейтинг и число опубликованных отзывов: {'avg': 4.5, 'count': 12}."""
    data = product.reviews.filter(is_published=True).aggregate(avg=Avg('rating'), count=Count('id'))
    data['avg'] = round(data['avg'], 1) if data['avg'] is not None else None
    return data
