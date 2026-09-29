"""Получение ТОП органической выдачи Google через SerpApi."""

from __future__ import annotations

import logging
from urllib.parse import urlparse

from serpapi import GoogleSearch

from config import AGGREGATOR_DOMAINS, DEFAULT_LOCATION, SERP_RESULT_LIMIT

logger = logging.getLogger(__name__)


def _normalize_host(url: str) -> str:
    """Возвращает hostname без ``www.`` в нижнем регистре."""
    host = urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def is_aggregator_url(url: str, blacklist: list[str] | None = None) -> bool:
    """Проверяет, принадлежит ли URL домену-агрегатору.

    Поддерживаются точные домены и маски вида ``yandex.*``: маска
    срабатывает, если hostname равен префиксу или является его поддоменом,
    либо совпадает с ``префикс.<зона>``.

    Args:
        url: Абсолютный URL из органической выдачи.
        blacklist: Список доменов. По умолчанию ``AGGREGATOR_DOMAINS``.

    Returns:
        ``True``, если URL нужно исключить из анализа конкурентов.
    """
    host = _normalize_host(url)
    if not host:
        return True

    domains = blacklist if blacklist is not None else AGGREGATOR_DOMAINS
    for raw in domains:
        domain = raw.lower().strip()
        if not domain:
            continue
        if domain.endswith(".*"):
            prefix = domain[:-2]
            if host == prefix or host.startswith(prefix + "."):
                return True
            continue
        if host == domain or host.endswith("." + domain):
            return True
    return False


def get_top_competitors(
    query: str,
    api_key: str,
    location: str = DEFAULT_LOCATION,
    num_results: int = SERP_RESULT_LIMIT,
) -> list[str]:
    """Возвращает URL прямых конкурентов из органической выдачи Google.

    Запрашивает SerpApi (engine=google), разбирает ``organic_results``
    и отбрасывает домены из блек-листа агрегаторов. Чтобы после фильтра
    набрать нужный объём, у SerpApi запрашивается расширенный ``num``.

    Args:
        query: Поисковый запрос из семантического ядра.
        api_key: Ключ SerpApi.
        location: География выдачи (формат SerpApi).
        num_results: Максимум URL прямых конкурентов (обычно 10).

    Returns:
        Список абсолютных URL длиной не более ``num_results``.

    Raises:
        ValueError: Если ключ API пустой или SerpApi вернул ошибку.
    """
    if not api_key or not api_key.strip():
        raise ValueError("Не указан API-ключ SerpApi.")

    fetch_count = min(max(num_results * 2, num_results), 20)
    params: dict[str, str | int] = {
        "engine": "google",
        "q": query,
        "location": location,
        "hl": "ru",
        "gl": "by",
        "google_domain": "google.by",
        "num": fetch_count,
        "api_key": api_key.strip(),
    }

    search = GoogleSearch(params)
    payload = search.get_dict()

    api_error = payload.get("error")
    if api_error:
        raise ValueError(f"SerpApi: {api_error}")

    organic = payload.get("organic_results") or []
    competitors: list[str] = []
    seen_hosts: set[str] = set()

    for item in organic:
        url = (item.get("link") or "").strip()
        if not url:
            continue
        if is_aggregator_url(url):
            logger.debug("Пропущен агрегатор: %s", url)
            continue
        host = _normalize_host(url)
        if host in seen_hosts:
            continue
        seen_hosts.add(host)
        competitors.append(url)
        if len(competitors) >= num_results:
            break

    return competitors
