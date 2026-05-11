from django.urls import path

from server.apps.job_advice import views

app_name = 'job_advice'

urlpatterns = [
    path(
        '<int:job_pk>/create/',
        views.JobAdviceCreateView.as_view(),
        name='create',
    ),
    path(
        '<int:pk>/status/',
        views.JobAdviceStatusView.as_view(),
        name='status',
    ),
]
