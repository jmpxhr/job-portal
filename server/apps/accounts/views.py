from typing import TYPE_CHECKING, Any, override

from django.contrib.auth import logout
from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseBase,
    HttpResponseRedirect,
)
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import FormView

from server.apps.accounts import const, forms
from server.apps.accounts.exceptions import (
    InvalidCredentialsError,
    UnverifiedAccountError,
)
from server.apps.accounts.forms import (
    CompanyRegistrationForm,
    JobSeekerRegistrationForm,
    LoginForm,
)
from server.apps.accounts.models import User
from server.apps.accounts.services import AuthService
from server.apps.accounts.tasks import (
    send_password_reset_email,
    send_verification_email,
)
from server.common.types import HtmxRequest

type RegistrationFormType = (
    type[CompanyRegistrationForm] | type[JobSeekerRegistrationForm]
)

if TYPE_CHECKING:
    from django.forms import forms as django_forms


class GenericRegisterView(View):
    def get(self, request: HtmxRequest) -> HttpResponse:
        if request.htmx:
            user_type = request.GET.get('user_type', 'jobseeker')
            form = self._get_form(user_type)
            form_url = self._get_template_name(user_type)
            return render(
                request,
                template_name=form_url,
                context={
                    'form': form,
                },
            )
        return render(request, const.REG_PAGE)

    def post(self, request: HtmxRequest) -> HttpResponse:
        user_type = request.POST.get('user_type', 'jobseeker')

        form_class = self._get_form(user_type)
        form = form_class(request.POST)

        if not form.is_valid():
            template = self._get_template_name(user_type)
            return render(request, template, {'form': form})

        account = form.save()
        AuthService.send_verification_email(request, account.user)

        return render(
            request,
            const.VERIFY_FORM,
            {
                'email': account.user.email,
                'resend_message': None,
            },
        )

    def _get_template_name(self, user_type: str) -> str:
        form_template_map = {
            'jobseeker': const.STUDENT_REG_FORM,
            'company': const.EMPLOYER_REG_FORM,
        }
        return form_template_map.get(user_type, const.STUDENT_REG_FORM)

    def _get_form(
        self,
        user_type: str,
    ) -> RegistrationFormType:
        match user_type:
            case 'company':
                return CompanyRegistrationForm
            case _:
                return JobSeekerRegistrationForm


