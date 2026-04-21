import socket

from debug_toolbar.settings import PANELS_DEFAULTS

from server.settings.components import config
from server.settings.components.common import (
    INSTALLED_APPS,
    MIDDLEWARE,
)

DEBUG = True

ALLOWED_HOSTS: list[str] = [
    config('DOMAIN_NAME', cast=str, default='localhost'),
    'localhost',
    '0.0.0.0',  # noqa: S104
    '127.0.0.1',
    '[::1]',
]
# Installed apps for development only:

INSTALLED_APPS += (
    # Better debug:
    'debug_toolbar',
)

# Django debug toolbar:
# https://django-debug-toolbar.readthedocs.io

MIDDLEWARE += ('debug_toolbar.middleware.DebugToolbarMiddleware',)

CORS_ALLOW_ALL_ORIGINS = True

# https://django-debug-toolbar.readthedocs.io/en/stable/installation.html#configure-internal-ips
try:  # This might fail on some OS
    INTERNAL_IPS = [
        '{}.1'.format(ip[: ip.rfind('.')])
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]
    ]
except OSError:  # pragma: no cover
    INTERNAL_IPS = []
INTERNAL_IPS += ['127.0.0.1', '10.0.2.2']

# This can be removed after `RedirectsPanel` will be gone:
DEBUG_TOOLBAR_PANELS = PANELS_DEFAULTS.copy()
DEBUG_TOOLBAR_PANELS.remove('debug_toolbar.panels.redirects.RedirectsPanel')
