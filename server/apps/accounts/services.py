from typing import TYPE_CHECKING

from django.contrib.auth import authenticate, get_user_model, login
from django.http import HttpRequest

from server.apps.accounts import tasks
from server.apps.accounts.exceptions import (
    InvalidCredentialsError,
    UnverifiedAccountError,
)

if TYPE_CHECKING:
    from server.apps.accounts.models import User as UserType

User = get_user_model()


class AuthService:
    @staticmethod
    def authenticate_user(
        request: HttpRequest,
        email: str,
        password: str,
    ) -> 'UserType':
        """Handle user authentication."""
        user = authenticate(request, username=email, password=password)

        if user is None:
            raise InvalidCredentialsError('Invalid email or password.')

        if not user.is_active:
            raise UnverifiedAccountError(
                'Please verify your email address before logging in.',
            )

        return user  # pyrefly: ignore

    @staticmethod
    def perform_login(
        request: HttpRequest,
        user: 'UserType',
        *,
        remember: bool = False,
    ) -> None:
        """Handle login session logic."""
        login(request, user)
        if not remember:
            request.session.set_expiry(0)

    @staticmethod
    def send_verification_email(
        request: HttpRequest,
        user: 'UserType',
    ) -> None:
        code = user.generate_verification_code()

        request.session['registration_user_pk'] = user.pk

        tasks.send_verification_email.enqueue(user.pk, code)
