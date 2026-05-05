# Agents

## Project

**startjob** - Job board for students and career starters.

## Stack

- Django 6.x + Django REST Framework
- Python 3.13 (uv for package management)
- Project structure: `wemake-django-template`
- Settings: `django-split-settings` (controlled by `DJANGO_ENV`)
- Apps: `accounts`, `company`, `jobs`, `dashboard`

## Apps

### `accounts`
- Custom user model (`accounts.User`) with email-based auth
- `User.AccountTypeEnum`: EMPTY, JOBSEEKER, COMPANY
- `JobSeeker` and `Recruiter` profiles linked 1:1 to User
- Email verification via 6-digit code

### `jobs`
- `Job`: title, description, skills (M2M), experience_level, work_format, schedule, employment_type, salary_min/max, location, is_student_friendly
- `JobApplication`: links JobSeeker to Job, status enum (PENDING/ACCEPTED/REJECTED)
- `SavedJob`: bookmarked jobs per JobSeeker
- `Skill`: name + slug (auto-generated from name), used by jobs for filtering/searching

### `company`
- `Company`: name, industry, size, website, description, logo, benefits (M2M), student_programs (M2M)
- `Industry`, `Benefit`, `StudentProgram` (with status enum)

### `dashboard`
- Entry point for frontend routes

## HTMX

- `django_htmx` in INSTALLED_APPS + middleware enabled
- `server/common/types.py`: `HtmxRequest` extends `HttpRequest` with `htmx: HtmxDetails`
- Check via `request.htmx` boolean in views

## django-filter

- `django_filters` in INSTALLED_APPS
- `jobs/filters.py`: `JobFilter` - search by q/title/description, location, employment_type, work_format, experience_level, salary_from, sort (recent/salary_high/salary_low)
- `company/filters.py`: `CompanyFilter` - search by q/name/description, industry, size, letter, sort (name/newest)

## Developer Commands

```bash
just dev          # Run dev server
just lint         # ruff check + format check
just type-check   # mypy + pyrefly
just test         # Django test runner
just db-sync      # makemigrations + migrate
just shell        # Django shell
just createsuperuser
```

**Order matters**: lint -> type-check -> test

## Architecture

- `server/settings/` - split settings (components + environments)
- `DJANGO_ENV` env var selects environment: `development`, `production`, or `local` override
- `BASE_DIR` resolves to `server/`
- `AUTH_USER_MODEL = 'accounts.User'`
- Migrations ignored by ruff and mypy

## Lint/Type Config

- `pyproject.toml`: ruff, mypy, pyrefly, djlint
- Migration files excluded from linting (`**/migrations/*.py`)
- mypy uses `django-stubs` + `djangorestframework-stubs`
- `DJANGO_SETTINGS_MODULE = "server.settings"`

## Env

- `config/.env` - local secrets (not committed)
- `config/.env.template` - template for env vars
