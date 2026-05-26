import os
import re
from functools import lru_cache
from typing import Any

from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from database import engine

load_dotenv(override=True)

DANAWA_RAG_LIMIT = int(os.getenv("DANAWA_RAG_LIMIT", "10"))
DANAWA_EMBEDDING_MODEL = os.getenv("DANAWA_EMBEDDING_MODEL", "models/gemini-embedding-001")
DANAWA_EMBEDDING_DIM = int(os.getenv("DANAWA_EMBEDDING_DIM", "768"))
DANAWA_PRODUCT_URL_TEMPLATE = "https://prod.danawa.com/info/?pcode={product_id}"

# ── PATCH 추가 1: spec_filters 14키 화이트리스트 ──────────────────────────
# map_language_to_specs(agent.py)가 내보내는 키와 정확히 일치해야 하며,
# 이 목록 밖의 키는 SQL params로 흘러가면 안 되므로 병합 시 걸러낸다.
ALLOWED_SPEC_KEYS = {
    "connection_type", "is_gaming", "max_weight_g", "right_hand_only",
    "left_hand_ok", "min_dpi", "min_polling_rate_hz", "min_battery_hours",
    "is_silent", "has_rgb", "has_multi_pairing", "min_button_count",
    "grip_query", "color_query",
}
# ──────────────────────────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def _has_product_table() -> bool:
    try:
        with engine.connect() as connection:
            exists = connection.execute(
                text("select to_regclass('public.danawa_products')")
            ).scalar()
            if not exists:
                return False
            count = connection.execute(text("select count(*) from danawa_products")).scalar()
    except SQLAlchemyError:
        return False
    return bool(count)


@lru_cache(maxsize=1)
def _has_indexed_embeddings() -> bool:
    try:
        with engine.connect() as connection:
            count = connection.execute(
                text("select count(*) from danawa_chunks where embedding is not null")
            ).scalar()
    except SQLAlchemyError:
        return False
    return bool(count)


@lru_cache(maxsize=1)
def _get_embeddings() -> GoogleGenerativeAIEmbeddings | None:
    api_key = os.getenv("GOOGLE_API_KEY", "")
    if not api_key or api_key == "your_google_api_key":
        return None

    return GoogleGenerativeAIEmbeddings(
        model=DANAWA_EMBEDDING_MODEL,
        output_dimensionality=DANAWA_EMBEDDING_DIM,
    )


def _to_vector_literal(values: list[float]) -> str:
    return "[" + ",".join(f"{value:.8f}" for value in values) + "]"


def _embed_query(query: str) -> str | None:
    if not _has_indexed_embeddings():
        return None

    embeddings = _get_embeddings()
    if embeddings is None:
        return None

    try:
        return _to_vector_literal(embeddings.embed_query(query))
    except Exception as exc:
        print(f"Danawa RAG embedding fallback: {exc}")
        return None


