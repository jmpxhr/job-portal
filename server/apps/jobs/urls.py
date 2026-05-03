from django.urls import path

from server.apps.jobs import views

urlpatterns = [
    path(
        '',
        views.JobListView.as_view(),
        name='jobs-list',
    ),
    path(
        '<int:pk>/',
        views.JobDetailView.as_view(),
        name='jobs-detail',
    ),
]
