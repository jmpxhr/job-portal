from django.db.models.signals import post_save
from django.dispatch import receiver

from server.apps.skill_tests.models import SkillTestAttempt, SkillVerification


@receiver(post_save, sender=SkillTestAttempt)
def upsert_skill_verification(
    sender: type[SkillTestAttempt],
    instance: SkillTestAttempt,
    created: bool,  # noqa: FBT001
    **kwargs: object,
) -> None:
    if not created or not instance.passed:
        return

    SkillVerification.objects.update_or_create(
        jobseeker=instance.jobseeker,
        skill=instance.skill_test.skill,
        defaults={
            'difficulty': instance.skill_test.difficulty,
            'best_score': instance.score,
        },
    )
