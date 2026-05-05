from django.db.models import F
from django.http import HttpRequest

from server.apps.accounts.models import Recruiter, User
from server.apps.jobs.models import Job, JobView


def record_job_view(job: Job, request: HttpRequest) -> bool:  # noqa: C901
    if not hasattr(request, 'session') or not request.session.session_key:
        request.session.save()

    session_key = request.session.session_key
    if not session_key:
        return False

    user = request.user
    if (
        user.is_authenticated
        and hasattr(user, 'account_type')
        and user.account_type == User.AccountTypeEnum.COMPANY
    ):
        try:
            if user.recruiter.company == job.company:  # pyrefly: ignore
                return False
        except (Recruiter.DoesNotExist, Exception):  # noqa: S110
            pass

    viewer = user if user.is_authenticated else None

    try:
        JobView.objects.create(
            job=job,
            session_key=session_key,
            viewer=viewer,
        )
    except Exception:
        return False

    Job.objects.filter(pk=job.pk).update(views_count=F('views_count') + 1)
    job.views_count = (job.views_count or 0) + 1
    return True
