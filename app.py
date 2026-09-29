"""Streamlit-приложение для On-Page анализа конкурентов по семантическому ядру."""

from __future__ import annotations

import io
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import pandas as pd
import streamlit as st

from aggregator import aggregate_seo_metrics
from config import (
    DEFAULT_LOCATION,
    DEFAULT_SEO_MARKERS,
    DEFAULT_THREAD_LIMIT,
    SERP_RESULT_LIMIT,
)
from parser import parse_onpage_factors
from serp import get_top_competitors

st.set_page_config(
    page_title="SEO On-Page: анализ конкурентов",
    page_icon="🔎",
    layout="wide",
)


@st.cache_data(ttl=60 * 60 * 12, show_spinner=False)
def cached_top_competitors(
    query: str,
    api_key: str,
    location: str,
    num_results: int,
) -> list[str]:
    """Кэширует ответ SerpApi, чтобы повторный запуск не тратил лимит."""
    return get_top_competitors(
        query=query,
        api_key=api_key,
        location=location,
        num_results=num_results,
    )


@st.cache_data(ttl=60 * 60 * 12, show_spinner=False)
def cached_parse_onpage(url: str, markers: tuple[str, ...]) -> dict[str, Any]:
    """Кэширует On-Page разбор URL для заданного набора маркеров."""
    return parse_onpage_factors(url, markers=list(markers))


def parse_markers(raw: str) -> list[str]:
    """Разбирает строку маркеров, введённых через запятую."""
    parts = [item.strip() for item in raw.split(",")]
    unique: list[str] = []
    seen: set[str] = set()
    for item in parts:
        key = item.casefold()
        if item and key not in seen:
            unique.append(item)
            seen.add(key)
    return unique or list(DEFAULT_SEO_MARKERS)


def load_queries(uploaded: Any) -> pd.DataFrame:
    """Читает Excel и нормализует колонку с запросами."""
    frame = pd.read_excel(uploaded, engine="openpyxl")
    rename_map = {col: str(col).strip() for col in frame.columns}
    frame = frame.rename(columns=rename_map)

    query_col = None
    for candidate in ("Запрос", "запрос", "Query", "query", "Ключ", "keyword"):
        if candidate in frame.columns:
            query_col = candidate
            break
    if query_col is None:
        raise ValueError(
            'В файле нет колонки «Запрос». Добавьте столбец с поисковыми фразами.'
        )

    queries = (
        frame[[query_col]]
        .rename(columns={query_col: "Запрос"})
        .dropna()
    )
    queries["Запрос"] = queries["Запрос"].astype(str).str.strip()
    queries = queries[queries["Запрос"] != ""]
    queries = queries.drop_duplicates(subset=["Запрос"]).reset_index(drop=True)
    return queries


def run_analysis(
    queries: list[str],
    api_key: str,
    location: str,
    markers: list[str],
    thread_limit: int,
) -> dict[str, Any]:
    """Последовательно обходит запросы и параллельно парсит URL конкурентов."""
    markers_tuple = tuple(markers)
    parsed: list[dict[str, Any]] = []
    errors: list[str] = []

    total_steps = max(len(queries) * SERP_RESULT_LIMIT, 1)
    progress = st.progress(0, text="Запуск анализа…")
    status = st.empty()
    done_steps = 0

    for index, query in enumerate(queries, start=1):
        status.markdown(f"**Запрос {index}/{len(queries)}:** `{query}` — получаем ТОП выдачи")
        try:
            urls = cached_top_competitors(
                query=query,
                api_key=api_key,
                location=location,
                num_results=SERP_RESULT_LIMIT,
            )
        except ValueError as exc:
            errors.append(f"{query}: {exc}")
            done_steps += SERP_RESULT_LIMIT
            progress.progress(
                min(done_steps / total_steps, 1.0),
                text=f"SerpApi ошибка: {query}",
            )
            continue

        if not urls:
            errors.append(f"{query}: после фильтра агрегаторов URL не осталось")
            done_steps += SERP_RESULT_LIMIT
            progress.progress(min(done_steps / total_steps, 1.0), text=f"Пустая выдача: {query}")
            continue

        status.markdown(
            f"**Запрос {index}/{len(queries)}:** `{query}` — парсинг {len(urls)} URL"
        )
        with ThreadPoolExecutor(max_workers=thread_limit) as pool:
            future_map = {
                pool.submit(cached_parse_onpage, url, markers_tuple): (rank, url)
                for rank, url in enumerate(urls, start=1)
            }
            for future in as_completed(future_map):
                rank, url = future_map[future]
                try:
                    page = future.result()
                except Exception as exc:  # noqa: BLE001
                    page = {
                        "url": url,
                        "error": True,
                        "error_message": str(exc),
                        "title": "",
                        "title_length": 0,
                        "h1": "",
                        "h2": [],
                        "text_length": 0,
                        "word_count": 0,
                        "markers_in_text": {marker: False for marker in markers},
                        "markers_in_title": {marker: False for marker in markers},
                    }
                page = dict(page)
                page["query"] = query
                page["rank"] = rank
                parsed.append(page)
                done_steps += 1
                progress.progress(
                    min(done_steps / total_steps, 1.0),
                    text=f"{query}: позиция {rank} — {url}",
                )

        remaining = SERP_RESULT_LIMIT - len(urls)
        if remaining > 0:
            done_steps += remaining
            progress.progress(min(done_steps / total_steps, 1.0), text=f"Готово: {query}")

    progress.progress(1.0, text="Анализ завершён")
    status.empty()
    return aggregate_seo_metrics(parsed, markers=markers) | {"errors": errors, "parsed": parsed}


