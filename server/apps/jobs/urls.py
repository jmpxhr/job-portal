from django.urls import path
from django.views.generic import TemplateView

urlpatterns = [
    path(
        '',
        TemplateView.as_view(template_name='jobs/jobs-list.html'),
        name='jobs_list',
    ),
    path(
        '<int:job_id>',
        TemplateView.as_view(template_name='jobs/jobs-detail.html'),
        name='jobs_detail',
    ),
]