def _build_reason(row: dict[str, Any]) -> str:
    reasons = []
    if row.get("brand"):
        reasons.append(str(row["brand"]))
    if row.get("connection_type"):
        reasons.append(str(row["connection_type"]))
    if row.get("connectivity") and row.get("connectivity") != row.get("connection_type"):
        reasons.append(str(row["connectivity"]))
    sensor_model = str(row.get("sensor_model") or "")
    if sensor_model and not re.search(r"^\d+(\.\d+)?mm$|^AA$", sensor_model, re.IGNORECASE):
        reasons.append(f"센서 {sensor_model}")
    if row.get("max_dpi") is not None:
        reasons.append(f"최대 {row['max_dpi']}DPI")
    if row.get("weight_g") is not None:
        reasons.append(f"{float(row['weight_g']):.1f}g")
    if row.get("polling_rate_hz") is not None:
        reasons.append(f"{row['polling_rate_hz']}Hz")
    if row.get("max_polling_rate") is not None and row.get("max_polling_rate") != row.get("polling_rate_hz"):
        reasons.append(f"{row['max_polling_rate']}Hz")
    if row.get("battery_max_hours") is not None:
        reasons.append(f"배터리 최대 {row['battery_max_hours']}시간")
    if row.get("button_count") is not None:
        reasons.append(f"버튼 {row['button_count']}개")
    if row.get("hand_orientation"):
        reasons.append(str(row["hand_orientation"]))
    if row.get("grip_type"):
        reasons.append(str(row["grip_type"]))
    if row.get("housing_design"):
        reasons.append(str(row["housing_design"]))
    if row.get("color"):
        reasons.append(str(row["color"]))
    if row.get("is_silent") is True:
        reasons.append("저소음")
    if row.get("has_rgb") is True:
        reasons.append("RGB")
    if row.get("has_multi_pairing") is True:
        reasons.append("멀티페어링")
    if row.get("key_pros"):
        reasons.append(str(row["key_pros"]))
    if row.get("avg_rating") is not None:
        reasons.append(f"평점 {float(row['avg_rating']):.2f}")
    if row.get("positive_count") is not None and row.get("total_count") is not None:
        reasons.append(f"긍정 리뷰 {row['positive_count']}/{row['total_count']}")
    elif row.get("total_count") is not None:
        reasons.append(f"리뷰 {row['total_count']}개")
    elif row.get("total_reviews") is not None:
        reasons.append(f"리뷰 {row['total_reviews']}개")
    if row.get("chunk_type"):
        reasons.append(f"{row['chunk_type']} 근거")
    return ", ".join(reasons) or "Danawa DB 검색 결과와 조건이 일치"


def _resolve_product_url(product_id: str, url: str | None) -> str:
    if url:
        return url
    return DANAWA_PRODUCT_URL_TEMPLATE.format(product_id=product_id)


def _rows_to_products(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}

    for row in rows:
        product_id = str(row["product_id"])
        score = float(row.get("score") or 0)
        product = grouped.get(product_id)

        if product is None:
            grouped[product_id] = {
                "product_id": product_id,
                "name": row.get("product_name") or "상품명 미상",
                "brand": row.get("brand") or "",
                "price": row.get("price"),
                "url": _resolve_product_url(product_id, row.get("url")),
                "thumbnail": row.get("thumbnail") or "",
                "reason": _build_reason(row),
                "score": score,
                "_rating": float(row["avg_rating"]) if row.get("avg_rating") is not None else 0,
                "_review_count": int(row.get("total_count") or row.get("total_reviews") or 0),
            }
            continue

        product["score"] = max(float(product["score"]), score)
        if not product["reason"] and row.get("chunk_type"):
            product["reason"] = _build_reason(row)

    products = list(grouped.values())
    products.sort(
        key=lambda product: (
            float(product.get("score") or 0),
            float(product.get("_rating") or 0),
            int(product.get("_review_count") or 0),
        ),
        reverse=True,
    )

    for product in products:
        product.pop("_rating", None)
        product.pop("_review_count", None)

    return products[:limit]


def _resolve_structured_filters(
    query: str,
    constraints: list[str] | None,
    ranking_priorities: list[str] | None,
) -> dict[str, Any]:
    terms = " ".join([query, " ".join(constraints or []), " ".join(ranking_priorities or [])]).lower()

    connection_type = None
    if "무선" in terms:
        connection_type = "무선"
    elif "유선" in terms:
        connection_type = "유선"

    return {
        "connection_type": connection_type,
        "is_gaming": "게이밍" in terms or "게임" in terms or "fps" in terms,
        "max_weight_g": 70 if "가벼" in terms or "초경량" in terms or "fps" in terms else None,
        "right_hand_only": True if "오른손" in terms else None,
        "left_hand_ok": True if "왼손" in terms or "양손" in terms else None,
        "min_dpi": 16000 if "dpi" in terms or "고감도" in terms else None,
        "min_polling_rate_hz": 1000 if "폴링" in terms or "hz" in terms or "fps" in terms else None,
        "min_battery_hours": 80 if "배터리" in terms or "오래" in terms else None,
        "is_silent": True if "무소음" in terms or "저소음" in terms or "조용" in terms else None,
        "has_rgb": True if "rgb" in terms or "조명" in terms or "led" in terms else None,
        "has_multi_pairing": True if "멀티페어링" in terms or "멀티 페어링" in terms else None,
        "min_button_count": 6 if "버튼" in terms or "매크로" in terms else None,
        "grip_query": "팜" if "팜그립" in terms or "팜 그립" in terms else None,
        "color_query": "블랙" if "블랙" in terms or "검정" in terms else ("화이트" if "화이트" in terms or "흰색" in terms else None),
    }


