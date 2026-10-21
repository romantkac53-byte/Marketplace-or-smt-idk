from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import exception_handler

from .errors import DomainError


def api_exception_handler(exc, context):
    """Ошибки бизнес-логики и валидации моделей → ответ 400 {"detail": "текст"}.
    404 — с русским текстом. Остальное (403, ошибки сериализаторов) обрабатывает стандартный обработчик DRF."""
    if isinstance(exc, DomainError):
        return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    if isinstance(exc, DjangoValidationError):
        data = exc.message_dict if hasattr(exc, 'error_dict') else {'detail': exc.messages}
        return Response(data, status=status.HTTP_400_BAD_REQUEST)
    if isinstance(exc, Http404):
        # Текст Django «No Order matches the given query.» — английский и раскрывает имя модели
        exc = NotFound('Не найдено: запись не существует или недоступна')
    return exception_handler(exc, context)
