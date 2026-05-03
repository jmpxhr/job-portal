from typing import override

from django import forms

from server.apps.company.models import (
    Benefit,
    Company,
    StudentProgram,
)


class CompanyUpdateForm(forms.ModelForm):  # type: ignore[type-arg]
    benefits = forms.ModelMultipleChoiceField(
        queryset=Benefit.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple(
            attrs={'class': 'form-check-input'},
        ),
    )
    clear_logo = forms.BooleanField(
        required=False,
        label='Remove current logo',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
    clear_cover_image = forms.BooleanField(
        required=False,
        label='Remove current cover image',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )

    class Meta:
        model = Company
        fields = [
            'name',
            'industry',
            'description',
            'founded_year',
            'email',
            'phone',
            'size',
            'headquarters',
            'website',
            'logo',
            'cover_image',
            'linkedin_url',
            'facebook_url',
            'instagram_url',
            'telegram_url',
            'hr_contact_name',
            'hr_contact_position',
            'hr_contact_email',
            'benefits',
        ]
        widgets = {
            'name': forms.TextInput(
                attrs={'class': 'form-control'},
            ),
            'industry': forms.Select(
                attrs={'class': 'form-select'},
            ),
            'description': forms.Textarea(
                attrs={'class': 'form-control', 'rows': 4},
            ),
            'founded_year': forms.NumberInput(
                attrs={'class': 'form-control'},
            ),
            'email': forms.EmailInput(
                attrs={'class': 'form-control'},
            ),
            'phone': forms.TextInput(
                attrs={'class': 'form-control'},
            ),
            'size': forms.Select(
                attrs={'class': 'form-select'},
            ),
            'headquarters': forms.TextInput(
                attrs={'class': 'form-control'},
            ),
            'website': forms.URLInput(
                attrs={'class': 'form-control'},
            ),
            'logo': forms.FileInput(
                attrs={'class': 'form-control'},
            ),
            'cover_image': forms.FileInput(
                attrs={'class': 'form-control'},
            ),
            'linkedin_url': forms.URLInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'LinkedIn URL',
                },
            ),
            'facebook_url': forms.URLInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Facebook URL',
                },
            ),
            'instagram_url': forms.URLInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Instagram URL',
                },
            ),
            'telegram_url': forms.URLInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Telegram URL',
                },
            ),
            'hr_contact_name': forms.TextInput(
                attrs={'class': 'form-control'},
            ),
            'hr_contact_position': forms.TextInput(
                attrs={'class': 'form-control'},
            ),
            'hr_contact_email': forms.EmailInput(
                attrs={'class': 'form-control'},
            ),
        }

    @override
    def save(self, commit: bool = True) -> Company:
        instance = super().save(commit=False)

        if self.cleaned_data.get('clear_logo') and instance.logo:
            instance.logo = ''

        if self.cleaned_data.get('clear_cover_image') and instance.cover_image:
            instance.cover_image = ''

        if commit:
            instance.save()
            self.save_m2m()

        return instance  # type: ignore[no-any-return]


class StudentProgramForm(forms.ModelForm):  # type: ignore[type-arg]
    class Meta:
        model = StudentProgram
        fields = ['title', 'description', 'status', 'url']
        widgets = {
            'title': forms.TextInput(
                attrs={'class': 'form-control'},
            ),
            'description': forms.Textarea(
                attrs={'class': 'form-control', 'rows': 3},
            ),
            'status': forms.Select(
                attrs={'class': 'form-select'},
            ),
            'url': forms.URLInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'https://...',
                },
            ),
        }
