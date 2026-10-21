from rest_framework.pagination import PageNumberPagination


class Pagination(PageNumberPagination):
    """По 20 на странице; фронтенд может попросить больше (?page_size=100) — например,
    чтобы показать все товары магазина в форме акции. Больше 100 за раз не отдаём."""

    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100
