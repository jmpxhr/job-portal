from django.http import HttpRequest
from django_htmx.middleware import HtmxDetails

from server.apps.accounts.models import User


class HtmxRequest(HttpRequest):
    htmx: HtmxDetails


class AuthenticatedHttpRequest(HttpRequest):
    user: User  # pyrefly: ignore


class AuthenticatedHtmxRequest(HtmxRequest, AuthenticatedHttpRequest): ...
