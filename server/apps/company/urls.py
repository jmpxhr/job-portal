
from django.urls import path

from server.apps.company import views

urlpatterns = [
    path(
        '',
        views.CompanyListView.as_view(),
        name='company-list',
    ),
    path(
        '<int:pk>/',
        views.CompanyDetailView.as_view(),
        name='company-detail',
    ),
    path(
        '<int:pk>/edit/',
        views.CompanyEditView.as_view(),
        name='company-edit',
    ),
    path(
        '<int:pk>/programs/create/',
        views.StudentProgramCreateView.as_view(),
        name='student-program-create',
    ),
    path(
        '<int:pk>/programs/<int:program_pk>/edit/',
        views.StudentProgramUpdateView.as_view(),
        name='student-program-edit',
    ),
    path(
        '<int:pk>/programs/<int:program_pk>/delete/',
        views.StudentProgramDeleteView.as_view(),
        name='student-program-delete',
    ),
]
