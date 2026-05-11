from datetime import datetime, timedelta
from typing import Any

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View

from server.apps.accounts.models import JobSeeker, User
from server.apps.jobs.models import Skill
from server.apps.skill_tests import const
from server.apps.skill_tests.forms import SkillTestStartForm, SkillTestTakeForm
from server.apps.skill_tests.models import (
    SkillTest,
    SkillTestAttempt,
    SkillTestStatusEnum,
    SkillVerification,
)
from server.apps.skill_tests.services import SkillTestScorer
from server.apps.skill_tests.tasks import generate_skill_test_questions
from server.common.types import (
    AuthenticatedHttpRequest,
    HtmxRequest,
)


class SkillTestListView(LoginRequiredMixin, View):
    template_name = const.SKILL_TEST_LIST

    def get_jobseeker(self, user: User) -> JobSeeker:
        return get_object_or_404(JobSeeker, user=user)

    def get(self, request: AuthenticatedHttpRequest) -> HttpResponse:
        jobseeker = self.get_jobseeker(request.user)

        search = request.GET.get('q', '').strip()
        skills = Skill.objects.all().order_by('name')

        if search:
            skills = skills.filter(name__icontains=search)

        verifications = SkillVerification.objects.filter(
            jobseeker=jobseeker,
        ).select_related('skill')

        context = {
            'skills': skills,
            'skill_verifications': verifications,
            'search': search,
        }
        return render(request, self.template_name, context)


class SkillTestStartView(LoginRequiredMixin, View):
    template_name = const.SKILL_TEST_START

    def get_jobseeker(self, user: User) -> JobSeeker:
        return get_object_or_404(JobSeeker, user=user)

    def get(
        self,
        request: AuthenticatedHttpRequest,
        skill_pk: int,
    ) -> HttpResponse:
        skill = get_object_or_404(Skill, pk=skill_pk)
        jobseeker = self.get_jobseeker(request.user)

        cooldown_until = self._get_cooldown(jobseeker, skill)

        form = SkillTestStartForm()
        context = {
            'skill': skill,
            'form': form,
            'cooldown_until': cooldown_until,
        }
        return render(request, self.template_name, context)

    def post(
        self,
        request: AuthenticatedHttpRequest,
        skill_pk: int,
    ) -> HttpResponse:
        skill = get_object_or_404(Skill, pk=skill_pk)
        jobseeker = self.get_jobseeker(request.user)

        cooldown_until = self._get_cooldown(jobseeker, skill)
        if cooldown_until:
            form = SkillTestStartForm(request.POST)
            context = {
                'skill': skill,
                'form': form,
                'cooldown_until': cooldown_until,
            }
            return render(request, self.template_name, context)

        form = SkillTestStartForm(request.POST)
        if not form.is_valid():
            context = {'skill': skill, 'form': form}
            return render(request, self.template_name, context)

        difficulty = int(form.cleaned_data['difficulty'])
        language = getattr(request, 'LANGUAGE_CODE', 'en')

        existing_ready = SkillTest.objects.filter(
            skill=skill,
            difficulty=difficulty,
            language=language,
            status=SkillTestStatusEnum.READY,
            expires_at__gt=timezone.now(),
        ).first()
        if existing_ready is not None:
            return redirect(
                reverse('skill_tests:take', kwargs={'pk': existing_ready.pk}),
            )

        existing_pending = SkillTest.objects.filter(
            skill=skill,
            difficulty=difficulty,
            language=language,
            status=SkillTestStatusEnum.PENDING,
        ).first()
        if existing_pending is not None:
            return redirect(
                reverse('skill_tests:take', kwargs={'pk': existing_pending.pk}),
            )

        SkillTest.objects.filter(
            skill=skill,
            difficulty=difficulty,
            status=SkillTestStatusEnum.FAILED,
        ).delete()

        skill_test = SkillTest.objects.create(
            skill=skill,
            difficulty=difficulty,
            status=SkillTestStatusEnum.PENDING,
            language=language,
        )

        generate_skill_test_questions.enqueue(skill_test.pk)

        return redirect(
            reverse('skill_tests:take', kwargs={'pk': skill_test.pk}),
        )

    def _get_cooldown(
        self,
        jobseeker: JobSeeker,
        skill: Skill,
    ) -> datetime | None:
        latest_attempt = (
            SkillTestAttempt.objects
            .filter(
                jobseeker=jobseeker,
                skill_test__skill=skill,
            )
            .order_by('-created_at')
            .first()
        )
        if latest_attempt is None:
            return None

        cooldown_end = latest_attempt.created_at + timedelta(
            days=const.COOLDOWN_DAYS,
        )
        if timezone.now() >= cooldown_end:
            return None

        return cooldown_end


