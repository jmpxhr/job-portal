from typing import Any

from django import template

register = template.Library()


@register.filter(name='keyvalue')
def keyvalue(d: dict, key: Any) -> Any:  # type: ignore[type-arg]
    try:
        return d[key]
    except KeyError:
        return ''
