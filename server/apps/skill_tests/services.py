from typing import Any

import lmstudio as lms
from django.conf import settings
from pydantic import BaseModel, Field

from server.apps.skill_tests import const
from server.apps.skill_tests.models import SkillTestDifficultyEnum


class QuestionModel(BaseModel):
    question: str = Field(description='A practical question about the skill')
    variants: list[str] = Field(
        description=f'Exactly {const.VARIANTS_PER_QUESTION} answer variants, '
        'one of which is correct',
    )
    correct_index: int = Field(
        description=f'Index (0-{const.VARIANTS_PER_QUESTION - 1}) '
        'of the correct answer in variants',
        ge=0,
        lt=const.VARIANTS_PER_QUESTION,
    )


class TestResponseModel(BaseModel):
    questions: list[QuestionModel] = Field(
        description=f'Exactly {const.QUESTIONS_PER_TEST} questions',
        min_length=const.QUESTIONS_PER_TEST,
        max_length=const.QUESTIONS_PER_TEST,
    )


LANGUAGE_NAMES: dict[str, str] = {
    'en': 'English',
    'ru': 'Russian',
}

DIFFICULTY_PROMPTS: dict[int, str] = {
    SkillTestDifficultyEnum.EASY: (
        'beginner level. Focus on fundamental concepts and basic knowledge '
        'that someone just starting out would know.'
    ),
    SkillTestDifficultyEnum.MEDIUM: (
        'intermediate level. Focus on practical application and deeper '
        'understanding that someone with moderate experience would have.'
    ),
    SkillTestDifficultyEnum.HARD: (
        'advanced level. Focus on complex scenarios, edge cases, and '
        'deep expertise that only an experienced practitioner would know.'
    ),
}


class SkillTestGenerator:
    def _get_model(self) -> Any:
        if model_identifier := settings.LMSTUDIO_MODEL:
            return lms.llm(model_identifier)
        return lms.llm()

    def _build_prompt(
        self,
        skill_name: str,
        difficulty: int,
        language: str = 'en',
    ) -> str:
        difficulty_desc = DIFFICULTY_PROMPTS.get(
            difficulty,
            DIFFICULTY_PROMPTS[SkillTestDifficultyEnum.EASY],
        )
        language_name = LANGUAGE_NAMES.get(language, language)
        return (
            f'Generate a skill assessment test for "{skill_name}" at {difficulty_desc} '  # noqa: E501
            f'The test must have exactly {const.QUESTIONS_PER_TEST} multiple choice questions. '  # noqa: E501
            f'Each question must have exactly {const.VARIANTS_PER_QUESTION} answer variants. '  # noqa: E501
            f'Questions should be practical and test real understanding, not trivia. '  # noqa: E501
            f'Make sure the correct answers are distributed across different variant positions. '  # noqa: E501
            f'All questions and variants must be in {language_name}.'
        )

    def generate(
        self,
        skill_name: str,
        difficulty: int,
        language: str = 'en',
    ) -> list[dict[str, Any]]:
        model = self._get_model()
        prompt = self._build_prompt(skill_name, difficulty, language)
        result = model.respond(prompt, response_format=TestResponseModel)
        return list(result.parsed['questions'])


class SkillTestScorer:
    @staticmethod
    def score(
        skill_test: Any,
        answers: dict[str, int],
    ) -> tuple[int, bool]:
        questions = skill_test.questions
        correct = 0
        total = len(questions)

        for i, question in enumerate(questions):
            chosen = answers.get(str(i))
            if chosen is not None and chosen == question['correct_index']:
                correct += 1

        if total == 0:
            return 0, False

        score = round((correct / total) * 100)
        passed = score >= const.PASS_THRESHOLD
        return score, passed
