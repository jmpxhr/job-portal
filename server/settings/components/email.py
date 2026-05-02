# Timeouts
# https://docs.djangoproject.com/en/6.0/ref/settings/#std:setting-EMAIL_TIMEOUT

from server.settings.components import config

EMAIL_TIMEOUT = 5

DEFAULT_FROM_EMAIL = 'noreply@startjob.com'
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = config('DJANGO_EMAIL_HOST')
EMAIL_PORT = config('DJANGO_EMAIL_PORT', cast=int, default=1025)
EMAIL_USE_TLS = False
