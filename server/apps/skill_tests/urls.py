from django.urls import path

from server.apps.skill_tests import views

app_name = 'skill_tests'

urlpatterns = [
    path(
        '',
        views.SkillTestListView.as_view(),
        name='list',
    ),
    path(
        '<int:skill_pk>/start/',
        views.SkillTestStartView.as_view(),
        name='start',
    ),
    path(
        'test/<int:pk>/take/',
        views.SkillTestTakeView.as_view(),
        name='take',
    ),
    path(
        'test/<int:pk>/status/',
        views.SkillTestStatusView.as_view(),
        name='status',
    ),
    path(
        'test/<int:pk>/retry/',
        views.SkillTestRetryView.as_view(),
        name='retry',
    ),
    path(
        'test/<int:pk>/result/',
        views.SkillTestResultView.as_view(),
        name='result',
    ),
    path(
        'history/',
        views.SkillTestHistoryView.as_view(),
        name='history',
    ),
]
