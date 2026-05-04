from django import template

register = template.Library()


@register.filter
def filename(value: str) -> str:
    return value.split('/')[-1]  # noqa: PLC0207
