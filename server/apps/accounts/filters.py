import django_filters
from django.db.models import Q, QuerySet

from server.apps.accounts.models import JobSeeker
from server.apps.jobs.models import Skill


class JobSeekerFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(
        method='filter_search',
        label='Search',
    )
    skills = django_filters.ModelMultipleChoiceFilter(
        queryset=Skill.objects.all(),
        field_name='skills__slug',
        label='Skills',
    )
    location = django_filters.CharFilter(
        method='filter_location',
        label='Location',
    )
    education_level = django_filters.NumberFilter(
        method='filter_education_level',
        label='Education Level',
    )
    sort = django_filters.CharFilter(
        method='filter_sort',
        label='Sort',
    )

    class Meta:
        model = JobSeeker
        fields: list[str] = []

    def filter_search(
        self,
        queryset: QuerySet[JobSeeker],
        name: str,
        value: str,
    ) -> QuerySet[JobSeeker]:
        if not value:
            return queryset
        return queryset.filter(
            Q(title__icontains=value)
            | Q(about__icontains=value)
            | Q(user__first_name__icontains=value)
            | Q(user__last_name__icontains=value),
        )

    def filter_location(
        self,
        queryset: QuerySet[JobSeeker],
        name: str,
        value: str,
    ) -> QuerySet[JobSeeker]:
        if not value:
            return queryset
        return queryset.filter(location__icontains=value)

    def filter_education_level(
        self,
        queryset: QuerySet[JobSeeker],
        name: str,
        value: int | None,
    ) -> QuerySet[JobSeeker]:
        if value is None:
            return queryset
        return queryset.filter(
            education__level=value,
        ).distinct()

    def filter_sort(
        self,
        queryset: QuerySet[JobSeeker],
        name: str,
        value: str,
    ) -> QuerySet[JobSeeker]:
        order_map: dict[str, str] = {
            'recent': '-created_at',
            'name': 'user__first_name',
        }
        return queryset.order_by(order_map.get(value, '-created_at'))
