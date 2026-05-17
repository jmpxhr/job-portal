import string

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from server.apps.company import const, filters, forms
from server.apps.company.models import Company, Industry, StudentProgram
from server.apps.company.services import (
    CompanyService,
    StudentProgramService,
)
from server.apps.job_sync.models import ExternalSource as ExternalSourceModel
from server.apps.jobs.models import Job
from server.common.types import HtmxRequest


class CompanyListView(View):
    def get(self, request: HtmxRequest) -> HttpResponse:
        company_filter = filters.CompanyFilter(
            request.GET,
            queryset=Company.objects
            .select_related(
                'industry',
                'recruiter__user',
            )
            .prefetch_related('benefits')
            .annotate(
                _open_jobs_count=Count(
                    'jobs',
                    filter=Q(jobs__is_active=True),
                ),
            ),
        )

        paginator = Paginator(company_filter.qs, 12)
        page_number = request.GET.get('page', 1)
        page = paginator.get_page(page_number)

        current_letter = request.GET.get('letter', '')
        current_sort = request.GET.get('sort', '')
        current_size = request.GET.get('size', '')
        current_industry = request.GET.get('industry', '')
        search_query = request.GET.get('q', '')

        context = {
            'companies': page,
            'page_obj': page,
            'filter': company_filter,
            'industries': Industry.objects.all(),
            'size_choices': Company.CompanySizeEnum.choices,
            'alphabet': list(string.ascii_uppercase),
            'current_letter': current_letter,
            'current_industry': current_industry,
            'current_size': current_size,
            'current_sort': current_sort,
            'search_query': search_query,
        }
        if request.htmx:
            return render(request, const.COMPANY_LIST + '#companies', context)

        return render(request, const.COMPANY_LIST, context)


class CompanyDetailView(View):
    def get(self, request: HttpRequest, pk: int) -> HttpResponse:
        company = get_object_or_404(
            Company.objects
            .select_related(
                'industry',
                'recruiter__user',
            )
            .prefetch_related('benefits', 'student_programs')
            .annotate(
                _open_jobs_count=Count(
                    'jobs',
                    filter=Q(jobs__is_active=True),
                ),
            ),
            pk=pk,
        )
        can_edit = CompanyService.can_edit(
            company,
            request.user,  # pyrefly: ignore
        )

        external_sources = []
        if can_edit:
            external_sources = list(
                ExternalSourceModel.objects.filter(
                    company=company,
                ).order_by('source_type'),
            )

        open_jobs = (
            Job.objects
            .filter(company=company, is_active=True)
            .select_related('company')
            .prefetch_related('skills')
            .annotate(applicants_count=Count('applications'))
            .order_by('-posted_at')
        )

        context = {
            'company': company,
            'can_edit': can_edit,
            'open_jobs': open_jobs,
            'employment_type_choices': Job.EmploymentTypeEnum.choices,
            'external_sources': external_sources,
        }
        return render(request, const.COMPANY_DETAIL, context)


class CompanyEditView(LoginRequiredMixin, View):
    def get(self, request: HttpRequest, pk: int) -> HttpResponse:
        company = get_object_or_404(Company, pk=pk)

        if not CompanyService.can_edit(
            company,
            request.user,  # pyrefly: ignore
        ):
            return redirect('company:company-detail', pk=pk)

        form = forms.CompanyUpdateForm(instance=company)
        context = {
            'form': form,
            'company': company,
        }
        return render(request, const.COMPANY_EDIT_PARTIAL, context)

    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        company = get_object_or_404(Company, pk=pk)

        if not CompanyService.can_edit(
            company,
            request.user,  # pyrefly: ignore
        ):
            return redirect('company:company-detail', pk=pk)

        form = forms.CompanyUpdateForm(
            request.POST,
            request.FILES,
            instance=company,
        )

        if form.is_valid():
            form.save()
            company.refresh_from_db()
            open_jobs = (
                Job.objects
                .filter(company=company, is_active=True)
                .select_related('company')
                .prefetch_related('skills')
                .order_by('-posted_at')
            )
            return render(
                request,
                const.COMPANY_VIEW_PARTIAL,
                {
                    'company': company,
                    'can_edit': True,
                    'open_jobs': open_jobs,
                    'employment_type_choices': Job.EmploymentTypeEnum.choices,
                },
            )

        context = {
            'form': form,
            'company': company,
        }
        return render(request, const.COMPANY_EDIT_PARTIAL, context)


