from django.urls import path

from server.apps.job_sync import views

urlpatterns = [
    path(
        'company/<int:pk>/source/',
        views.ExternalSourceView.as_view(),
        name='external-source',
    ),
    path(
        'company/<int:pk>/sync/<int:source_id>/',
        views.SyncJobsView.as_view(),
        name='sync-jobs',
    ),
    path(
        'company/<int:pk>/sync/<int:source_id>/status/',
        views.SyncStatusView.as_view(),
        name='sync-status',
    ),
]
