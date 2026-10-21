from rest_framework import serializers
from rest_framework.fields import empty


class ActiveByDefaultField(serializers.BooleanField):
    """Флаг «включено», который по умолчанию — True.

    Обычное BooleanField в DRF, если данные пришли HTML-формой (multipart), считает отсутствующее поле
    снятым чекбоксом, то есть False. Из-за этого новый сотрудник создавался бы заблокированным,
    а новый товар — снятым с продажи. Здесь отсутствие поля означает «не указано» → True."""

    default_empty_html = empty

    def __init__(self, **kwargs):
        kwargs.setdefault('required', False)
        kwargs.setdefault('default', True)
        super().__init__(**kwargs)
