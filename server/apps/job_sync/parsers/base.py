from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ParsedJobData:
    title: str = ''
    description: str = ''
    salary_min: int | None = None
    salary_max: int | None = None
    location: str = ''
    experience_level: int | None = None
    work_format: int | None = None
    schedule: int | None = None
    employment_type: int | None = None
    skills: list[str] = field(default_factory=list)
    external_id: str = ''
    external_url: str = ''
    raw_data: dict[str, object] = field(default_factory=dict)


class BaseParser(ABC):
    source_type: int

    @abstractmethod
    def fetch_listing(self, url: str) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def parse_job_detail(self, url: str) -> ParsedJobData:
        raise NotImplementedError
