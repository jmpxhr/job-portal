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

_BASE_URL = 'https://career.habr.com'

_GRADE_MAP: dict[str, int] = {
    'intern': 1,
    'стажёр': 1,
    'стажер': 1,
    'junior': 2,
    'младший': 2,
    'middle': 3,
    'средний': 3,
    'senior': 4,
    'старший': 4,
    'lead': 4,
    'ведущий': 4,
}

_WORK_FORMAT_REMOTE = 'можно удалённ'
_WORK_FORMAT_REMOTE_ALT = 'можно удаленн'

_WORK_FORMAT_MAP: dict[str, int] = {
    _WORK_FORMAT_REMOTE: 0,
    _WORK_FORMAT_REMOTE_ALT: 0,
    'удалённ': 0,
    'удаленн': 0,
    'remote': 0,
    'гибрид': 1,
    'hybrid': 1,
    'офис': 2,
    'на территории': 2,
}

_EMPLOYMENT_TYPE_MAP: dict[str, int] = {
    'full_time': 0,
    'полная': 0,
    'full-time': 0,
    'part_time': 1,
    'частичн': 1,
    'part-time': 1,
    'неполный': 1,
    'contract': 1,
    'internship': 2,
    'стажир': 2,
    'стажировка': 2,
}


def _match_enum(text: str, mapping: dict[str, int]) -> int | None:
    lower = text.lower().strip()
    for key, value in mapping.items():
        if key in lower:
            return value
    return None


def _parse_salary_text(text: str) -> tuple[int | None, int | None]:
    text = text.lower().replace('\xa0', '').replace(' ', '').strip()
    text = re.sub(r'[^\d\-]', '', text)

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
        range_match = re.search(r'(\d+)\-(\d+)', text)
        if range_match:
            salary_min = int(range_match.group(1))
            salary_max = int(range_match.group(2))
        else:
            single_match = re.search(r'(\d+)', text)
            if single_match:
                salary_min = int(single_match.group(1))

    return salary_min, salary_max


def _find_job_posting(data: dict[str, Any]) -> dict[str, Any] | None:
    data_type = data.get('@type')
    if data_type == 'JobPosting':
        return data

    graph: list[Any] = data.get('@graph', [])
    for item in graph:
        if isinstance(item, dict) and item.get('@type') == 'JobPosting':
            return item

    return None


def _parse_ld_json(soup: BeautifulSoup) -> dict[str, Any] | None:
    scripts = soup.select('script[type="application/ld+json"]')
    for script in scripts:
        content = script.string
        if not content:
            continue
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            continue
        result = _find_job_posting(data)
        if result:
            return result
    return None


def _extract_ld_location(ld_data: dict[str, Any]) -> str:
    try:
        location = ld_data['jobLocation']
        if isinstance(location, str):
            return location
        address = location.get('address', {})
        if isinstance(address, str):
            return address
        parts = [
            address.get('addressLocality', ''),
            address.get('addressRegion', ''),
            address.get('addressCountry', ''),
        ]
        return ', '.join(p for p in parts if p)
    except (KeyError, TypeError, AttributeError):
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


def _fill_ld_str_field(
    data: ParsedJobData,
    ld_data: dict[str, Any],
    field: str,
    ld_key: str,
) -> None:
    ld_value = ld_data.get(ld_key, '')
    if ld_value:
        current = getattr(data, field, '')
        if not current:
            setattr(data, field, ld_value)


def _fill_from_ld(
    data: ParsedJobData,
    ld_data: dict[str, Any],
) -> ParsedJobData:
    _fill_ld_str_field(data, ld_data, 'title', 'title')
    _fill_ld_str_field(data, ld_data, 'description', 'description')

    if not data.location:
        data.location = _extract_ld_location(ld_data)

    if data.salary_min is None and data.salary_max is None:
        data.salary_min, data.salary_max = _extract_ld_salary(
            ld_data,
        )

    employment = ld_data.get('employmentType', [])
    if isinstance(employment, str):
        employment = [employment]
    if employment and data.employment_type is None:
        data.employment_type = _match_first_enum(
            employment,
            _EMPLOYMENT_TYPE_MAP,
        )

    location_type = ld_data.get('jobLocationType', '')
    if location_type == 'TELECOMMUTE' and data.work_format is None:
        data.work_format = 0

    return data


def _match_first_enum(
    values: list[str],
    mapping: dict[str, int],
) -> int | None:
    for value in values:
        matched = _match_enum(value, mapping)
        if matched is not None:
            return matched
    return None


def _parse_skills(soup: BeautifulSoup) -> list[str]:
    skills: list[str] = []
    chip_links = soup.select(
        'a.basic-chip--color-ui-gray-4.vacancy-card__skills-chip',
    )
    if chip_links:
        for link in chip_links:
            text = link.get_text(strip=True)
            if text:
                skills.append(text)
        return skills

    chip_divs = soup.select(
        'div.basic-chip--color-ui-gray-4:not([class*="chip-with-icon"])',
    )
    for chip in chip_divs:
        text = chip.get_text(strip=True)
        if text:
            skills.append(text)
    return skills


