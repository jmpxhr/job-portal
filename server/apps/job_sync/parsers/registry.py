from collections.abc import Callable

from server.apps.job_sync.models import SourceTypeEnum
from server.apps.job_sync.parsers.base import BaseParser

_registry: dict[int, type[BaseParser]] = {}


def register_parser(
    source_type: int,
) -> Callable[[type[BaseParser]], type[BaseParser]]:
    def decorator(
        cls: type[BaseParser],
    ) -> type[BaseParser]:
        _registry[source_type] = cls
        return cls

    return decorator


def get_parser(source_type: int) -> BaseParser | None:
    parser_cls = _registry.get(source_type)
    if parser_cls is None:
        return None
    return parser_cls()


def get_source_type_from_url(url: str) -> int | None:
    if 'praca.by' in url:
        return SourceTypeEnum.PRACA_BY
    if 'career.habr.com' in url:
        return SourceTypeEnum.CAREER_HABR_COM
    return None
