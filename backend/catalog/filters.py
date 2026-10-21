import re

from rest_framework.filters import SearchFilter

# «ID123456789», «id 123456789», «ИД 123456789», «арт. 123456789», «артикул: 123456789» или просто 9 цифр
ARTICLE_QUERY = re.compile(r'^\s*(?:id|ид|арт\.?|артикул)?\s*[:#№]?\s*(\d{9})\s*$', re.IGNORECASE)


def parse_article(text):
    """Номер артикула из поисковой строки или None, если это обычный текстовый поиск."""
    match = ARTICLE_QUERY.match(text or '')
    return int(match.group(1)) if match else None


class ArticleSearchFilter(SearchFilter):
    """Обычный поиск по тексту, но запрос вида «ID123456789» ищет товар по артикулу — точно, без похожих.
    article_lookup во view — путь к артикулу (по умолчанию поле article самого товара)."""

    def filter_queryset(self, request, queryset, view):
        article = parse_article(request.query_params.get(self.search_param, ''))
        if article is not None:
            return queryset.filter(**{getattr(view, 'article_lookup', 'article'): article})
        return super().filter_queryset(request, queryset, view)
