from django.conf import settings
from django.core.mail import send_mail
from django.tasks import task
from django.template.loader import render_to_string

from server.apps.accounts.models import User


@task
def send_verification_email(
    user_id: int,
    verification_code: str,
) -> None:
    user = User.objects.get(pk=user_id)
    subject = 'Verify your email - StartJob'
    context = {
        'user': user,
        'verification_code': verification_code,
    }
    text_message = render_to_string(
        'accounts/emails/verification_code.txt',
        context,
    )
    html_message = render_to_string(
        'accounts/emails/verification_code.html',
        context,
    )
    send_mail(
        subject=subject,
        message=text_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=html_message,
    )


@task
def send_password_reset_email(
    user_id: int,
    verification_code: str,
) -> None:
    user = User.objects.get(pk=user_id)
    subject = 'Reset your password - StartJob'
    context = {
        'user': user,
        'verification_code': verification_code,
    }
    text_message = render_to_string(
        'accounts/emails/password_reset_code.txt',
        context,
    )
    html_message = render_to_string(
        'accounts/emails/password_reset_code.html',
        context,
    )
    send_mail(
        subject=subject,
        message=text_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=html_message,
    )
