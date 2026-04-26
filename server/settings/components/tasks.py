# Task framework settings
# https://docs.djangoproject.com/en/6.0/topics/tasks/

TASKS = {
    'default': {
        'BACKEND': 'django_tasks_db.DatabaseBackend',
        'QUEUES': ['default'],
    },
}
