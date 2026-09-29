"""On-Page парсинг HTML-страниц конкурентов."""

from __future__ import annotations

import logging
import re
from typing import Any

import requests
import urllib3
from bs4 import BeautifulSoup, Tag
from requests.exceptions import RequestException, Timeout

from config import (
    DEFAULT_REQUEST_HEADERS,
    DEFAULT_SEO_MARKERS,
    DEFAULT_TIMEOUT,
    STRIP_TAGS,
)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

_WHITESPACE_RE = re.compile(r"\s+")


def fetch_page(url: str, timeout: int = DEFAULT_TIMEOUT) -> str:
    """Выполняет HTTP GET с заголовками браузера.

    SSL-сертификаты не проверяются (``verify=False``), чтобы не терять
    сайты с некорректной цепочкой сертификатов. Таймауты и сетевые
    ошибки пробрасываются вызывающему коду.

    Args:
        url: Абсолютный URL страницы.
        timeout: Таймаут запроса в секундах.

    Returns:
        Тело ответа в виде Unicode-строки.

    Raises:
        requests.exceptions.RequestException: Сетевая или HTTP-ошибка.
    """
    response = requests.get(
        url,
        headers=DEFAULT_REQUEST_HEADERS,
        timeout=timeout,
        verify=False,
        allow_redirects=True,
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    return response.text


def _extract_text(element: Tag | None) -> str:
    """Возвращает нормализованный видимый текст узла."""
    if element is None:
        return ""
    raw = element.get_text(separator=" ", strip=True)
    return _WHITESPACE_RE.sub(" ", raw).strip()


def _empty_result(
    url: str,
    markers: list[str],
    error_message: str,
) -> dict[str, Any]:
    """Собирает словарь-заглушку при ошибке парсинга."""
    return {
        "url": url,
        "error": True,
        "error_message": error_message,
        "title": "",
        "title_length": 0,
        "h1": "",
        "h2": [],
        "text_length": 0,
        "word_count": 0,
        "markers_in_text": {marker: False for marker in markers},
        "markers_in_title": {marker: False for marker in markers},
    }


def _marker_presence(haystack: str, markers: list[str]) -> dict[str, bool]:
    """Проверяет вхождение каждого маркера без учёта регистра."""
    normalized = haystack.casefold()
    return {marker: marker.casefold() in normalized for marker in markers}


def parse_onpage_factors(
    url: str,
    markers: list[str] | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """Извлекает On-Page факторы со страницы ``url``.

    Собирает Title, первый H1, все H2, объём очищенного текста и
    булевы флаги коммерческих маркеров в Title и в теле страницы.
    При 4xx/5xx, таймауте или любой ``RequestException`` возвращает
    словарь с ``error=True`` и не прерывает пакетный анализ.

    Args:
        url: Абсолютный URL страницы.
        markers: Список коммерческих маркеров. По умолчанию из ``config``.
        timeout: Таймаут HTTP-запроса.

    Returns:
        Словарь с полями Title/H1/H2, объёмом текста и маркерами.
    """
    used_markers = markers if markers is not None else list(DEFAULT_SEO_MARKERS)

    try:
        html = fetch_page(url, timeout=timeout)
    except Timeout:
        logger.warning("Timeout при запросе %s", url)
        return _empty_result(url, used_markers, "Timeout: превышено время ожидания ответа")
    except RequestException as exc:
        status = ""
        response = getattr(exc, "response", None)
        if response is not None and getattr(response, "status_code", None):
            status = f"HTTP {response.status_code}: "
        logger.warning("Ошибка запроса %s: %s", url, exc)
        return _empty_result(url, used_markers, f"{status}{exc}".strip())

    try:
        soup = BeautifulSoup(html, "lxml")

        title_text = _extract_text(soup.title) if soup.title else ""
        first_h1 = soup.find("h1")
        h1_text = _extract_text(first_h1)
        h2_list = [_extract_text(node) for node in soup.find_all("h2")]
        h2_list = [item for item in h2_list if item]

        for tag_name in STRIP_TAGS:
            for node in soup.find_all(tag_name):
                node.decompose()

        body = soup.body or soup
        clean_text = _extract_text(body)
        words = [token for token in clean_text.split(" ") if token]

        return {
            "url": url,
            "error": False,
            "error_message": "",
            "title": title_text,
            "title_length": len(title_text),
            "h1": h1_text,
            "h2": h2_list,
            "text_length": len(clean_text),
            "word_count": len(words),
            "markers_in_text": _marker_presence(clean_text, used_markers),
            "markers_in_title": _marker_presence(title_text, used_markers),
        }
    except Exception as exc:  # noqa: BLE001 — страница не должна ронять пайплайн
        logger.exception("Ошибка разбора HTML %s", url)
        return _empty_result(url, used_markers, f"Parse error: {exc}")
