from typing import Any

import lmstudio as lms
from django.conf import settings
from pydantic import BaseModel, Field

SUITABILITY_HIGH = 'high'
SUITABILITY_MEDIUM = 'medium'
SUITABILITY_LOW = 'low'

LANGUAGE_NAMES: dict[str, str] = {
    'en': 'English',
    'ru': 'Russian',
}


class JobAdviceResponse(BaseModel):
    suitability: str = Field(
        description='Overall suitability assessment: "high", "medium", or "low"',  # noqa: E501
    )
    summary: str = Field(
        description='A 2-3 sentence summary of the candidate fit for this position',  # noqa: E501
    )
    matching_skills: list[str] = Field(
        description='Skills the candidate has that match the job requirements',
    )
    missing_skills: list[str] = Field(
        description='Skills required by the job that the candidate is missing',
    )
    strengths: list[str] = Field(
        description='Candidate strengths relevant to this position',
    )
    areas_to_improve: list[str] = Field(
        description='Specific areas where the candidate should improve for this role',  # noqa: E501
    )
    recommendations: list[str] = Field(
        description='Actionable recommendations for the candidate',
    )


class JobAdviceSerializer:
    @staticmethod
    def serialize_jobseeker(jobseeker: Any) -> dict[str, Any]:
        education_data = [
            {
                'level': edu.get_level_label(),
                'institution': edu.institution_name,
                'faculty': edu.faculty,
                'specialization': edu.specialization,
                'year': edu.year_of_graduation,
            }
            for edu in jobseeker.education.all()
        ]

        experience_data = [
            {
                'position': exp.position,
                'company': exp.company_name,
                'start_date': str(exp.start_date),
                'end_date': str(exp.end_date) if exp.end_date else 'present',
                'description': exp.description,
            }
            for exp in jobseeker.experience.all()
        ]

        language_data = [
            {
                'name': lang.name,
                'proficiency': lang.get_proficiency_label(),
            }
            for lang in jobseeker.languages.all()
        ]

        return {
            'title': jobseeker.title,
            'about': jobseeker.about,
            'location': jobseeker.location,
            'resume_objective': jobseeker.resume_objective,
            'skills': [skill.name for skill in jobseeker.skills.all()],
            'education': education_data,
            'experience': experience_data,
            'languages': language_data,
        }

    @staticmethod
    def serialize_job(job: Any) -> dict[str, Any]:
        salary_info = ''
        if job.salary_min and job.salary_max:
            salary_info = f'{job.salary_min}-{job.salary_max}'
        elif job.salary_min:
            salary_info = f'from {job.salary_min}'
        elif job.salary_max:
            salary_info = f'up to {job.salary_max}'

        return {
            'title': job.title,
            'description': job.description,
            'experience_level': job.experience_level_label,
            'work_format': job.work_format_label,
            'schedule': job.schedule_label,
            'employment_type': job.employment_type_label,
            'salary': salary_info,
            'location': job.location,
            'is_student_friendly': job.is_student_friendly,
            'skills': [skill.name for skill in job.skills.all()],
            'company': {
                'name': job.company.name,
                'industry': str(job.company.industry)
                if hasattr(job.company, 'industry') and job.company.industry
                else '',
                'size': job.company.display_size
                if hasattr(job.company, 'display_size')
                else '',
            },
        }