# ── PATCH 추가 2: 룰 필터 위에 도구(spec_filters)를 덮어쓰는 병합 ──────────
def _merge_spec_filters(
    rule_filters: dict[str, Any],
    spec_filters: dict[str, Any] | None,
) -> dict[str, Any]:
    """룰 필터를 베이스로 두고, map_language_to_specs가 만든 spec_filters를
    덮어쓴다. 정책: 합집합 + 충돌 시 spec_filters(도구) 우선.

    - 도구가 None이 아닌 값을 준 키만 덮어쓴다(None은 '의견 없음'으로 간주).
    - 화이트리스트 밖 키는 무시한다(SQL 안전성).
    """
    merged = dict(rule_filters)
    if not spec_filters:
        return merged
    for key, value in spec_filters.items():
        if key not in ALLOWED_SPEC_KEYS:
            continue
        if value is not None:
            merged[key] = value
    return merged
# ──────────────────────────────────────────────────────────────────────────


def _extract_keyword_tokens(*values: str | None) -> list[str]:
    stopwords = {
        "추천",
        "이하",
        "이상",
        "정도",
        "제품",
        "상품",
        "마우스",
        "좋은",
        "best",
    }
    tokens: list[str] = []
    for value in values:
        if not value:
            continue
        for token in re.findall(r"[0-9A-Za-z가-힣]+", value):
            normalized = token.lower()
            if len(normalized) < 2 or normalized in stopwords:
                continue
            if normalized not in tokens:
                tokens.append(normalized)
    return tokens


