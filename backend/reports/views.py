import csv

from django.http import HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from marketplace.permissions import IsSeller, has_role
from users.models import User

from . import services

IsDirector = has_role(User.Role.DIRECTOR)  # руководитель; администратор проходит любую проверку роли


class PeriodSerializer(serializers.Serializer):
    date_from = serializers.DateField(required=False, help_text='Начало периода, по умолчанию — 30 дней назад')
    date_to = serializers.DateField(required=False, help_text='Конец периода (включительно), по умолчанию — сегодня')
    group = serializers.ChoiceField(choices=['day', 'week', 'month'], default='day', help_text='Шаг графика')

    def validate(self, data):
        if data.get('date_from') and data.get('date_to') and (data['date_to'] - data['date_from']).days > 731:
            raise serializers.ValidationError('Период — не больше двух лет')
        return data


PERIOD_PARAMS = [
    OpenApiParameter('date_from', OpenApiTypes.DATE), OpenApiParameter('date_to', OpenApiTypes.DATE),
    OpenApiParameter('group', OpenApiTypes.STR, enum=['day', 'week', 'month']),
]
EXPORT_PARAM = OpenApiParameter('export', OpenApiTypes.STR, enum=['csv'], description='csv — скачать таблицу для Excel')


class ReportView(APIView):
    """Общее: разбор периода из параметров и выгрузка таблицы в CSV."""

    permission_classes = [IsDirector]
    csv_columns = ()  # [(ключ, заголовок)]
    csv_name = 'report'

    def period(self, request):
        params = PeriodSerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        data = params.validated_data
        return services.Period(data.get('date_from'), data.get('date_to')), data['group']

    def table_response(self, request, period, rows):
        if request.query_params.get('export') != 'csv':
            return Response({'period': period.as_dict(), 'results': rows})
        # BOM и «;» — чтобы Excel в русской локали сам открыл файл с кириллицей по столбцам
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = (f'attachment; filename="{self.csv_name}_{period.date_from}_{period.date_to}.csv"')
        response.write('﻿')
        writer = csv.writer(response, delimiter=';')
        writer.writerow([title for _, title in self.csv_columns])
        for row in rows:
            writer.writerow([str(row[key]).replace('.', ',') if row[key] is not None else '' for key, _ in self.csv_columns])
        return response


@extend_schema(tags=['Отчёты'], summary='Сводка: показатели, сравнение с прошлым периодом, график, доставка, топ товаров',
               parameters=PERIOD_PARAMS, responses=OpenApiTypes.OBJECT)
class DashboardView(ReportView):
    def get(self, request):
        period, group = self.period(request)
        return Response({
            'period': period.as_dict(),
            'summary': services.summary(period),
            'previous': services.summary(period.previous()),
            'series': services.sales_series(period, group),
            'deliveries': services.deliveries(period),
            'top_products': services.top_products(period, limit=5),
        })


@extend_schema(tags=['Отчёты'], summary='Продажи по магазинам', parameters=PERIOD_PARAMS + [EXPORT_PARAM],
               responses=OpenApiTypes.OBJECT)
class SellersReportView(ReportView):
    csv_name = 'sales_by_seller'
    csv_columns = (('store_name', 'Магазин'), ('orders', 'Заказов'), ('items_sold', 'Продано, шт.'),
                   ('gmv', 'Оборот, ₽'), ('commission', 'Комиссия площадки, ₽'), ('seller_payout', 'Выплата продавцу, ₽'),
                   ('returns_amount', 'Возвраты, ₽'), ('rating', 'Рейтинг'))

    def get(self, request):
        period, _ = self.period(request)
        return self.table_response(request, period, services.by_seller(period))


@extend_schema(tags=['Отчёты'], summary='Продажи по категориям', parameters=PERIOD_PARAMS + [EXPORT_PARAM],
               responses=OpenApiTypes.OBJECT)
class CategoriesReportView(ReportView):
    csv_name = 'sales_by_category'
    csv_columns = (('category', 'Категория'), ('items_sold', 'Продано, шт.'), ('gmv', 'Оборот, ₽'),
                   ('commission', 'Комиссия, ₽'), ('share', 'Доля оборота, %'))

    def get(self, request):
        period, _ = self.period(request)
        return self.table_response(request, period, services.by_category(period))


@extend_schema(tags=['Отчёты'], summary='Топ товаров по продажам', parameters=PERIOD_PARAMS + [EXPORT_PARAM],
               responses=OpenApiTypes.OBJECT)
class ProductsReportView(ReportView):
    csv_name = 'top_products'
    csv_columns = (('name', 'Товар'), ('store_name', 'Магазин'), ('items_sold', 'Продано, шт.'), ('gmv', 'Оборот, ₽'))

    def get(self, request):
        period, _ = self.period(request)
        return self.table_response(request, period, services.top_products(period, limit=50))


@extend_schema(tags=['Кабинет продавца'], summary='Сводка по моему магазину', parameters=PERIOD_PARAMS,
               responses=OpenApiTypes.OBJECT)
class SellerStatsView(ReportView):
    permission_classes = [IsSeller]

    def get(self, request):
        period, group = self.period(request)
        seller = request.user.seller  # только свой магазин
        return Response({
            'period': period.as_dict(),
            'summary': services.summary(period, seller),
            'previous': services.summary(period.previous(), seller),
            'series': services.sales_series(period, group, seller),
            'top_products': services.top_products(period, seller, limit=5),
        })
