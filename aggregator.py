"""Агрегация On-Page метрик конкурентов в статистику по запросам."""

from __future__ import annotations

import re
from statistics import mean, median
from typing import Any

import pandas as pd

_WORD_RE = re.compile(r"\s+")


def h1_matches_query(h1: str, query: str) -> bool:
    """Проверяет, совпадает ли H1 с запросом или содержит его ключи.

    Сравнение регистронезависимое. Считается совпадением, если:
    - нормализованный запрос целиком входит в H1 (или наоборот);
    - все значимые слова запроса (длиннее 2 символов) входят в H1.

    Args:
        h1: Текст первого заголовка H1.
        query: Поисковый запрос.

    Returns:
        ``True``, если H1 релевантен запросу.
    """
    if not h1 or not query:
        return False
    h1_n = h1.casefold().strip()
    query_n = query.casefold().strip()
    if not h1_n or not query_n:
        return False
    if query_n in h1_n or h1_n in query_n:
        return True
    words = [token for token in _WORD_RE.split(query_n) if len(token) > 2]
    if not words:
        return query_n in h1_n
    return all(word in h1_n for word in words)


def _successful(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Отбирает успешно распарсенные страницы, отсортированные по позиции."""
    ok = [row for row in rows if not row.get("error")]
    return sorted(ok, key=lambda item: int(item.get("rank") or 0))


def _top_n(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    """Возвращает срез успешно разобранных URL до позиции ``limit``."""
    return [row for row in _successful(rows) if int(row.get("rank") or 0) <= limit]


def _safe_mean(values: list[float]) -> float | None:
    return round(float(mean(values)), 1) if values else None


def _safe_median(values: list[float]) -> float | None:
    return round(float(median(values)), 1) if values else None


def _pct(flag_count: int, total: int) -> float | None:
    if total <= 0:
        return None
    return round(100.0 * flag_count / total, 1)


def _text_stats(rows: list[dict[str, Any]]) -> dict[str, float | None]:
    lengths = [float(row.get("text_length") or 0) for row in rows]
    words = [float(row.get("word_count") or 0) for row in rows]
    return {
        "text_length_mean": _safe_mean(lengths),
        "text_length_median": _safe_median(lengths),
        "word_count_mean": _safe_mean(words),
        "word_count_median": _safe_median(words),
    }


def aggregate_seo_metrics(
    parsed_data: list[dict[str, Any]],
    markers: list[str] | None = None,
) -> dict[str, Any]:
    """Считает медианы, средние и доли маркеров по ТОП-3/5/10.

    Группирует результаты парсинга по полю ``query``. Для каждой группы:
    - медиана и среднее длины текста и числа слов (ТОП-3, ТОП-5, ТОП-10);
    - доля конкурентов с каждым маркером в Title (ТОП-5 и ТОП-10);
    - доля страниц, у которых H1 совпадает с запросом или содержит ключи.

    Args:
        parsed_data: Список словарей On-Page факторов (включая ``query`` и ``rank``).
        markers: Маркеры для колонок сводки. Если не заданы, берутся из данных.

    Returns:
        Словарь с ключами ``summary`` (DataFrame), ``details`` (DataFrame)
        и ``stats`` (список словарей статистики по запросам).
    """
    if markers is None:
        markers = []
        if parsed_data:
            sample = parsed_data[0].get("markers_in_title") or {}
            markers = list(sample.keys())

    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in parsed_data:
        query = str(row.get("query") or "")
        grouped.setdefault(query, []).append(row)

    stats_rows: list[dict[str, Any]] = []
    for query, rows in grouped.items():
        top3 = _top_n(rows, 3)
        top5 = _top_n(rows, 5)
        top10 = _top_n(rows, 10)
        t3, t5, t10 = _text_stats(top3), _text_stats(top5), _text_stats(top10)

        record: dict[str, Any] = {
            "Запрос": query,
            "URL в анализе": len(rows),
            "Успешно ТОП-10": len(top10),
            "Текст среднее ТОП-3": t3["text_length_mean"],
            "Текст медиана ТОП-3": t3["text_length_median"],
            "Текст среднее ТОП-5": t5["text_length_mean"],
            "Текст медиана ТОП-5": t5["text_length_median"],
            "Текст среднее ТОП-10": t10["text_length_mean"],
            "Текст медиана ТОП-10": t10["text_length_median"],
            "Слова среднее ТОП-3": t3["word_count_mean"],
            "Слова среднее ТОП-5": t5["word_count_mean"],
            "Слова среднее ТОП-10": t10["word_count_mean"],
            "H1 содержит ключ ТОП-5, %": _pct(
                sum(1 for row in top5 if h1_matches_query(str(row.get("h1") or ""), query)),
                len(top5),
            ),
            "H1 содержит ключ ТОП-10, %": _pct(
                sum(1 for row in top10 if h1_matches_query(str(row.get("h1") or ""), query)),
                len(top10),
            ),
        }

        for marker in markers:
            title_top5 = sum(
                1 for row in top5 if (row.get("markers_in_title") or {}).get(marker)
            )
            title_top10 = sum(
                1 for row in top10 if (row.get("markers_in_title") or {}).get(marker)
            )
            text_top10 = sum(
                1 for row in top10 if (row.get("markers_in_text") or {}).get(marker)
            )
            record[f'Title «{marker}» ТОП-5, %'] = _pct(title_top5, len(top5))
            record[f'Title «{marker}» ТОП-10, %'] = _pct(title_top10, len(top10))
            record[f'Текст «{marker}» ТОП-10, %'] = _pct(text_top10, len(top10))

        stats_rows.append(record)

    details_rows: list[dict[str, Any]] = []
    for row in parsed_data:
        query = str(row.get("query") or "")
        detail: dict[str, Any] = {
            "Запрос": query,
            "Позиция": row.get("rank"),
            "URL": row.get("url"),
            "Ошибка": bool(row.get("error")),
            "Описание ошибки": row.get("error_message") or "",
            "Title": row.get("title") or "",
            "Длина Title": row.get("title_length") or 0,
            "H1": row.get("h1") or "",
            "H1 содержит ключ": h1_matches_query(str(row.get("h1") or ""), query),
            "H2": "; ".join(row.get("h2") or []),
            "Длина текста": row.get("text_length") or 0,
            "Слов": row.get("word_count") or 0,
        }
        title_flags = row.get("markers_in_title") or {}
        text_flags = row.get("markers_in_text") or {}
        for marker in markers:
            detail[f"Title: {marker}"] = bool(title_flags.get(marker))
            detail[f"Текст: {marker}"] = bool(text_flags.get(marker))
        details_rows.append(detail)

    summary_df = pd.DataFrame(stats_rows)
    details_df = pd.DataFrame(details_rows)
    if not details_df.empty:
        details_df = details_df.sort_values(
            by=["Запрос", "Позиция"],
            kind="mergesort",
        ).reset_index(drop=True)

    return {
        "summary": summary_df,
        "details": details_df,
        "stats": stats_rows,
    }