class JobAdviceGenerator:
    def _get_model(self) -> Any:
        model_identifier = getattr(settings, 'LMSTUDIO_MODEL', '')
        if model_identifier:
            return lms.llm(model_identifier)
        return lms.llm()

    def _build_prompt(  # noqa: C901
        self,
        jobseeker_data: dict[str, Any],
        job_data: dict[str, Any],
        language: str = 'en',
    ) -> str:
        language_name = LANGUAGE_NAMES.get(language, language)

        jobseeker_lines = [
            '## Candidate Profile',
        ]
        if jobseeker_data.get('title'):
            jobseeker_lines.append(
                f'- Title/Headline: {jobseeker_data["title"]}',
            )
        if jobseeker_data.get('about'):
            jobseeker_lines.append(f'- About: {jobseeker_data["about"]}')
        if jobseeker_data.get('location'):
            jobseeker_lines.append(f'- Location: {jobseeker_data["location"]}')
        if jobseeker_data.get('resume_objective'):
            jobseeker_lines.append(
                f'- Career Objective: {jobseeker_data["resume_objective"]}',
            )
        if jobseeker_data.get('skills'):
            jobseeker_lines.append(
                f'- Skills: {", ".join(jobseeker_data["skills"])}',
            )
        for i, exp in enumerate(jobseeker_data.get('experience', []), 1):
            jobseeker_lines.append(
                f'- Experience {i}: {exp["position"]} at {exp["company"]} ({exp["start_date"]} - {exp["end_date"]})',  # noqa: E501
            )
            if exp.get('description'):
                jobseeker_lines.append(f'  {exp["description"]}')
        for i, edu in enumerate(jobseeker_data.get('education', []), 1):
            jobseeker_lines.append(
                f'- Education {i}: {edu["level"]} at {edu["institution"]}',
            )
            if edu.get('specialization'):
                jobseeker_lines.append(
                    f'  Specialization: {edu["specialization"]}',
                )
            if edu.get('year'):
                jobseeker_lines.append(f'  Year: {edu["year"]}')
        if jobseeker_data.get('languages'):
            lang_str = ', '.join(
                f'{l["name"]} ({l["proficiency"]})'
                for l in jobseeker_data['languages']  # noqa: E741
            )
            jobseeker_lines.append(f'- Languages: {lang_str}')

        job_lines = [
            '## Job Requirements',
            f'- Title: {job_data["title"]}',
            f'- Experience Level: {job_data["experience_level"]}',
            f'- Work Format: {job_data["work_format"]}',
            f'- Schedule: {job_data["schedule"]}',
            f'- Employment Type: {job_data["employment_type"]}',
        ]
        if job_data.get('location'):
            job_lines.append(f'- Location: {job_data["location"]}')
        if job_data.get('salary'):
            job_lines.append(f'- Salary: {job_data["salary"]}')
        if job_data.get('is_student_friendly'):
            job_lines.append('- Student Friendly: Yes')
        if job_data.get('skills'):
            job_lines.append(
                f'- Required Skills: {", ".join(job_data["skills"])}',
            )
        if job_data.get('company'):
            if job_data['company'].get('name'):
                job_lines.append(f'- Company: {job_data["company"]["name"]}')
            if job_data['company'].get('industry'):
                job_lines.append(
                    f'- Industry: {job_data["company"]["industry"]}',
                )
        if job_data.get('description'):
            desc = job_data['description']
            if len(desc) > 2000:
                desc = desc[:2000] + '...'
            job_lines.append(f'- Description: {desc}')

        candidate_section = '\n'.join(jobseeker_lines)
        job_section = '\n'.join(job_lines)

        return (
            f'You are a career advisor AI. Analyze how well a candidate fits a job posting '  # noqa: E501
            f'and provide detailed, actionable advice.\n\n'
            f'{candidate_section}\n\n'
            f'{job_section}\n\n'
            f'Based on the candidate profile and job requirements above, provide:\n'  # noqa: E501
            f'1. An overall suitability rating: "high", "medium", or "low"\n'
            f'2. A brief summary (2-3 sentences) of the candidate fit\n'
            f'3. Which of the job required skills the candidate already has (matching_skills)\n'  # noqa: E501
            f'4. Which skills the candidate is missing for this role (missing_skills)\n'  # noqa: E501
            f'5. The candidate strengths relevant to this position (strengths)\n'  # noqa: E501
            f'6. Areas where the candidate should improve for this role (areas_to_improve)\n'  # noqa: E501
            f'7. Actionable recommendations for the candidate (recommendations)\n\n'  # noqa: E501
            f'Be specific and practical. Reference actual skills and experience from the profile. '  # noqa: E501
            f'Respond in {language_name}.'
        )

    def generate(
        self,
        jobseeker: Any,
        job: Any,
        language: str = 'en',
    ) -> dict[str, Any]:
        jobseeker_data = JobAdviceSerializer.serialize_jobseeker(jobseeker)
        job_data = JobAdviceSerializer.serialize_job(job)
        model = self._get_model()
        prompt = self._build_prompt(jobseeker_data, job_data, language)
        result = model.respond(prompt, response_format=JobAdviceResponse)
        return dict(result.parsed)
