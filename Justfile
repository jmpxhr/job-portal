# Default environment settings
set dotenv-load
set positional-arguments

# List all available commands
default:
    @just --list

# Start a new Django app inside the current project
create-app app_name:
    @echo "Creating Django app: {{ app_name }}"
    uv run python manage.py startapp {{ app_name }}
    @echo "App created! Don't forget to add it to INSTALLED_APPS"

# Run development server
dev port="8000":
    @echo "Starting Django development server on port {{ port }}..."
    uv run python manage.py runserver {{ port }}

worker:
    uv run python manage.py db_worker

# Make and run migrations
db-sync:
    @echo "Running migrations..."
    uv run python manage.py makemigrations
    uv run python manage.py migrate

# Run all linters
lint:
    uv run ruff check --exit-non-zero-on-fix
    uv run ruff format --check --diff

# Run all type checkers
type-check:
    uv run mypy .
    uv run pyrefly check --remove-unused-ignores

migrate:
    uv run python manage.py migrate

makemigrations:
    uv run python manage.py makemigrations

# Create a new superuser
createsuperuser:
    uv run python manage.py createsuperuser

# Open Django shell
shell:
    uv run python manage.py shell

# Collect static files
static:
    uv run python manage.py collectstatic --noinput

# Run tests
test args="":
    uv run python manage.py test {{ args }}

# Check for security issues
check:
    uv run python manage.py check

# Freeze requirements
freeze:
    uv lock

# Install requirements
install:
    uv venv
    uv sync
