from __future__ import annotations

import json
import logging
import re
from typing import Any, override

import httpx
from bs4 import BeautifulSoup

from server.apps.job_sync.models import SourceTypeEnum
from server.apps.job_sync.parsers.base import BaseParser, ParsedJobData
from server.apps.job_sync.parsers.registry import register_parser

logger = logging.getLogger('django')

_BASE_URL = 'https://praca.by'

_EXPERIENCE_MAP: dict[str, int] = {
    'не требуется': 1,
    'без опыта': 1,
    'нет опыта': 1,
    'от 1 года': 2,
    'от 1 до 3': 2,
    '1-3 года': 2,
    'от 3 до 6': 3,
    '3-6 лет': 3,
    'более 6': 4,
    'больше 6': 4,
    'от 6 лет': 4,
}

_EMPLOYMENT_TYPE_MAP: dict[str, int] = {
    'полная': 0,
    'full_time': 0,
    'частичная': 1,
    'part_time': 1,
    'стажировка': 2,
    'интернатура': 2,
    'internship': 2,
}

_WORK_FORMAT_MAP: dict[str, int] = {
    'на территории работодателя': 2,
    'удалённая работа': 0,
    'удаленная работа': 0,
    'удаленно': 0,
    'гибрид': 1,
    'смешанный': 1,
}

_SCHEDULE_MAP: dict[str, int] = {
    'фиксированный': 0,
    'гибкий': 1,
    'гибкого': 1,
    'свободный': 1,
}


def _match_enum(text: str, mapping: dict[str, int]) -> int | None:
    lower = text.lower().strip()
    for key, value in mapping.items():
        if key in lower:
            return value
    return None


def _parse_salary_text(
    text: str,
) -> tuple[int | None, int | None]:
    text = text.lower().replace('\xa0', '').replace(' ', '').strip()
    salary_min: int | None = None
    salary_max: int | None = None

    from_match = re.search(r'от(\d+)', text)
    to_match = re.search(r'до(\d+)', text)

    if from_match and to_match:
        salary_min = int(from_match.group(1))
        salary_max = int(to_match.group(1))
    elif from_match:
        salary_min = int(from_match.group(1))
    elif to_match:
        salary_max = int(to_match.group(1))
    else:
        range_match = re.search(r'(\d+)[^\d]+(\d+)', text)
        if range_match:
            salary_min = int(range_match.group(1))
            salary_max = int(range_match.group(2))
        else:
            single_match = re.search(r'(\d+)', text)
            if single_match:
                salary_min = int(single_match.group(1))

    return salary_min, salary_max


def _find_job_posting(data: dict[str, Any]) -> dict[str, Any] | None:
    graph: list[Any] = data.get('@graph', [])
    for item in graph:
        if isinstance(item, dict) and item.get('@type') == 'JobPosting':
            return item
    if data.get('@type') == 'JobPosting':
        return data
    return None


def _parse_ld_json(soup: BeautifulSoup) -> dict[str, Any] | None:
    scripts = soup.select('script[type="application/ld+json"]')
    for script in scripts:
        content = script.string
        if not content:
            continue
        cleaned = re.sub(r'//<!--|//-->', '', content).strip()
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            continue
        result = _find_job_posting(data)
        if result:
            return result
    return None


def _extract_ld_location(ld_data: dict[str, Any]) -> str:
    try:
        address = ld_data['jobLocation']['address']
        parts = [
            address.get('addressLocality', ''),
            address.get('addressRegion', ''),
        ]
        return ', '.join(p for p in parts if p)
    except (KeyError, TypeError):
        return ''


def _extract_ld_salary(
    ld_data: dict[str, Any],
) -> tuple[int | None, int | None]:
    try:
        salary = ld_data['baseSalary']['value']
        value = salary.get('value')
        if isinstance(value, (int, float)):
            return int(value), None
        if isinstance(value, dict):
            min_val = value.get('minValue')
            max_val = value.get('maxValue')
            return (
                int(min_val) if min_val is not None else None,
                int(max_val) if max_val is not None else None,
            )
    except (KeyError, TypeError):
        pass
    return None, None


def _extract_work_schedule(soup: BeautifulSoup) -> dict[str, Any]:
    result: dict[str, Any] = {}
    items = soup.select('div.vacancy__item')
    for item in items:
        icon = item.select_one('i')
        text = item.get_text(strip=True)
        if not icon:
            continue
        icon_classes_raw: Any = icon.get('class')
        icon_classes = (
            ' '.join(icon_classes_raw)
            if isinstance(icon_classes_raw, list)
            else str(icon_classes_raw)
        )
        if 'icon-chair' in icon_classes:
            result['work_format'] = _match_enum(
                text,
                _WORK_FORMAT_MAP,
            )
        elif 'icon-schedule' in icon_classes:
            result['schedule'] = _match_enum(
                text,
                _SCHEDULE_MAP,
            )
        elif 'icon-employment' in icon_classes:
            result['employment_type'] = _match_enum(
                text,
                _EMPLOYMENT_TYPE_MAP,
            )
    return result


def _extract_simple_field(
    soup: BeautifulSoup,
    selector: str,
    field: str,
    result: dict[str, Any],
    *,
    match_enum: bool = False,
) -> None:
    el = soup.select_one(selector)
    if not el:
        return
    text = el.get_text(strip=True)
    if match_enum:
        result[field] = _match_enum(text, _EXPERIENCE_MAP)
    else:
        result[field] = text


