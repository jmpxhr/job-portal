from typing import Any

from django.views.generic import TemplateView

from server.apps.jobs.models import Job


class HomePageView(TemplateView):
    template_name = 'dashboard/index.html'

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['latest_jobs'] = (
            Job.objects
            .filter(is_active=True)
            .select_related('company')
            .prefetch_related('skills')
            .order_by('-posted_at')[:3]
        )
        return context
