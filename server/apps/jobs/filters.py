import django_filters
from django.db.models import Q, QuerySet

from server.apps.jobs.models import Job


class JobFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(
        method='filter_search',
        label='Search',
    )
    location = django_filters.CharFilter(
        field_name='location',
        lookup_expr='icontains',
        label='Location',
    )
    employment_type = django_filters.MultipleChoiceFilter(
        choices=Job.EmploymentTypeEnum.choices,
        label='Employment Type',
    )
    work_format = django_filters.MultipleChoiceFilter(
        choices=Job.WorkFormatEnum.choices,
        label='Work Format',
    )
    experience_level = django_filters.MultipleChoiceFilter(
        choices=Job.ExperienceLevelEnum.choices,
        label='Experience Level',
    )
    salary_from = django_filters.NumberFilter(
        method='filter_salary_from',
        label='Salary From',
    )
    company = django_filters.NumberFilter(
        field_name='company__id',
        label='Company',
    )
    sort = django_filters.CharFilter(
        method='filter_sort',
        label='Sort by',
    )

    class Meta:
        model = Job
        fields: list[str] = []

    def filter_search(
        self,
        queryset: QuerySet[Job],
        name: str,
        value: str,
    ) -> QuerySet[Job]:
        if not value:
            return queryset
        return queryset.filter(
            Q(title__icontains=value) | Q(description__icontains=value),
        )

    def filter_salary_from(
        self,
        queryset: QuerySet[Job],
        name: str,
        value: int,
    ) -> QuerySet[Job]:
        if not value:
            return queryset
        return queryset.filter(
            Q(salary_min__gte=value) | Q(salary_max__gte=value),
        )

    def filter_sort(
        self,
        queryset: QuerySet[Job],
        name: str,
        value: str,
    ) -> QuerySet[Job]:
        order_map = {
            'recent': '-posted_at',
            'salary_high': '-salary_max',
            'salary_low': 'salary_min',
            'match_score': '-match_score',
        }
        return queryset.order_by(order_map.get(value, '-posted_at'))
