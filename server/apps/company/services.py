from typing import TYPE_CHECKING

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.db.models import QuerySet

from server.apps.company.models import Company, StudentProgram

if TYPE_CHECKING:
    from server.apps.accounts.models import User as UserType

User = get_user_model()


class CompanyService:
    @staticmethod
    def get_company_detail(company_id: int) -> Company | None:
        try:
            return (
                Company.objects
                .select_related(
                    'industry',
                    'recruiter__user',
                )
                .prefetch_related(
                    'benefits',
                    'student_programs',
                )
                .get(pk=company_id)
            )
        except Company.DoesNotExist:
            return None

    @staticmethod
    def can_edit(
        company: Company,
        user: 'UserType | AnonymousUser',
    ) -> bool:
        if not user.is_authenticated:
            return False
        try:
            return company.recruiter_id == user.recruiter.pk  # pyrefly: ignore
        except Exception:
            return False


class StudentProgramService:
    @staticmethod
    def get_company_programs(company_pk: int) -> QuerySet[StudentProgram]:
        return StudentProgram.objects.filter(
            company_id=company_pk,
        ).order_by('-created_at')

    @staticmethod
    def create_program(
        company: Company,
        *,
        title: str,
        description: str = '',
        status: int = StudentProgram.ProgramStatusEnum.APPLICATIONS_OPEN,
        url: str = '',
    ) -> StudentProgram:
        return StudentProgram.objects.create(
            company=company,
            title=title,
            description=description,
            status=status,
            url=url,
        )

    @staticmethod
    def update_program(
        program: StudentProgram,
        *,
        title: str | None = None,
        description: str | None = None,
        status: int | None = None,
        url: str | None = None,
    ) -> StudentProgram:
        if title is not None:
            program.title = title
        if description is not None:
            program.description = description
        if status is not None:
            program.status = status
        if url is not None:
            program.url = url
        program.save()
        return program

    @staticmethod
    def delete_program(program: StudentProgram) -> None:
        program.delete()
