from django.contrib import admin

from server.apps.accounts.models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin[User]):
    list_display = (
        'id',
        'email',
        'first_name',
        'last_name',
        'date_joined',
    )
