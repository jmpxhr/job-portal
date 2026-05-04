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
    path(
        'jobseeker/my-applications/',
        views.MyApplicationsView.as_view(),
        name='my-applications',
    ),
    path(
        'jobseeker/my-applications/<int:pk>/',
        views.ApplicationDetailView.as_view(),
        name='application-detail',
    ),
    path(
        'jobseeker/profile/',
        views.CandidateProfileView.as_view(),
        name='candidate-profile',
    ),
    path(
        'jobseeker/profile/edit/',
        views.EditProfileView.as_view(),
        name='edit-profile',
    ),
    path(
        'jobseeker/profile/education/create/',
        views.EducationCreateView.as_view(),
        name='education-create',
    ),
    path(
        'jobseeker/profile/education/<int:pk>/update/',
        views.EducationUpdateView.as_view(),
        name='education-update',
    ),
    path(
        'jobseeker/profile/education/<int:pk>/delete/',
        views.EducationDeleteView.as_view(),
        name='education-delete',
    ),
]
