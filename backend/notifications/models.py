from django.db import models

from users.models import User


class Notification(models.Model):
    """Уведомление пользователю (колокольчик в шапке): «Посылка в пути», «Новый заказ» и т.п."""

    user = models.ForeignKey(User, verbose_name='Пользователь', on_delete=models.CASCADE, related_name='notifications')
    text = models.CharField('Текст', max_length=255)
    link = models.CharField('Ссылка во фронтенде', max_length=200, blank=True)  # куда перейти по клику
    is_read = models.BooleanField('Прочитано', default=False)
    created_at = models.DateTimeField('Создано', auto_now_add=True)

    class Meta:
        verbose_name = 'Уведомление'
        verbose_name_plural = 'Уведомления'
        ordering = ['-created_at', '-id']
        indexes = [models.Index(fields=['user', 'is_read'])]  # быстрый подсчёт непрочитанных

    def __str__(self):
        return f'{self.user}: {self.text}'


def notify(user, text, link=''):
    """Создать уведомление. Вызывается из signals.py и из представлений."""
    if user is None:
        return None
    return Notification.objects.create(user=user, text=text[:255], link=link)
