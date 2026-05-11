from django import forms

from server.apps.skill_tests.models import SkillTestDifficultyEnum


class SkillTestStartForm(forms.Form):
    difficulty = forms.ChoiceField(
        choices=SkillTestDifficultyEnum.choices,
        widget=forms.Select(
            attrs={
                'class': 'form-select',
            },
        ),
        initial=SkillTestDifficultyEnum.EASY,
    )


class SkillTestTakeForm(forms.Form):
    def __init__(  # type: ignore[no-untyped-def]
        self,
        *args,
        questions: list | None = None,  # type: ignore[type-arg]
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.questions = questions or []
        if self.questions:
            for i, question in enumerate(self.questions):
                choices = [
                    (idx, variant)
                    for idx, variant in enumerate(question['variants'])
                ]
                self.fields[f'question_{i}'] = forms.ChoiceField(
                    label=question['question'],
                    choices=choices,
                    widget=forms.RadioSelect(
                        attrs={'class': 'form-check-input'},
                    ),
                )
