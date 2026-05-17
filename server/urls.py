"""
URL configuration for server project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from typing import TYPE_CHECKING

from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.contrib import admin
from django.contrib.admindocs import urls as admindocs_urls
from django.urls import include, path, re_path

from server.apps.accounts import urls as accounts_urls
from server.apps.chat import urls as chat_urls
from server.apps.company import urls as company_urls
from server.apps.dashboard import urls as dashboard_url
from server.apps.dashboard.views import HomePageView
from server.apps.job_advice import urls as job_advice_urls
from server.apps.job_sync import urls as job_sync_urls
from server.apps.jobs import urls as jobs_urls
from server.apps.skill_tests import urls as skill_tests_urls

if TYPE_CHECKING:
    from django.urls import URLPattern, URLResolver

admin.autodiscover()

urlpatterns: list['URLPattern | URLResolver'] = [
    path('i18n/', include('django.conf.urls.i18n')),
    # django-admin:
    path('admin/doc/', include(admindocs_urls)),
    path('admin/', admin.site.urls),
]

urlpatterns += i18n_patterns(
    # API:
    # Accounts
    path(
        'accounts/',
        include((accounts_urls, 'accounts'), namespace='accounts'),
    ),
    path(
        'company/',
        include((company_urls, 'company'), namespace='company'),
    ),
    path(
        'jobs/',
        include((jobs_urls, 'jobs'), namespace='jobs'),
    ),
    # Chat
    path(
        'chat/',
        include((chat_urls, 'chat'), namespace='chat'),
    ),
    # Dashboard
    path(
        'dashboard/',
        include((dashboard_url, 'dashboard'), namespace='dashboard'),
    ),
    # Skill Tests
    path(
        'skill-tests/',
        include((skill_tests_urls, 'skill_tests'), namespace='skill_tests'),
    ),
    # Job Advice
    path(
        'job-advice/',
        include((job_advice_urls, 'job_advice'), namespace='job_advice'),
    ),
    path(
        'job-sync/',
        include((job_sync_urls, 'job_sync'), namespace='job_sync'),
    ),
    # Index
    path('', HomePageView.as_view(), name='home'),
)

if settings.DEBUG:  # pragma: no cover
    import debug_toolbar
    from django.conf.urls.static import static

    urlpatterns = [
        # URLs specific only to django-debug-toolbar:
        path('__debug__/', include(debug_toolbar.urls)),
        *urlpatterns,
        # Serving media files in development only:
        *static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT),
    ]

if 'rosetta' in settings.INSTALLED_APPS:
    urlpatterns += [re_path(r'^rosetta/', include('rosetta.urls'))]