class SkillTestTakeView(LoginRequiredMixin, View):
    template_name = const.SKILL_TEST_TAKE

    def get(self, request: HtmxRequest, pk: int) -> HttpResponse:
        skill_test = get_object_or_404(SkillTest, pk=pk)

        context = {
            'skill_test': skill_test,
            'poll_interval': const.POLL_INTERVAL_MS,
        }

        if (
            skill_test.status == SkillTestStatusEnum.READY
            and skill_test.questions
        ):
            form = SkillTestTakeForm(questions=skill_test.questions)
            # pyrefly: ignore [bad-typed-dict-key]
            context['form'] = form

        return render(request, self.template_name, context)

    def post(self, request: AuthenticatedHttpRequest, pk: int) -> HttpResponse:
        skill_test = get_object_or_404(SkillTest, pk=pk)

        if (
            skill_test.status != SkillTestStatusEnum.READY
            or not skill_test.questions
        ):
            return redirect(
                reverse('skill_tests:take', kwargs={'pk': skill_test.pk}),
            )

        try:
            jobseeker = JobSeeker.objects.get(user=request.user)
        except JobSeeker.DoesNotExist:
            raise Http404 from None

        answers: dict[str, int] = {}
        for i, _question in enumerate(skill_test.questions):
            value = request.POST.get(f'question_{i}')
            if value is not None:
                answers[str(i)] = int(value)

        scorer = SkillTestScorer()
        score, passed = scorer.score(skill_test, answers)

        attempt = SkillTestAttempt.objects.create(
            jobseeker=jobseeker,
            skill_test=skill_test,
            answers=answers,
            score=score,
            passed=passed,
        )

        return redirect(
            reverse('skill_tests:result', kwargs={'pk': attempt.pk}),
        )


class SkillTestStatusView(LoginRequiredMixin, View):
    def get(self, request: AuthenticatedHttpRequest, pk: int) -> JsonResponse:
        skill_test = get_object_or_404(SkillTest, pk=pk)

        status_name = SkillTestStatusEnum(skill_test.status).name.lower()
        data: dict[str, Any] = {
            'status': status_name,
        }

        if skill_test.status == SkillTestStatusEnum.READY:
            data['questions'] = skill_test.questions
            data['skill_name'] = skill_test.skill.name
            # pyrefly: ignore [missing-attribute]
            data['difficulty'] = skill_test.get_difficulty_display()
        elif skill_test.status == SkillTestStatusEnum.FAILED:
            data['error'] = skill_test.error_message

        return JsonResponse(data)


class SkillTestRetryView(LoginRequiredMixin, View):
    def post(self, request: AuthenticatedHttpRequest, pk: int) -> HttpResponse:
        try:
            jobseeker = JobSeeker.objects.get(user=request.user)
        except JobSeeker.DoesNotExist:
            raise Http404 from None

        skill_test = get_object_or_404(SkillTest, pk=pk)

        if skill_test.status != SkillTestStatusEnum.FAILED:
            return redirect(
                reverse('skill_tests:take', kwargs={'pk': skill_test.pk}),
            )

        cooldown_until = SkillTestStartView()._get_cooldown(  # noqa: SLF001
            jobseeker,
            skill_test.skill,
        )
        if cooldown_until:
            return redirect(
                reverse(
                    'skill_tests:start',
                    kwargs={
                        'skill_pk': skill_test.skill.pk,
                    },
                ),
            )

        skill = skill_test.skill
        difficulty = skill_test.difficulty
        language = skill_test.language
        skill_test.delete()

        existing_ready = SkillTest.objects.filter(
            skill=skill,
            difficulty=difficulty,
            language=language,
            status=SkillTestStatusEnum.READY,
            expires_at__gt=timezone.now(),
        ).first()
        if existing_ready is not None:
            return redirect(
                reverse('skill_tests:take', kwargs={'pk': existing_ready.pk}),
            )

        new_test = SkillTest.objects.create(
            skill=skill,
            difficulty=difficulty,
            status=SkillTestStatusEnum.PENDING,
            language=language,
        )
        generate_skill_test_questions.enqueue(new_test.pk)

        return redirect(
            reverse('skill_tests:take', kwargs={'pk': new_test.pk}),
        )


class SkillTestResultView(LoginRequiredMixin, View):
    template_name = const.SKILL_TEST_RESULT

    def get(self, request: AuthenticatedHttpRequest, pk: int) -> HttpResponse:
        try:
            jobseeker = JobSeeker.objects.get(user=request.user)
        except JobSeeker.DoesNotExist:
            raise Http404 from None

        attempt = get_object_or_404(
            SkillTestAttempt,
            pk=pk,
            jobseeker=jobseeker,
        )
        skill_test = attempt.skill_test

        question_results: list[dict[str, Any]] = []
        # pyrefly: ignore [bad-argument-type]
        for i, question in enumerate(skill_test.questions):  # type: ignore[arg-type]
            chosen = attempt.answers.get(str(i))
            question_results.append({
                'index': i,
                'question': question['question'],
                'variants': question['variants'],
                'correct_index': question['correct_index'],
                'chosen_index': chosen,
                'is_correct': chosen == question['correct_index'],
            })

        context = {
            'attempt': attempt,
            'skill_test': skill_test,
            'question_results': question_results,
        }
        return render(request, self.template_name, context)


class SkillTestHistoryView(LoginRequiredMixin, View):
    template_name = const.SKILL_TEST_HISTORY

    def get_jobseeker(self, user: User) -> JobSeeker:
        return get_object_or_404(JobSeeker, user=user)

    def get(self, request: AuthenticatedHttpRequest) -> HttpResponse:
        jobseeker = self.get_jobseeker(request.user)

        attempts = (
            SkillTestAttempt.objects
            .filter(jobseeker=jobseeker)
            .select_related('skill_test', 'skill_test__skill')
            .order_by('-created_at')
        )

        verifications = SkillVerification.objects.filter(
            jobseeker=jobseeker,
        ).select_related('skill')
        verification_map: dict[int, SkillVerification] = {
            # pyrefly: ignore [missing-attribute]
            v.skill_id: v
            for v in verifications
        }

        context = {
            'attempts': attempts,
            'verification_map': verification_map,
        }
        return render(request, self.template_name, context)
