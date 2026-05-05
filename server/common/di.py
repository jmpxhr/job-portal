# from collections.abc import Callable
# from typing import Any, final

# import punq


# def _global_namespace() -> dict[str, Any]:
#     from django.conf import LazySettings  # noqa: F401, PLC0415
#     from django.core.cache import BaseCache  # noqa: F401, PLC0415

#     return locals()


# def _create_injector[Thing](
#     container: punq.Container,
#     localns: dict[str, Any],
# ) -> Callable[[Thing], Thing]:
#     # We need to provide the same string names as we do in the definition.
#     localns.pop('container')
#     localns.update(_global_namespace())
#     container.registrations._localns.update(localns)  # type: ignore[attr-defined]  # noqa: SLF001
#     return lambda service: service


# def _inject_django(container: punq.Container) -> None:
#     from django.conf import LazySettings, settings  # noqa: PLC0415

#     # Django:
#     container.register(
#         LazySettings,
#         instance=settings,
#         scope=punq.Scope.singleton,
#     )


# def _inject_main(container: punq.Container) -> None:
#     # Hacks to resolve annotations:
#     inject = _create_injector(container, locals())

#     # Things to register:


# def _populate_dependencies(container: punq.Container) -> punq.Container:
#     """Populates dependencies for the container."""
#     # Deps:
#     _inject_django(container)
#     # Apps:
#     _inject_main(container)
#     return container


# class HasContainer:
#     """
#     Base class for all parts that use ``resolve()`` function.

#     Must be the first base class.
#     """

#     __slots__ = ('_container',)

#     def __init__(self, *args: Any, **kwargs: Any) -> None:
#         """Create container with dependencies for this class."""
#         super().__init__(*args, **kwargs)
#         self._container = _populate_dependencies(punq.Container())

#     @final
#     def resolve[Thing](self, thing: type[Thing]) -> Thing:
#         """Resolve a dependency."""
#         return self._container.resolve(thing)
