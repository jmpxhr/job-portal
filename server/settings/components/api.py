from server.settings.components import config

REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': (
        'rest_framework.pagination.PageNumberPagination'
    ),
    'PAGE_SIZE': 10,
}

# django-cors-headers
# https://github.com/adamchainz/django-cors-headers

CORS_ALLOWED_ORIGINS = [
    f'https://{config("DOMAIN_NAME")}',
]
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_CREDENTIALS = True