def search_danawa_products(
    query: str,
    category: str | None = None,
    budget_krw: int | None = None,
    constraints: list[str] | None = None,
    ranking_priorities: list[str] | None = None,
    limit: int = DANAWA_RAG_LIMIT,
    spec_filters: dict[str, Any] | None = None,   # ── PATCH 시그니처 추가 ──
) -> list[dict[str, Any]]:
    vector_literal = _embed_query(query)
    search_terms = " ".join(
        value
        for value in [query, category or "", " ".join(constraints or []), " ".join(ranking_priorities or [])]
        if value
    )
    keyword_tokens = _extract_keyword_tokens(
        query,
        category,
        " ".join(constraints or []),
        " ".join(ranking_priorities or []),
    )
    # ── PATCH: 룰 필터 산출 후 spec_filters 병합 (이 두 줄이 변경의 전부) ──
    rule_filters = _resolve_structured_filters(query, constraints, ranking_priorities)
    filters = _merge_spec_filters(rule_filters, spec_filters)
    # ──────────────────────────────────────────────────────────────────────

    params = {
        "query": search_terms,
        "token_patterns": [f"%{token}%" for token in keyword_tokens] or [f"%{query}%"],
        "embedding": vector_literal,
        "budget_krw": budget_krw,
        "connection_type": filters["connection_type"],
        "is_gaming": filters["is_gaming"],
        "max_weight_g": filters["max_weight_g"],
        "right_hand_only": filters["right_hand_only"],
        "left_hand_ok": filters["left_hand_ok"],
        "min_dpi": filters["min_dpi"],
        "min_polling_rate_hz": filters["min_polling_rate_hz"],
        "min_battery_hours": filters["min_battery_hours"],
        "is_silent": filters["is_silent"],
        "has_rgb": filters["has_rgb"],
        "has_multi_pairing": filters["has_multi_pairing"],
        "min_button_count": filters["min_button_count"],
        "grip_pattern": f"%{filters['grip_query']}%" if filters["grip_query"] else None,
        "color_pattern": f"%{filters['color_query']}%" if filters["color_query"] else None,
        "candidate_limit": max(limit * 8, 40),
    }

    product_statement = text(
        """
        select
            null as chunk_id,
            'product' as chunk_type,
            product_id,
            product_name,
            brand,
            price,
            avg_rating,
            total_reviews as total_count,
            null::integer as positive_count,
            null::integer as negative_count,
            null::numeric as positive_ratio,
            connectivity as connection_type,
            connectivity,
            sensor_model,
            max_dpi as dpi_max,
            max_dpi,
            max_polling_rate as polling_rate_hz,
            max_polling_rate,
            weight_g,
            is_gaming,
            case
                when hand_orientation like '%오른손%' then true
                else null
            end as is_right_hand_only,
            hand_orientation,
            battery_max_hours,
            button_count,
            is_silent,
            has_rgb,
            has_multi_pairing,
            grip_type,
            housing_design,
            key_pros,
            key_cons,
            color,
            url,
            thumbnail,
            (
                ts_rank_cd(search_vector, plainto_tsquery('simple', :query))
                + (
                    select count(*)::float
                    from unnest(cast(:token_patterns as text[])) as token(pattern)
                    where product_name ilike token.pattern
                       or brand ilike token.pattern
                       or coalesce(sensor_model, '') ilike token.pattern
                       or coalesce(connectivity, '') ilike token.pattern
                       or coalesce(key_pros, '') ilike token.pattern
                       or coalesce(key_cons, '') ilike token.pattern
                       or coalesce(reviews, '') ilike token.pattern
                       or coalesce(grip_type, '') ilike token.pattern
                       or coalesce(housing_design, '') ilike token.pattern
                )
                + coalesce(avg_rating, 0) / 5.0
                + least(coalesce(total_reviews, 0), 100)::float / 100.0
            ) as score
        from danawa_products
        where (
              search_vector @@ plainto_tsquery('simple', :query)
              or exists (
                  select 1
                  from unnest(cast(:token_patterns as text[])) as token(pattern)
                  where product_name ilike token.pattern
                     or brand ilike token.pattern
                     or coalesce(sensor_model, '') ilike token.pattern
                     or coalesce(connectivity, '') ilike token.pattern
                     or coalesce(key_pros, '') ilike token.pattern
                     or coalesce(key_cons, '') ilike token.pattern
                     or coalesce(reviews, '') ilike token.pattern
                     or coalesce(grip_type, '') ilike token.pattern
                     or coalesce(housing_design, '') ilike token.pattern
              )
        )
          and (:budget_krw is null or price is null or price <= :budget_krw)
          and (
              :connection_type is null
              or connectivity ilike '%' || :connection_type || '%'
              or (:connection_type = '무선' and connectivity ilike '%블루투스%')
          )
          and (:is_gaming = false or is_gaming = true)
          and (:max_weight_g is null or weight_g <= :max_weight_g)
          and (:right_hand_only is null or hand_orientation is null or hand_orientation like '%오른손%' or hand_orientation like '%양손%')
          and (:left_hand_ok is null or hand_orientation is null or hand_orientation like '%왼손%' or hand_orientation like '%양손%')
          and (:min_dpi is null or max_dpi >= :min_dpi)
          and (:min_polling_rate_hz is null or max_polling_rate >= :min_polling_rate_hz)
          and (:min_battery_hours is null or battery_max_hours >= :min_battery_hours)
          and (:is_silent is null or is_silent = :is_silent)
          and (:has_rgb is null or has_rgb = :has_rgb)
          and (:has_multi_pairing is null or has_multi_pairing = :has_multi_pairing)
          and (:min_button_count is null or button_count >= :min_button_count)
          and (:grip_pattern is null or grip_type ilike :grip_pattern)
          and (:color_pattern is null or color ilike :color_pattern or product_name ilike :color_pattern)
        order by score desc, price asc nulls last
        limit :candidate_limit
        """
    )

    keyword_statement = text(
        """
        select
            chunk_id,
            chunk_type,
            product_id,
            product_name,
            brand,
            price,
            avg_rating,
            total_count,
            positive_count,
            negative_count,
            positive_ratio,
            connection_type,
            sensor_model,
            dpi_max,
            polling_rate_hz,
            weight_g,
            is_gaming,
            is_right_hand_only,
            length_mm,
            url,
            thumbnail,
            (
                ts_rank_cd(search_vector, plainto_tsquery('simple', :query))
                + (
                    select count(*)::float
                    from unnest(cast(:token_patterns as text[])) as token(pattern)
                    where chunk_text ilike token.pattern
                       or product_name ilike token.pattern
                       or brand ilike token.pattern
                )
            ) as score
        from danawa_chunks
        where (
              search_vector @@ plainto_tsquery('simple', :query)
              or exists (
                  select 1
                  from unnest(cast(:token_patterns as text[])) as token(pattern)
                  where chunk_text ilike token.pattern
                     or product_name ilike token.pattern
                     or brand ilike token.pattern
              )
        )
          and (:budget_krw is null or price is null or price <= :budget_krw)
          and (
              :connection_type is null
              or connection_type = :connection_type
              or (:connection_type in ('유선', '무선') and connection_type = '유선+무선')
          )
          and (:is_gaming = false or is_gaming = true)
          and (:max_weight_g is null or weight_g is null or weight_g <= :max_weight_g)
          and (:right_hand_only is null or is_right_hand_only = :right_hand_only)
          and (:min_dpi is null or dpi_max is null or dpi_max >= :min_dpi)
          and (:min_polling_rate_hz is null or polling_rate_hz is null or polling_rate_hz >= :min_polling_rate_hz)
        order by score desc
        limit :candidate_limit
        """
    )

    vector_statement = None
    if vector_literal:
        vector_statement = text(
            """
            select
                chunk_id,
                chunk_type,
                product_id,
                product_name,
                brand,
                price,
                avg_rating,
                total_count,
                positive_count,
                negative_count,
                positive_ratio,
                connection_type,
                sensor_model,
                dpi_max,
                polling_rate_hz,
                weight_g,
                is_gaming,
                is_right_hand_only,
                length_mm,
                url,
                thumbnail,
                (
                    (1 - (embedding <=> cast(:embedding as extensions.vector))) * 0.75
                    + ts_rank_cd(search_vector, plainto_tsquery('simple', :query)) * 0.25
                ) as score
            from danawa_chunks
            where embedding is not null
              and (:budget_krw is null or price is null or price <= :budget_krw)
              and (
                  :connection_type is null
                  or connection_type = :connection_type
                  or (:connection_type in ('유선', '무선') and connection_type = '유선+무선')
              )
              and (:is_gaming = false or is_gaming = true)
              and (:max_weight_g is null or weight_g is null or weight_g <= :max_weight_g)
              and (:right_hand_only is null or is_right_hand_only = :right_hand_only)
              and (:min_dpi is null or dpi_max is null or dpi_max >= :min_dpi)
              and (:min_polling_rate_hz is null or polling_rate_hz is null or polling_rate_hz >= :min_polling_rate_hz)
            order by embedding <=> cast(:embedding as extensions.vector)
            limit :candidate_limit
            """
        )

    try:
        with engine.connect() as connection:
            rows = []
            if _has_product_table():
                rows = [dict(row._mapping) for row in connection.execute(product_statement, params)]
            if vector_statement is not None and len(rows) < limit:
                rows.extend(dict(row._mapping) for row in connection.execute(vector_statement, params))
            if not rows:
                rows = [dict(row._mapping) for row in connection.execute(keyword_statement, params)]
    except SQLAlchemyError as exc:
        print(f"Danawa RAG query unavailable: {exc}")
        return []

    return _rows_to_products(rows, limit)