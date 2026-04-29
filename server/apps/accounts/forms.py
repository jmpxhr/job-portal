from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from server.apps.accounts.models import (
    JobSeeker,
    Recruiter,
    User,
)
from server.apps.companies.models import Company, Industry


class JobSeekerRegistrationForm(forms.Form):
    first_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(
            attrs={
                'class': 'form-control',
                'placeholder': 'Anna',
            },
        ),
    )
    last_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(
            attrs={
                'class': 'form-control',
                'placeholder': 'Petrova',
            },
        ),
    )
    email = forms.EmailField(
        widget=forms.EmailInput(
            attrs={
                'class': 'form-control',
                'placeholder': 'anna@student.com',
            },
        ),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                'class': 'form-control',
                'placeholder': 'Create password',
            },
        ),
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                'class': 'form-control',
                'placeholder': 'Confirm password',
            },
        ),
    )

    def clean_email(self) -> str:
        email = self.cleaned_data['email']
        if User.objects.filter(email__iexact=email).exists():
            msg = 'An account with this email already exists.'
            raise ValidationError(msg)
        return email

    def clean(self) -> dict[str, str] | None:
        cleaned_data = super().clean()
        if cleaned_data is None:
            return None
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        if password and confirm_password and password != confirm_password:
            msg = 'Passwords do not match.'
            self.add_error('confirm_password', msg)
        if password:
            try:
                validate_password(password)
            except ValidationError as e:
                self.add_error('password', e)
        return cleaned_data

    def save(self) -> JobSeeker:
        user = User(
            first_name=self.cleaned_data['first_name'],
            last_name=self.cleaned_data['last_name'],
            email=self.cleaned_data['email'],
            is_active=False,
            account_type=User.AccountTypeEnum.JOBSEEKER,
        )
        user.set_password(self.cleaned_data['password'])
        user.save()
        return JobSeeker.objects.create(user=user)


class CompanyRegistrationForm(forms.Form):
    first_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(
            attrs={
                'class': 'form-control',
                'placeholder': 'John',
            },
        ),
    )
    last_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(
            attrs={
                'class': 'form-control',
                'placeholder': 'Smith',
            },
        ),
    )
    email = forms.EmailField(
        widget=forms.EmailInput(
            attrs={
                'class': 'form-control',
                'placeholder': 'john@company.com',
            },
        ),
    )
    company_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(
            attrs={
                'class': 'form-control',
                'placeholder': 'TechStart Inc.',
            },
        ),
    )
    company_email = forms.EmailField(
        widget=forms.EmailInput(
            attrs={
                'class': 'form-control',
                'placeholder': 'hr@techstart.com',
            },
        ),
    )
    industry = forms.ModelChoiceField(
        queryset=Industry.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        empty_label='Select industry',
    )
    company_size = forms.ChoiceField(
        choices=Company.CompanySizeEnum.choices,
        initial=Company.CompanySizeEnum.SMALL,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    website = forms.URLField(
        required=False,
        widget=forms.URLInput(
            attrs={
                'class': 'form-control',
                'placeholder': 'https://www.company.com',
            },
        ),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                'class': 'form-control',
                'placeholder': 'Create password',
            },
        ),
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                'class': 'form-control',
                'placeholder': 'Confirm password',
            },
        ),
    )

    def clean_email(self) -> str:
        email = self.cleaned_data['email']
        if User.objects.filter(email__iexact=email).exists():
            msg = 'An account with this email already exists.'
            raise ValidationError(msg)
        return email

    def clean(self) -> dict[str, str] | None:
        cleaned_data = super().clean()
        if cleaned_data is None:
            return None
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        if password and confirm_password and password != confirm_password:
            msg = 'Passwords do not match.'
            self.add_error('confirm_password', msg)
        if password:
            try:
                validate_password(password)
            except ValidationError as e:
                self.add_error('password', e)
        return cleaned_data

    def save(self) -> Recruiter:
        user = User(
            first_name=self.cleaned_data['first_name'],
            last_name=self.cleaned_data['last_name'],
            email=self.cleaned_data['email'],
            is_active=False,
            account_type=User.AccountTypeEnum.COMPANY,
        )
        user.set_password(self.cleaned_data['password'])
        user.save()
        recruiter = Recruiter(user=user)
        recruiter.save()
        Company.objects.create(
            recruiter=recruiter,
            name=self.cleaned_data['company_name'],
            email=self.cleaned_data['company_email'],
            industry=self.cleaned_data.get('industry'),
            size=self.cleaned_data['company_size'],
            website=self.cleaned_data.get('website', ''),
        )
        return recruiter


class VerificationForm(forms.Form):
    otp = forms.CharField(max_length=10, required=True)


class LoginForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(
            attrs={
                'class': 'form-control border-start-0',
                'placeholder': 'you@example.com',
            },
        ),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                'class': 'form-control border-start-0',
                'placeholder': '••••••••',
                'data-type': 'password',
            },
        ),
    )
    user_type = forms.CharField(
        widget=forms.HiddenInput(),
        initial='jobseeker',
    )
    remember_me = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )

    def __init__(self, *args: object, **kwargs: object) -> None:
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)  # type: ignore
        self.user_cache = None

    def clean(self) -> dict[str, str] | None:
        cleaned_data = super().clean()
        if cleaned_data is None:
            return None
        email = cleaned_data.get('email')
        password = cleaned_data.get('password')
        if email and password:
            self.user_cache = authenticate(
                request=self.request,  # type: ignore
                username=email,
                password=password,
            )
            if self.user_cache is None:
                msg = 'Invalid email or password.'
                raise ValidationError(msg)
            if not self.user_cache.is_active:
                msg = 'Please verify your email address before logging in.'
                raise ValidationError(msg)
        return cleaned_data

    def get_user(self) -> User | None:
        return self.user_cache


class PasswordRecoveryEmailForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(
            attrs={
                'class': 'form-control border-start-0',
                'placeholder': 'anna.petrova@email.com',
            },
        ),
    )


class PasswordResetForm(forms.Form):
    new_password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                'class': 'form-control border-start-0',
                'placeholder': 'New password',
            },
        ),
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                'class': 'form-control border-start-0',
                'placeholder': 'Confirm new password',
            },
        ),
    )

    def __init__(self, *args: object, **kwargs: object) -> None:
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)  # type: ignore

    def clean(self) -> dict[str, str] | None:
        cleaned_data = super().clean()
        if cleaned_data is None:
            return None
        new_password = cleaned_data.get('new_password')
        confirm_password = cleaned_data.get('confirm_password')
        if new_password and confirm_password:
            if new_password != confirm_password:
                msg = 'Passwords do not match.'
                self.add_error('confirm_password', msg)
            if self.user:
                try:
                    validate_password(
                        new_password,
                        user=self.user,  # type: ignore
                    )
                except ValidationError as e:
                    self.add_error('new_password', e)
        return cleaned_data
