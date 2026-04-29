from typing import TYPE_CHECKING, Any

from django.contrib.auth import login
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import FormView, TemplateView

from server.apps.accounts import const, forms
from server.apps.accounts.models import User
from server.apps.accounts.tasks import (
    send_password_reset_email,
    send_verification_email,
)
from server.common.types import HttpRequest

if TYPE_CHECKING:
    from django.forms import forms as django_forms


class RegisterView(TemplateView):
    template_name = const.REG_PAGE


class RegisterFormView(View):
    def get_form_class(
        self,
        user_type: str,
    ) -> 'type[django_forms.Form]':
        if user_type == 'company':
            return forms.CompanyRegistrationForm
        return forms.JobSeekerRegistrationForm

    def get_template_name(self, user_type: str) -> str:
        if user_type == 'company':
            return const.EMPLOYER_REG_FORM
        return const.STUDENT_REG_FORM

    def get_context_data(self, form: 'django_forms.Form') -> dict[str, Any]:
        return {'form': form}

    def post(self, request: HttpRequest) -> HttpResponse:
        user_type = request.POST.get('user_type', 'jobseeker')
        form_class = self.get_form_class(user_type)
        form = form_class()
        template_name = self.get_template_name(user_type)
        context = self.get_context_data(form)

        return render(request, template_name, context)


class RegisterSubmitView(View):
    def get_form_class(self, user_type: str):
        if user_type == 'company':
            return forms.CompanyRegistrationForm
        return forms.JobSeekerRegistrationForm

    def get_template_name(self, user_type: str) -> str:
        if user_type == 'company':
            return const.EMPLOYER_REG_FORM
        return const.STUDENT_REG_FORM

    def post(self, request: HttpRequest) -> HttpResponse:
        user_type = request.POST.get('user_type', 'jobseeker')

        form_class = self.get_form_class(user_type)
        form = form_class(request.POST)

        if not form.is_valid():
            template = self.get_template_name(user_type)
            return render(request, template, {'form': form})

        account = form.save()
        code = account.user.generate_verification_code()

        request.session['registration_user_pk'] = account.user.pk
        request.session['registration_user_type'] = user_type

        send_verification_email.enqueue(account.user.pk, code)

        return render(
            request,
            const.VERIFY_FORM,
            {
                'email': account.user.email,
                'resend_message': None,
            },
        )


class VerifyCodeView(FormView):
    form_class = forms.VerificationForm
    template_name = const.VERIFY_FORM

    def dispatch(self, request, *args, **kwargs):
        user_pk = request.session.get('registration_user_pk')
        if not user_pk:
            return redirect('accounts:register')

        try:
            self.user = User.objects.get(pk=user_pk)
        except User.DoesNotExist:
            return redirect('accounts:register')

        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        return {
            'email': self.user.email,
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['email'] = self.user.email
        context['resend_message'] = None
        if 'error' in kwargs:
            context['error'] = kwargs['error']
        return context

    def form_valid(self, form):
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
            self.request.session.pop(
                'registration_user_type',
                None,
            )

            response = HttpResponse(status=200)
            response['HX-Redirect'] = '/accounts/login/'
            return response

        return self.form_invalid(form)

    def form_invalid(self, form):
        context = self.get_context_data(
            form=form,
            error='Invalid verification code. Please try again.',
        )
        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        if form.is_valid():
            return self.form_valid(form)
        return self.form_invalid(form)


class ResendVerificationView(View):
    def get_user_from_session(self, request: HttpRequest):
        user_pk = request.session.get('registration_user_pk')
        if not user_pk:
            return None

        try:
            return User.objects.get(pk=user_pk)
        except User.DoesNotExist:
            return None

    def resend_verification_code(self, user: 'User'):
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
        form = forms.LoginForm()
        return render(
            request,
            const.LOGIN_PAGE,
            {'form': form},
        )

    def post(self, request: HttpRequest) -> HttpResponse:
        form = forms.LoginForm(request.POST, request=request)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            remember = form.cleaned_data.get('remember_me')
            if not user:
                return redirect(reverse('accounts:login'))
            if not remember:
                request.session.set_expiry(0)
            if user.account_type == User.AccountTypeEnum.JOBSEEKER:
                return redirect(reverse('dashboard:home'))
            if user.account_type == User.AccountTypeEnum.COMPANY:
                return redirect('/employer/dashboard/')
            return redirect('/')

        return render(
            request,
            const.LOGIN_PAGE,
            {'form': form},
        )


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
