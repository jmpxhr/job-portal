import string

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from server.apps.company import const, filters, forms
from server.apps.company.models import Company, Industry, StudentProgram
from server.apps.company.services import (
    CompanyService,
    StudentProgramService,
)


class CompanyListView(View):
    def get(self, request: HttpRequest) -> HttpResponse:
        company_filter = filters.CompanyFilter(
            request.GET,
            queryset=Company.objects.select_related(
                'industry',
                'recruiter__user',
            ).prefetch_related('benefits'),
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
        return render(request, const.COMPANY_LIST, context)


class CompanyDetailView(View):
    def get(self, request: HttpRequest, pk: int) -> HttpResponse:
        company = get_object_or_404(
            Company.objects.select_related(
                'industry',
                'recruiter__user',
            ).prefetch_related('benefits', 'student_programs'),
            pk=pk,
        )
        can_edit = CompanyService.can_edit(  # pyrefly: ignore
            company,
            request.user,  # pyrefly: ignore
        )

        context = {
            'company': company,
            'can_edit': can_edit,
        }
        return render(request, const.COMPANY_DETAIL, context)


class CompanyEditView(LoginRequiredMixin, View):
    def get(self, request: HttpRequest, pk: int) -> HttpResponse:
        company = get_object_or_404(Company, pk=pk)

        if not CompanyService.can_edit(  # pyrefly: ignore
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

        if not CompanyService.can_edit(  # pyrefly: ignore
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
            return render(
                request,
                const.COMPANY_VIEW_PARTIAL,
                {
                    'company': company,
                    'can_edit': True,
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

        if not CompanyService.can_edit(  # pyrefly: ignore
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

        if not CompanyService.can_edit(  # pyrefly: ignore
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

        if not CompanyService.can_edit(  # pyrefly: ignore
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

        if not CompanyService.can_edit(  # pyrefly: ignore
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

        if not CompanyService.can_edit(  # pyrefly: ignore
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

        if not CompanyService.can_edit(  # pyrefly: ignore
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
