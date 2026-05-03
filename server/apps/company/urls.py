from django.urls import path
from django.views.generic import TemplateView

urlpatterns = [
    path(
        '',
        TemplateView.as_view(template_name='company/company-list.html'),
        name='company-list',
    ),
    path(
        '<int:company_id>/',
        TemplateView.as_view(template_name='company/company-detail.html'),
        name='company-detail',
    ),
]
