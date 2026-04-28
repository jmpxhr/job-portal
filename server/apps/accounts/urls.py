from dmr.routing import path

from server.apps.accounts.views import register

urlpatterns = [
    path('register/', register),
]