def to_excel_bytes(summary: pd.DataFrame, details: pd.DataFrame) -> bytes:
    """Собирает xlsx-отчёт с вкладками «Сводка» и «Детальные данные»."""
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="Сводка", index=False)
        details.to_excel(writer, sheet_name="Детальные данные", index=False)
    return buffer.getvalue()


def render_sidebar() -> tuple[str, str, list[str], int]:
    """Рисует боковую панель с ключом API, регионом и маркерами."""
    with st.sidebar:
        st.header("Настройки")
        api_key = st.text_input(
            "API-ключ SerpApi",
            type="password",
            help="Ключ с https://serpapi.com. Кэшируется на 12 часов.",
        )
        location = st.text_input("Регион выдачи Google", value=DEFAULT_LOCATION)
        markers_raw = st.text_area(
            "Коммерческие маркеры (через запятую)",
            value=", ".join(DEFAULT_SEO_MARKERS),
            height=120,
        )
        thread_limit = st.slider(
            "Потоков парсинга",
            min_value=1,
            max_value=10,
            value=DEFAULT_THREAD_LIMIT,
        )

    return api_key, location, parse_markers(markers_raw), thread_limit


def main() -> None:
    """Точка входа Streamlit UI."""
    st.title("On-Page анализ конкурентов по семантическому ядру")
    st.write(
        "Загрузите Excel с колонкой **Запрос**, получите ТОП-10 Google через SerpApi, "
        "снимите Title / H1 / объём текста и коммерческие маркеры, затем выгрузите отчёт."
    )

    api_key, location, markers, thread_limit = render_sidebar()
    uploaded = st.file_uploader("Семантическое ядро (.xlsx)", type=["xlsx"])

    if uploaded is None:
        st.info("Ожидается Excel-файл с колонкой «Запрос».")
        return

    try:
        queries_df = load_queries(uploaded)
    except Exception as exc:  # noqa: BLE001
        st.error(str(exc))
        return

    st.subheader("Предпросмотр ядра")
    st.dataframe(queries_df, use_container_width=True, hide_index=True)
    st.caption(f"Уникальных запросов: {len(queries_df)}")

    run_clicked = st.button("Запустить анализ", type="primary", use_container_width=False)

    if run_clicked:
        if not api_key.strip():
            st.error("Укажите API-ключ SerpApi в боковой панели.")
            return
        if queries_df.empty:
            st.error("Список запросов пуст.")
            return

        with st.spinner("Идёт сбор выдачи и парсинг страниц…"):
            result = run_analysis(
                queries=queries_df["Запрос"].tolist(),
                api_key=api_key,
                location=location,
                markers=markers,
                thread_limit=thread_limit,
            )
        st.session_state["seo_result"] = result

    result = st.session_state.get("seo_result")
    if not result:
        return

    for message in result.get("errors") or []:
        st.warning(message)

    summary: pd.DataFrame = result["summary"]
    details: pd.DataFrame = result["details"]

    st.subheader("Сводная статистика по запросам")
    if summary.empty:
        st.warning("Нет данных для сводки. Проверьте ключ API и состав ядра.")
    else:
        st.dataframe(summary, use_container_width=True, hide_index=True)

    st.subheader("Детальные данные по URL конкурентов")
    if details.empty:
        st.warning("Не удалось распарсить ни одной страницы конкурентов.")
    else:
        st.dataframe(details, use_container_width=True, hide_index=True)

    if not summary.empty or not details.empty:
        st.download_button(
            label="Скачать отчёт .xlsx",
            data=to_excel_bytes(summary, details),
            file_name="seo_onpage_report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


main()
