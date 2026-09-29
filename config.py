"""Конфигурация SEO On-Page анализатора конкурентов."""

from __future__ import annotations

# Домены каталогов, справочников и поисковых поверхностей,
# которые не считаются прямыми конкурентами в выдаче.
AGGREGATOR_DOMAINS: list[str] = [
    "103.by",
    "spravker.by",
    "barb.by",
    "relaxed.by",
    "zoon.ru",
    "yandex.*",
    "zoon.by",
    "yandex.ru",
    "yandex.by",
    "yandex.com",
    "yandex.kz",
    "yandex.eu",
    "ya.ru",
    "maps.yandex.ru",
    "market.yandex.ru",
    "2gis.ru",
    "2gis.by",
    "2gis.com",
    "google.com",
    "google.by",
    "google.ru",
    "maps.google.com",
    "youtube.com",
    "wikipedia.org",
    "wikidata.org",
    "facebook.com",
    "instagram.com",
    "vk.com",
    "ok.ru",
    "otzovik.com",
    "irecommend.ru",
    "flamp.ru",
    "yell.ru",
    "yell.by",
    "orgpage.ru",
    "orgpage.by",
    "spr.ru",
    "yp.ru",
    "deal.by",
    "shop.by",
    "kufar.by",
    "avito.ru",
    "tiu.ru",
    "pulscen.ru",
    "blizko.ru",
    "bizly.ru",
    "cataloxy.ru",
    "cataloxy.by",
    "flagma.by",
    "flagma.ru",
    "tripadvisor.com",
    "tripadvisor.ru",
    "booking.com",
    "prodoctorov.ru",
    "docdoc.ru",
    "napopravku.ru",
    "sberhealth.ru",
    "gdeslon.ru",
    "otzyvby.com",
    "infobel.com",
    "yellowpages.by",
]

# User-Agent, имитирующий обычный браузер.
DEFAULT_USER_AGENT: str = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0.0.0 Safari/537.36"
)

DEFAULT_TIMEOUT: int = 10
DEFAULT_THREAD_LIMIT: int = 5
SERP_RESULT_LIMIT: int = 10
DEFAULT_LOCATION: str = "Minsk, Belarus"

DEFAULT_REQUEST_HEADERS: dict[str, str] = {
    "User-Agent": DEFAULT_USER_AGENT,
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Cache-Control": "no-cache",
}

DEFAULT_SEO_MARKERS: list[str] = [
    "цена",
    "стоимость",
    "руб",
    "записаться",
    "врач",
    "отзывы",
    "акция",
]

# DOM-элементы, которые исключаются перед подсчётом чистого текста.
STRIP_TAGS: tuple[str, ...] = (
    "script",
    "style",
    "nav",
    "footer",
    "header",
    "form",
    "noscript",
    "svg",
    "iframe",
)
