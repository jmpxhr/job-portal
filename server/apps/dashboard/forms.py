from typing import override

from django import forms
from django.contrib.auth.password_validation import validate_password

from server.apps.accounts.models import (
    Education,
    Experience,
    JobSeeker,
    Language,
    User,
)


class JobSeekerProfileForm(forms.ModelForm[JobSeeker]):
    first_name = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(
            attrs={'class': 'form-control', 'placeholder': 'First name'},
        ),
    )
    last_name = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(
            attrs={'class': 'form-control', 'placeholder': 'Last name'},
        ),
    )

    class Meta:
        model = JobSeeker
        fields = ('title', 'phone', 'location', 'about', 'avatar')
        widgets = {
            'title': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'e.g. Computer Science Student',
                },
            ),
            'phone': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': '+375 29 123-45-67',
                },
            ),
            'location': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'e.g. Minsk, Belarus',
                },
            ),
            'about': forms.Textarea(
                attrs={
                    'class': 'form-control',
                    'rows': 4,
                    'placeholder': 'Tell us about yourself...',
                },
            ),
            'avatar': forms.FileInput(
                attrs={'class': 'form-control'},
            ),
        }

    def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        super().__init__(*args, **kwargs)
        if self.instance.user_id:  # pyrefly: ignore
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name

    @override
    def save(self, commit: bool = True) -> JobSeeker:
        jobseeker = super().save(commit=False)
        user = jobseeker.user
        user.first_name = self.cleaned_data.get('first_name', '')
        user.last_name = self.cleaned_data.get('last_name', '')
        user.save(update_fields=['first_name', 'last_name'])
        if commit:
            jobseeker.save()
            self.save_m2m()
        return jobseeker


class EducationForm(forms.ModelForm[Education]):
    class Meta:
        model = Education
        fields = (
            'level',
            'institution_name',
            'faculty',
            'specialization',
            'year_of_graduation',
        )
        widgets = {
            'level': forms.Select(attrs={'class': 'form-select'}),
            'institution_name': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'e.g. Belarusian State University',
                },
            ),
            'faculty': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'e.g. Faculty of Computer Science',
                },
            ),
            'specialization': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'e.g. Software Engineering',
                },
            ),
            'year_of_graduation': forms.NumberInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'e.g. 2026',
                },
            ),
        }
        labels = {
            'level': 'Education Level',
            'institution_name': 'Institution',
            'faculty': 'Faculty',
            'specialization': 'Specialization',
            'year_of_graduation': 'Year of Graduation',
        }


class LanguageForm(forms.ModelForm[Language]):
    class Meta:
        model = Language
        fields = ('name', 'proficiency')
        widgets = {
            'name': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'e.g. English',
                },
            ),
            'proficiency': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'name': 'Language',
            'proficiency': 'Proficiency Level',
        }


class ExperienceForm(forms.ModelForm[Experience]):
    class Meta:
        model = Experience
        fields = (
            'position',
            'company_name',
            'start_date',
            'end_date',
            'description',
        )
        widgets = {
            'position': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'e.g. Frontend Developer Intern',
                },
            ),
            'company_name': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'e.g. TechStart Inc.',
                },
            ),
            'start_date': forms.DateInput(
                attrs={
                    'class': 'form-control',
                    'type': 'date',
                },
            ),
            'end_date': forms.DateInput(
                attrs={
                    'class': 'form-control',
                    'type': 'date',
                },
            ),
            'description': forms.Textarea(
                attrs={
                    'class': 'form-control',
                    'rows': 4,
                    'placeholder': (
                        'Describe your responsibilities and achievements...'
                    ),
                },
            ),
        }
        labels = {
            'position': 'Position',
            'company_name': 'Company',
            'start_date': 'Start Date',
            'end_date': 'End Date (leave empty if current)',
            'description': 'Description',
        }


class ResumeForm(forms.ModelForm[JobSeeker]):
    class Meta:
        model = JobSeeker
        fields = ('resume_objective', 'resume_file')
        widgets = {
            'resume_objective': forms.Textarea(
                attrs={
                    'class': 'form-control',
                    'rows': 4,
                    'placeholder': (
                        'Briefly describe your career goals and '
                        + 'what you bring to the table...'
                    ),
                },
            ),
            'resume_file': forms.FileInput(
                attrs={'class': 'form-control'},
            ),
        }
        labels = {
            'resume_objective': 'Career Objective',
            'resume_file': 'Upload Resume File',
        }


class SkillAddForm(forms.Form):
    names = forms.CharField(
        required=True,
        widget=forms.HiddenInput(),
    )

    def clean_names(self) -> list[str]:
        raw = self.cleaned_data.get('names', '')
        names = [name.strip() for name in raw.split(',') if name.strip()]
        if not names:
            raise forms.ValidationError('Please enter at least one skill.')
        for name in names:
            if len(name) > 100:
                raise forms.ValidationError(
                    f'Skill "{name[:20]}..." is too long (max 100 characters).',
                )
        return names


class PrivacySettingsForm(forms.ModelForm[JobSeeker]):
    class Meta:
        model = JobSeeker
        fields = ('profile_visible', 'resume_public')
        widgets = {
            'profile_visible': forms.CheckboxInput(
                attrs={'class': 'form-check-input'},
            ),
            'resume_public': forms.CheckboxInput(
                attrs={'class': 'form-check-input'},
            ),
        }
        labels = {
            'profile_visible': 'Profile visible to employers',
            'resume_public': 'Resume public',
        }


class ChangePasswordForm(forms.Form):
    current_password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={'class': 'form-control', 'placeholder': 'Current password'},
        ),
    )
    new_password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={'class': 'form-control', 'placeholder': 'New password'},
        ),
        validators=[validate_password],
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                'class': 'form-control',
                'placeholder': 'Confirm new password',
            },
        ),
    )

    def __init__(self, *args, user: User | None = None, **kwargs) -> None:  # type: ignore[no-untyped-def]
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_current_password(self) -> str:
        current_password: str = self.cleaned_data.get('current_password', '')
        if self.user and not self.user.check_password(current_password):
            raise forms.ValidationError('Current password is incorrect.')
        return current_password

    @override
    def clean(self) -> dict[str, str] | None:
        cleaned_data = super().clean()
        if cleaned_data is None:
            return None
        new_password = cleaned_data.get('new_password')
        confirm_password = cleaned_data.get('confirm_password')
        if (
            new_password
            and confirm_password
            and new_password != confirm_password
        ):
            self.add_error('confirm_password', 'Passwords do not match.')
        return cleaned_data
