class AuthenticationError(Exception):
    """Base authentication exception."""


class InvalidCredentialsError(AuthenticationError):
    """Raised when email/password combination is invalid."""


class UnverifiedAccountError(AuthenticationError):
    """Raised when account exists but is not verified."""