class StudentProgramCreateView(LoginRequiredMixin, View):
    def get(self, request: HttpRequest, pk: int) -> HttpResponse:
        company = get_object_or_404(Company, pk=pk)

        if not CompanyService.can_edit(
            company,
            request.user,  # pyrefly: ignore
        ):
            return redirect('company:company-detail', pk=pk)

        form = forms.StudentProgramForm()
        context = {
            'form': form,
            'company': company,
        }
        return render(request, const.STUDENT_PROGRAM_FORM, context)

    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        company = get_object_or_404(Company, pk=pk)

        if not CompanyService.can_edit(
            company,
            request.user,  # pyrefly: ignore
        ):
            return redirect('company:company-detail', pk=pk)

        form = forms.StudentProgramForm(request.POST)
        if form.is_valid():
            program = form.save(commit=False)
            program.company = company
            program.save()

            return render(
                request,
                const.STUDENT_PROGRAM_LIST,
                {
                    'company': company,
                    'student_programs': (
                        StudentProgramService.get_company_programs(
                            company.pk,
                        )
                    ),
                    'can_edit': True,
                },
            )

        context = {
            'form': form,
            'company': company,
        }
        return render(request, const.STUDENT_PROGRAM_FORM, context)


class StudentProgramUpdateView(LoginRequiredMixin, View):
    def get(
        self,
        request: HttpRequest,
        pk: int,
        program_pk: int,
    ) -> HttpResponse:
        company = get_object_or_404(Company, pk=pk)
        program = get_object_or_404(
            StudentProgram,
            pk=program_pk,
            company=company,
        )

        if not CompanyService.can_edit(
            company,
            request.user,  # pyrefly: ignore
        ):
            return redirect('company:company-detail', pk=pk)

        form = forms.StudentProgramForm(instance=program)
        context = {
            'form': form,
            'company': company,
            'program': program,
        }
        return render(request, const.STUDENT_PROGRAM_FORM, context)

    def post(
        self,
        request: HttpRequest,
        pk: int,
        program_pk: int,
    ) -> HttpResponse:
        company = get_object_or_404(Company, pk=pk)
        program = get_object_or_404(
            StudentProgram,
            pk=program_pk,
            company=company,
        )

        if not CompanyService.can_edit(
            company,
            request.user,  # pyrefly: ignore
        ):
            return redirect('company:company-detail', pk=pk)

        form = forms.StudentProgramForm(
            request.POST,
            instance=program,
        )
        if form.is_valid():
            form.save()

            return render(
                request,
                const.STUDENT_PROGRAM_LIST,
                {
                    'company': company,
                    'student_programs': (
                        StudentProgramService.get_company_programs(
                            company.pk,
                        )
                    ),
                    'can_edit': True,
                },
            )

        context = {
            'form': form,
            'company': company,
            'program': program,
        }
        return render(request, const.STUDENT_PROGRAM_FORM, context)


class StudentProgramDeleteView(LoginRequiredMixin, View):
    def get(
        self,
        request: HttpRequest,
        pk: int,
        program_pk: int,
    ) -> HttpResponse:
        company = get_object_or_404(Company, pk=pk)
        program = get_object_or_404(
            StudentProgram,
            pk=program_pk,
            company=company,
        )

        if not CompanyService.can_edit(
            company,
            request.user,  # pyrefly: ignore
        ):
            return redirect('company:company-detail', pk=pk)

        context = {
            'company': company,
            'program': program,
        }
        return render(
            request,
            const.STUDENT_PROGRAM_CONFIRM_DELETE,
            context,
        )

    def post(
        self,
        request: HttpRequest,
        pk: int,
        program_pk: int,
    ) -> HttpResponse:
        company = get_object_or_404(Company, pk=pk)
        program = get_object_or_404(
            StudentProgram,
            pk=program_pk,
            company=company,
        )

        if not CompanyService.can_edit(
            company,
            request.user,  # pyrefly: ignore
        ):
            return redirect('company:company-detail', pk=pk)

        StudentProgramService.delete_program(program)

        return render(
            request,
            const.STUDENT_PROGRAM_LIST,
            {
                'company': company,
                'student_programs': (
                    StudentProgramService.get_company_programs(
                        company.pk,
                    )
                ),
                'can_edit': True,
            },
        )
