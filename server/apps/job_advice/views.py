from typing import Any

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views import View

from server.apps.accounts.models import JobSeeker, User
from server.apps.job_advice.models import JobAdvice, JobAdviceStatusEnum
from server.apps.job_advice.tasks import generate_job_advice
from server.apps.jobs.models import Job
from server.common.types import AuthenticatedHttpRequest


class JobAdviceCreateView(LoginRequiredMixin, View):
    def post(
        self, request: AuthenticatedHttpRequest, job_pk: int,
    ) -> JsonResponse:
        if request.user.account_type != User.AccountTypeEnum.JOBSEEKER:
            return JsonResponse(
                {'error': 'Only job seekers can request advice'},
                status=403,
            )

        try:
            jobseeker = JobSeeker.objects.get(user=request.user)
        except JobSeeker.DoesNotExist:
            return JsonResponse(
                {'error': 'Job seeker profile not found'},
                status=404,
            )

        job = get_object_or_404(Job, pk=job_pk, is_active=True)

        existing_ready = JobAdvice.objects.filter(
            jobseeker=jobseeker,
            job=job,
            status=JobAdviceStatusEnum.READY,
            expires_at__gt=timezone.now(),
        ).first()
        if existing_ready is not None:
            return JsonResponse(
                {
                    'advice_id': existing_ready.pk,
                    'status': 'ready',
                },
            )

        existing_pending = JobAdvice.objects.filter(
            jobseeker=jobseeker,
            job=job,
            status=JobAdviceStatusEnum.PENDING,
        ).first()
        if existing_pending is not None:
            return JsonResponse(
                {
                    'advice_id': existing_pending.pk,
                    'status': 'pending',
                },
            )

        JobAdvice.objects.filter(
            jobseeker=jobseeker,
            job=job,
            status=JobAdviceStatusEnum.FAILED,
        ).delete()

        language = jobseeker.lang or getattr(request, 'LANGUAGE_CODE', 'en')
        advice = JobAdvice.objects.create(
            jobseeker=jobseeker,
            job=job,
            status=JobAdviceStatusEnum.PENDING,
            language=language,
        )

        generate_job_advice.enqueue(advice.pk)

        return JsonResponse(
            {
                'advice_id': advice.pk,
                'status': 'pending',
            },
        )


class JobAdviceStatusView(LoginRequiredMixin, View):
    def get(self, request: AuthenticatedHttpRequest, pk: int) -> JsonResponse:
        advice = get_object_or_404(JobAdvice, pk=pk)

        if advice.jobseeker.user_id != request.user.pk:
            return JsonResponse({'error': 'Not found'}, status=404)

        status_name = JobAdviceStatusEnum(advice.status).name.lower()
        data: dict[str, Any] = {
            'status': status_name,
        }

        if advice.status == JobAdviceStatusEnum.READY:
            data['advice'] = advice.advice
        elif advice.status == JobAdviceStatusEnum.FAILED:
            data['error'] = advice.error_message

        return JsonResponse(data)
