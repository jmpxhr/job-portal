import django_filters
from django.db.models import Q, QuerySet

from server.apps.company.models import Company, Industry


class CompanyFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(
        method='filter_search',
        label='Search',
    )
    industry = django_filters.ModelChoiceFilter(
        queryset=Industry.objects.all(),
        field_name='industry',
        label='Industry',
    )
    size = django_filters.NumberFilter(field_name='size')
    letter = django_filters.CharFilter(
        method='filter_letter',
        label='First letter',
    )
    sort = django_filters.CharFilter(
        method='filter_sort',
        label='Sort',
    )

    class Meta:
        model = Company
        fields: list[str] = []

    def filter_search(
        self,
        queryset: QuerySet[Company],
        name: str,
        value: str,
    ) -> QuerySet[Company, Company]:
        if not value:
            return queryset
        return queryset.filter(
            Q(name__icontains=value) | Q(description__icontains=value),
        )

    def filter_letter(
        self,
        queryset: QuerySet[Company],
        name: str,
        value: str,
    ) -> QuerySet[Company, Company]:
        if not value:
            return queryset
        return queryset.filter(name__istartswith=value)

    def filter_sort(
        self,
        queryset: QuerySet[Company],
        name: str,
        value: str,
    ) -> QuerySet[Company, Company]:
        order_map: dict[str, str] = {
            'name': 'name',
            'newest': '-pk',
        }
        return queryset.order_by(order_map.get(value, 'name'))
