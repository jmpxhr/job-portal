from dmr.routing import path

from server.apps.dashboard.views import HomePageView

urlpatterns = [
    path('', HomePageView.as_view(), name='home'),
]
