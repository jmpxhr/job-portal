# pyrefly: ignore [untyped-import]
import markdown  # type: ignore[import-untyped]
from django import template
from django.utils.safestring import SafeString, mark_safe

register = template.Library()


@register.filter(name='render_markdown')
def render_markdown(text: str) -> str | SafeString:
    if not text:
        return ''
    html = markdown.markdown(
        text,
        extensions=['fenced_code', 'codehilite', 'tables'],
        # pyrefly: ignore [unexpected-keyword]
        extension_defaults={
            'codehilite': {
                'css_class': 'highlight',
                'guess_lang': True,
            },
        },
    )
    return mark_safe(html)  # type: ignore[no-any-return] # noqa: S308
