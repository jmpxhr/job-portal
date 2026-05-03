from django.urls import path

from server.apps.dashboard import views

urlpatterns = [
    path('', views.HomePageView.as_view(), name='home'),
    path(
        'jobseeker/saved-jobs/',
        views.SavedJobsView.as_view(),
        name='saved-jobs',
    ),
    path(
        'jobseeker/saved-jobs/<int:pk>',
        views.SavedJobsView.as_view(),
        name='saved-jobs',
    ),
]