def _classify_chip(
    chip: Any,
    result: dict[str, Any],
) -> None:
    text = chip.get_text(strip=True)
    icon = chip.select_one('svg use')
    if not icon:
        grade_match = _match_enum(text, _GRADE_MAP)
        if grade_match is not None:
            result['experience_level'] = grade_match
        return

    href = str(icon.get('xlink:href', '') or icon.get('href', '') or '')

    if 'icon-grade' in href:
        result['experience_level'] = _match_enum(
            text,
            _GRADE_MAP,
        )
    elif 'icon-format' in href:
        result['work_format'] = _match_enum(
            text,
            _WORK_FORMAT_MAP,
        )
    elif 'icon-time' in href:
        result['employment_type'] = _match_enum(
            text,
            _EMPLOYMENT_TYPE_MAP,
        )


def _parse_meta_chips(soup: BeautifulSoup) -> dict[str, Any]:
    result: dict[str, Any] = {}
    header = soup.select_one('div.vacancy-header')
    container = header or soup
    chips = container.select('div.basic-chip')
    for chip in chips:
        _classify_chip(chip, result)
    return result


_SALARY_NOT_SPECIFIED = 'не указана'


def _parse_salary_html(
    soup: BeautifulSoup,
) -> tuple[int | None, int | None]:
    salary_el = soup.select_one('div.vacancy-header__salary')
    if salary_el:
        s_min, s_max = _parse_salary_text(
            salary_el.get_text(strip=True),
        )
        if s_min is not None or s_max is not None:
            return s_min, s_max

    for el in soup.select('h4.predicted-salary__title'):
        text = el.get_text(strip=True)
        if _SALARY_NOT_SPECIFIED not in text.lower():
            s_min, s_max = _parse_salary_text(text)
            if s_min is not None or s_max is not None:
                return s_min, s_max

    return None, None


def _parse_title(soup: BeautifulSoup) -> str:
    title_el = soup.select_one('h1.page-title__title')
    if title_el:
        return title_el.get_text(strip=True)
    return ''


def _parse_description(soup: BeautifulSoup) -> str:
    desc_el = soup.select_one('div.vacancy-description__text')
    if not desc_el:
        desc_el = soup.select_one('div.style-ugc')
    if desc_el:
        return desc_el.decode_contents().strip()
    return ''


def _parse_html_detail(soup: BeautifulSoup) -> dict[str, Any]:
    result: dict[str, Any] = {}

    title = _parse_title(soup)
    if title:
        result['title'] = title

    description = _parse_description(soup)
    if description:
        result['description'] = description

    s_min, s_max = _parse_salary_html(soup)
    if s_min is not None:
        result['salary_min'] = s_min
    if s_max is not None:
        result['salary_max'] = s_max

    meta = _parse_meta_chips(soup)
    result.update(meta)

    skills = _parse_skills(soup)
    if skills:
        result['skills'] = skills

    return result


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


@register_parser(SourceTypeEnum.CAREER_HABR_COM)
class HabrCareerParser(BaseParser):
    source_type = SourceTypeEnum.CAREER_HABR_COM

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
        base_url = url.rstrip('/')
        if not base_url.endswith('/vacancies'):
            base_url = f'{base_url}/vacancies'

        job_urls: list[str] = []
        page = 1

        while True:
            page_url = self._build_page_url(base_url, page)
            page_links = self._fetch_page_links(page_url)
            if not page_links:
                break
            job_urls.extend(page_links)

            if not self._has_next_page(page_url):
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
        return self._parse_page(url, soup)

    def _parse_page(
        self,
        url: str,
        soup: BeautifulSoup,
    ) -> ParsedJobData:
        external_id = self._extract_id(url)
        data = ParsedJobData(
            external_id=external_id,
            external_url=url,
        )

        ld_data_dict = _parse_ld_json(soup)
        if ld_data_dict:
            data = _fill_from_ld(data, ld_data_dict)

        html_data = _parse_html_detail(soup)
        data = _fill_from_html(data, html_data)

        data.raw_data = {
            'ld_json': ld_data_dict,
            'html_fields': html_data,
            'source_url': url,
        }
        return data

    @staticmethod
    def _build_page_url(base_url: str, page: int) -> str:
        if page <= 1:
            return base_url
        separator = '&' if '?' in base_url else '?'
        return f'{base_url}{separator}page={page}'

    def _fetch_page_links(self, page_url: str) -> list[str]:
        try:
            resp = self._client.get(page_url)
            resp.raise_for_status()
        except httpx.HTTPError:
            logger.exception('Failed to fetch listing: %s', page_url)
            return []

        soup = BeautifulSoup(resp.text, 'html.parser')
        links = soup.select('a.vacancy-card__title-link')
        result: list[str] = []
        for link in links:
            href = link.get('href', '')
            if isinstance(href, str) and href.startswith('/'):
                href = f'{_BASE_URL}{href}'
            elif not isinstance(href, str):
                continue
            result.append(href)
        return result

    def _has_next_page(self, current_url: str) -> bool:
        try:
            resp = self._client.get(current_url)
            resp.raise_for_status()
        except httpx.HTTPError:
            return False

        soup = BeautifulSoup(resp.text, 'html.parser')
        pagination = soup.select('a[href*="page="]')
        for link in pagination:
            href = str(link.get('href', ''))
            page_match = re.search(r'page=(\d+)', href)
            if not page_match:
                continue
            cur_match = re.search(r'page=(\d+)', current_url)
            cur_page = int(cur_match.group(1)) if cur_match else 1
            next_page = int(page_match.group(1))
            if next_page > cur_page:
                return True
        return False

    @staticmethod
    def _extract_id(url: str) -> str:
        match = re.search(r'/vacancies/(\d+)', url)
        return match.group(1) if match else url.rstrip('/').split('/')[-1]