def _extract_text_fields(
    soup: BeautifulSoup,
    result: dict[str, Any],
) -> None:
    _extract_simple_field(
        soup,
        'div.vacancy__title h1',
        'title',
        result,
    )
    _extract_simple_field(
        soup,
        'div.vacancy__city',
        'location',
        result,
    )
    _extract_simple_field(
        soup,
        'p.vacancy__experience',
        'experience_level',
        result,
        match_enum=True,
    )

    desc_el = soup.select_one('div.vacancy__description div.description')
    if desc_el:
        result['description'] = desc_el.decode_contents().strip()

    salary_el = soup.select_one('div.vacancy__salary')
    if salary_el:
        s_min, s_max = _parse_salary_text(
            salary_el.get_text(strip=True),
        )
        if s_min is not None:
            result['salary_min'] = s_min
        if s_max is not None:
            result['salary_max'] = s_max

    skills = soup.select('div.vacancy__skills span.skills_tile')
    result['skills'] = [s.get_text(strip=True) for s in skills]


def _parse_html_fields(soup: BeautifulSoup) -> dict[str, Any]:
    result = _extract_work_schedule(soup)
    _extract_text_fields(soup, result)
    return result


def _fill_from_ld(
    data: ParsedJobData,
    ld_data: dict[str, Any],
) -> ParsedJobData:
    data.title = ld_data.get('title', '') or data.title
    data.description = ld_data.get('description', '') or data.description
    if not data.location:
        data.location = _extract_ld_location(ld_data)
    if data.salary_min is None and data.salary_max is None:
        data.salary_min, data.salary_max = _extract_ld_salary(ld_data)
    employment = ld_data.get('employmentType', [])
    if isinstance(employment, str):
        employment = [employment]
    if employment and data.employment_type is None:
        data.employment_type = _match_enum(
            employment[0],
            _EMPLOYMENT_TYPE_MAP,
        )
    return data


def _fill_from_html(
    data: ParsedJobData,
    html_data: dict[str, Any],
) -> ParsedJobData:
    str_fallbacks: dict[str, str] = {
        'title': '',
        'description': '',
        'location': '',
    }
    for field, default in str_fallbacks.items():
        current = getattr(data, field, default)
        if not current:
            setattr(data, field, html_data.get(field, default))

    optional_fields = [
        'salary_min',
        'salary_max',
        'experience_level',
        'work_format',
        'schedule',
        'employment_type',
    ]
    for field in optional_fields:
        if getattr(data, field) is None:
            setattr(data, field, html_data.get(field))

    if not data.skills:
        data.skills = html_data.get('skills', [])
    return data


@register_parser(SourceTypeEnum.PRACA_BY)
class PracaByParser(BaseParser):
    source_type = SourceTypeEnum.PRACA_BY

    def __init__(self) -> None:
        self._client = httpx.Client(
            timeout=30,
            follow_redirects=True,
            headers={
                'User-Agent': (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/125.0.0.0 Safari/537.36'
                ),
            },
        )

    @override
    def fetch_listing(self, url: str) -> list[str]:
        job_urls: list[str] = []
        page = 1

        while True:
            page_url = self._build_page_url(url, page)
            page_links = self._fetch_page_links(page_url)
            if not page_links:
                break
            job_urls.extend(page_links)

            if not self._has_next_page(page_url, page):
                break
            page += 1

        return job_urls

    @override
    def parse_job_detail(self, url: str) -> ParsedJobData:
        try:
            resp = self._client.get(url)
            resp.raise_for_status()
        except httpx.HTTPError:
            logger.exception('Failed to fetch job detail: %s', url)
            return ParsedJobData(external_url=url)

        soup = BeautifulSoup(resp.text, 'html.parser')
        external_id = self._extract_id(url)
        data = ParsedJobData(
            external_id=external_id,
            external_url=url,
        )

        ld_data = _parse_ld_json(soup)
        if ld_data:
            data = _fill_from_ld(data, ld_data)

        html_data = _parse_html_fields(soup)
        data = _fill_from_html(data, html_data)

        data.raw_data = {
            'ld_json': ld_data,
            'html_fields': html_data,
            'source_url': url,
        }
        return data

    @staticmethod
    def _build_page_url(url: str, page: int) -> str:
        if page <= 1:
            return url
        separator = '&' if '?' in url else '?'
        return f'{url}{separator}page={page}'

    def _fetch_page_links(self, page_url: str) -> list[str]:
        try:
            resp = self._client.get(page_url)
            resp.raise_for_status()
        except httpx.HTTPError:
            logger.exception('Failed to fetch listing: %s', page_url)
            return []

        soup = BeautifulSoup(resp.text, 'html.parser')
        links = soup.select('a.vac-small__title-link')
        result: list[str] = []
        for link in links:
            href = link.get('href', '')
            if isinstance(href, str) and href.startswith('/'):
                href = f'{_BASE_URL}{href}'
            elif isinstance(href, str):
                pass
            else:
                continue
            result.append(href)
        return result

    def _has_next_page(self, url: str, current_page: int) -> bool:
        try:
            resp = self._client.get(url)
            resp.raise_for_status()
        except httpx.HTTPError:
            return False

        soup = BeautifulSoup(resp.text, 'html.parser')
        pagination = soup.select('ul.pagination li a')
        return any(
            '?page=' in str(p.get('href', ''))
            and str(current_page + 1) in str(p.get('href', ''))
            for p in pagination
        )

    @staticmethod
    def _extract_id(url: str) -> str:
        match = re.search(r'/vacancy/(\d+)', url)
        return match.group(1) if match else url.rstrip('/').split('/')[-1]
