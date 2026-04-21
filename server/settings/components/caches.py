# Caching
# https://docs.djangoproject.com/en/6.0/topics/cache/

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    },
}
