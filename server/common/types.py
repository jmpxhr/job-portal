from django.http import HttpRequest as HttpRequestBase
from django_htmx.middleware import HtmxDetails


class HtmxRequest(HttpRequestBase):
    htmx: HtmxDetails
