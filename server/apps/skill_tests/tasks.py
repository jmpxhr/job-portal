from datetime import timedelta

from django.tasks import task
from django.utils import timezone

from server.apps.skill_tests import const
from server.apps.skill_tests.models import (
    SkillTest,
    SkillTestStatusEnum,
)
from server.apps.skill_tests.services import SkillTestGenerator


@task
def generate_skill_test_questions(skill_test_id: int) -> None:
    try:
        skill_test = SkillTest.objects.get(pk=skill_test_id)
    except SkillTest.DoesNotExist:
        return

    try:
        generator = SkillTestGenerator()
        questions = generator.generate(
            skill_test.skill.name,
            skill_test.difficulty,
            language=skill_test.language,
        )
        skill_test.questions = questions
        skill_test.status = SkillTestStatusEnum.READY
        skill_test.expires_at = timezone.now() + timedelta(
            days=const.CACHE_DAYS,
        )
        skill_test.save(
            update_fields=[
                'questions',
                'status',
                'expires_at',
                'updated_at',
            ],
        )
    except Exception as e:
        skill_test.status = SkillTestStatusEnum.FAILED
        skill_test.error_message = str(e)[:500]
        skill_test.save(
            update_fields=[
                'status',
                'error_message',
                'updated_at',
            ],
        )