class VerifyCodeView(FormView):  # type: ignore[type-arg]
    form_class = forms.VerificationForm
    template_name = const.VERIFY_FORM

    @override
    def dispatch(  # type: ignore[no-untyped-def]
        self,
        request: HttpRequest,
        *args,
        **kwargs,
    ) -> HttpResponseBase | HttpResponseRedirect:
        user_pk = request.session.get('registration_user_pk')
        if not user_pk:
            return redirect('accounts:register')

        try:
            self.user = User.objects.get(pk=user_pk)
        except User.DoesNotExist:
            return redirect('accounts:register')

        return super().dispatch(request, *args, **kwargs)

    @override
    def get_initial(self) -> dict[str, str]:
        return {
            'email': self.user.email,
        }

    @override
    def get_context_data(self, **kwargs) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        context = super().get_context_data(**kwargs)
        context['email'] = self.user.email
        context['resend_message'] = None
        if 'error' in kwargs:
            context['error'] = kwargs['error']
        return context

    @override
    def form_valid(self, form: type['django_forms.Form']) -> HttpResponse:
        code = form.cleaned_data['otp']

        if code == self.user.email_verification_code:
            self.user.is_active = True
            self.user.email_verification_code = ''
            self.user.email_verification_sent_at = None
            self.user.save(
                update_fields=[
                    'is_active',
                    'email_verification_code',
                    'email_verification_sent_at',
                ],
            )

            self.request.session.pop(
                'registration_user_pk',
                None,
            )

            response = HttpResponse(status=200)
            response['HX-Redirect'] = reverse('accounts:login')
            return response

        return self.form_invalid(form)

    @override
    def form_invalid(self, form: type['django_forms.Form']) -> HttpResponse:
        context = self.get_context_data(
            form=form,
            error='Invalid verification code. Please try again.',
        )
        return self.render_to_response(context)

    @override
    def post(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:  # type: ignore[no-untyped-def]
        form = self.get_form()
        if form.is_valid():
            return self.form_valid(form)
        return self.form_invalid(form)


class ResendVerificationView(View):
    def get_user_from_session(self, request: HttpRequest) -> User | None:
        user_pk = request.session.get('registration_user_pk')
        if not user_pk:
            return None

        try:
            return User.objects.get(pk=user_pk)
        except User.DoesNotExist:
            return None

    def resend_verification_code(self, user: 'User') -> None:
        code = user.generate_verification_code()
        send_verification_email.enqueue(user.pk, code)

    def post(self, request: HttpRequest) -> HttpResponse:
        user = self.get_user_from_session(request)

        if not user:
            return redirect('accounts:register')

        self.resend_verification_code(user)

        return render(
            request,
            const.VERIFY_FORM,
            {
                'email': user.email,
                'resend_message': (
                    'A new verification code has been sent to your email.'
                ),
            },
        )


class LoginView(View):
    def get(self, request: HttpRequest) -> HttpResponse:
        form = LoginForm()
        return render(request, const.LOGIN_PAGE, {'form': form})

    def post(self, request: HttpRequest) -> HttpResponse:
        form = forms.LoginForm(request.POST)
        if form.is_valid():
            try:
                user = AuthService.authenticate_user(
                    request,
                    form.cleaned_data['email'],
                    form.cleaned_data['password'],
                )

                AuthService.perform_login(
                    request,
                    user,
                    remember=bool(form.cleaned_data.get('remember_me')),
                )

                return self._redirect_by_user_type(user)

            except InvalidCredentialsError as e:
                form.add_error(None, str(e))
            except UnverifiedAccountError as e:
                form.add_error(None, str(e))

        return render(request, const.LOGIN_PAGE, {'form': form})

    def _redirect_by_user_type(self, user: User) -> HttpResponse:
        """Handle post-login redirection based on user type."""
        redirect_map = {
            User.AccountTypeEnum.JOBSEEKER: reverse('dashboard:home'),
            User.AccountTypeEnum.COMPANY: '/employer/dashboard/',
        }
        return redirect(redirect_map.get(user.account_type, '/'))


class PasswordRecoveryView(View):
    def get(self, request: HttpRequest) -> HttpResponse:
        return render(
            request,
            const.PASSWORD_RECOVERY,
            {'form': forms.PasswordRecoveryEmailForm()},
        )

    def post(self, request: HttpRequest) -> HttpResponse:
        form = forms.PasswordRecoveryEmailForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            try:
                user = User.objects.get(email__iexact=email)
                if user.is_active:
                    code = user.generate_verification_code()
                    request.session['password_reset_user_pk'] = user.pk
                    send_password_reset_email.enqueue(user.pk, code)
            except User.DoesNotExist:
                pass

        return render(
            request,
            const.PASSWORD_RECOVERY_VERIFY,
            {
                'message': (
                    'If an account exists with this email, '
                    'a reset code has been sent.'
                ),
                'error': None,
            },
        )


class PasswordRecoveryVerifyView(View):
    def post(self, request: HttpRequest) -> HttpResponse:
        user_pk = request.session.get('password_reset_user_pk')
        if not user_pk:
            return redirect('accounts:password_recovery')

        try:
            user = User.objects.get(pk=user_pk)
        except User.DoesNotExist:
            return redirect('accounts:password_recovery')

        code = request.POST.get('otp', '')
        if (
            not user.email_verification_code
            or code != user.email_verification_code
        ):
            return render(
                request,
                const.PASSWORD_RECOVERY_VERIFY,
                {
                    'message': None,
                    'error': 'Invalid verification code. Please try again.',
                },
            )

        request.session['password_reset_verified'] = True
        return render(
            request,
            const.PASSWORD_RECOVERY_RESET,
            {'form': forms.PasswordResetForm()},
        )


class PasswordRecoveryResendView(View):
    def post(self, request: HttpRequest) -> HttpResponse:
        user_pk = request.session.get('password_reset_user_pk')
        if not user_pk:
            return redirect('accounts:password_recovery')

        try:
            user = User.objects.get(pk=user_pk)
        except User.DoesNotExist:
            return redirect('accounts:password_recovery')

        code = user.generate_verification_code()
        send_password_reset_email.enqueue(user.pk, code)

        return render(
            request,
            const.PASSWORD_RECOVERY_VERIFY,
            {
                'message': 'A new code has been sent to your email.',
                'error': None,
            },
        )


class PasswordRecoveryResetView(View):
    def post(self, request: HttpRequest) -> HttpResponse:
        user_pk = request.session.get('password_reset_user_pk')
        verified = request.session.get('password_reset_verified')
        if not user_pk or not verified:
            return redirect('accounts:password_recovery')

        try:
            user = User.objects.get(pk=user_pk)
        except User.DoesNotExist:
            return redirect('accounts:password_recovery')

        form = forms.PasswordResetForm(
            request.POST,
            user=user,
        )
        if form.is_valid():
            user.set_password(form.cleaned_data['new_password'])
            user.email_verification_code = ''
            user.email_verification_sent_at = None
            user.save(
                update_fields=[
                    'password',
                    'email_verification_code',
                    'email_verification_sent_at',
                ],
            )
            request.session.pop('password_reset_user_pk', None)
            request.session.pop('password_reset_verified', None)

            return render(
                request,
                const.PASSWORD_RECOVERY_SUCCESS,
            )

        return render(
            request,
            const.PASSWORD_RECOVERY_RESET,
            {'form': form},
        )


class LogoutView(View):
    def get(self, request: HttpRequest) -> HttpResponseRedirect:
        logout(request)
        return redirect(reverse('dashboard:home'))
