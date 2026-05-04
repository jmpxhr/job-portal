from django import forms


class JobApplicationForm(forms.Form):
    cover_letter = forms.CharField(
        widget=forms.Textarea(
            attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': "Tell the employer why you're a great fit...",
            },
        ),
        required=False,
    )
    resume_file = forms.FileField(
        widget=forms.FileInput(
            attrs={
                'class': 'form-control',
                'accept': '.pdf,.doc,.docx',
            },
        ),
        required=False,
    )
