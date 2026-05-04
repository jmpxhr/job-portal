from typing import override

from django import forms

from server.apps.accounts.models import Education, JobSeeker


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
