import argparse
import csv
import os
import sys
from pathlib import Path
from typing import Any

import psycopg2
from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from psycopg2.extras import execute_values

load_dotenv(override=True)

DANAWA_EMBEDDING_MODEL = os.getenv("DANAWA_EMBEDDING_MODEL", "models/gemini-embedding-001")
DANAWA_EMBEDDING_DIM = int(os.getenv("DANAWA_EMBEDDING_DIM", "768"))
DANAWA_PRODUCT_URL_TEMPLATE = "https://prod.danawa.com/info/?pcode={product_id}"


def _clean_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    return int(float(value))


def _clean_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _clean_bool(value: str | None) -> bool | None:
    if value is None or value == "":
        return None
    return value.strip().lower() in {"1", "true", "t", "yes", "y", "○"}


def _vector_literal(values: list[float] | None) -> str | None:
    if values is None:
        return None
    return "[" + ",".join(f"{value:.8f}" for value in values) + "]"


def _resolve_product_url(product_id: str, url: str | None) -> str:
    if url:
        return url
    return DANAWA_PRODUCT_URL_TEMPLATE.format(product_id=product_id)


def _read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        rows = []
        for index, row in enumerate(reader, start=1):
            rows.append(
                {
                    "chunk_id": _clean_int(row.get("chunk_id")) or index,
                    "chunk_type": row["chunk_type"],
                    "product_id": str(row["product_id"]),
                    "product_name": row.get("product_name"),
                    "brand": row.get("brand"),
                    "price": _clean_int(row.get("price")),
                    "tier": row.get("tier"),
                    "avg_rating": _clean_float(row.get("avg_rating")),
                    "total_count": _clean_int(row.get("total_count")),
                    "positive_count": _clean_int(row.get("positive_count")),
                    "negative_count": _clean_int(row.get("negative_count")),
                    "positive_ratio": _clean_float(row.get("positive_ratio")),
                    "connection_type": row.get("connection_type") or None,
                    "sensor_model": row.get("sensor_model") or None,
                    "dpi_max": _clean_int(row.get("dpi_max")),
                    "polling_rate_hz": _clean_int(row.get("polling_rate_hz")),
                    "weight_g": _clean_float(row.get("weight_g")),
                    "is_gaming": _clean_bool(row.get("is_gaming")) or False,
                    "is_right_hand_only": _clean_bool(row.get("is_right_hand_only")),
                    "length_mm": _clean_float(row.get("length_mm")),
                    "url": _resolve_product_url(str(row["product_id"]), row.get("url")),
                    "thumbnail": row.get("thumbnail") or None,
                    "chunk_text": row["chunk_text"],
                }
            )
    return rows


def _embed_rows(rows: list[dict[str, Any]], batch_size: int, skip_embeddings: bool) -> None:
    if skip_embeddings:
        for row in rows:
            row["embedding"] = None
        return

    api_key = os.getenv("GOOGLE_API_KEY", "")
    if not api_key or api_key == "your_google_api_key":
        raise RuntimeError("GOOGLE_API_KEY is required unless --skip-embeddings is used.")

    embeddings = GoogleGenerativeAIEmbeddings(
        model=DANAWA_EMBEDDING_MODEL,
        output_dimensionality=DANAWA_EMBEDDING_DIM,
    )

    for start in range(0, len(rows), batch_size):
        batch = rows[start : start + batch_size]
        vectors = embeddings.embed_documents([row["chunk_text"] for row in batch])
        for row, vector in zip(batch, vectors, strict=True):
            row["embedding"] = _vector_literal(vector)
        print(f"Embedded {min(start + batch_size, len(rows))}/{len(rows)} chunks")


def _insert_rows(rows: list[dict[str, Any]]) -> None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required.")

    values = [
        (
            row["chunk_id"],
            row["chunk_type"],
            row["product_id"],
            row["product_name"],
            row["brand"],
            row["price"],
            row["tier"],
            row["avg_rating"],
            row["total_count"],
            row["positive_count"],
            row["negative_count"],
            row["positive_ratio"],
            row["connection_type"],
            row["sensor_model"],
            row["dpi_max"],
            row["polling_rate_hz"],
            row["weight_g"],
            row["is_gaming"],
            row["is_right_hand_only"],
            row["length_mm"],
            row["url"],
            row["thumbnail"],
            row["chunk_text"],
            row["embedding"],
        )
        for row in rows
    ]

    statement = """
        insert into danawa_chunks (
            chunk_id,
            chunk_type,
            product_id,
            product_name,
            brand,
            price,
            tier,
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
            chunk_text,
            embedding
        )
        values %s
        on conflict (chunk_id) do update set
            chunk_type = excluded.chunk_type,
            product_id = excluded.product_id,
            product_name = excluded.product_name,
            brand = excluded.brand,
            price = excluded.price,
            tier = excluded.tier,
            avg_rating = excluded.avg_rating,
            total_count = excluded.total_count,
            positive_count = excluded.positive_count,
            negative_count = excluded.negative_count,
            positive_ratio = excluded.positive_ratio,
            connection_type = excluded.connection_type,
            sensor_model = excluded.sensor_model,
            dpi_max = excluded.dpi_max,
            polling_rate_hz = excluded.polling_rate_hz,
            weight_g = excluded.weight_g,
            is_gaming = excluded.is_gaming,
            is_right_hand_only = excluded.is_right_hand_only,
            length_mm = excluded.length_mm,
            url = excluded.url,
            thumbnail = excluded.thumbnail,
            chunk_text = excluded.chunk_text,
            embedding = excluded.embedding,
            updated_at = now()
    """

    template = """
        (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s::extensions.vector
        )
    """

    with psycopg2.connect(database_url) as connection:
        with connection.cursor() as cursor:
            execute_values(cursor, statement, values, template=template, page_size=500)
        connection.commit()


def main() -> int:
    parser = argparse.ArgumentParser(description="Import Danawa chunk CSV into Supabase pgvector.")
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--skip-embeddings", action="store_true")
    args = parser.parse_args()

    rows = _read_csv(args.csv_path)
    if not rows:
        print("No rows found.")
        return 0

    _embed_rows(rows, batch_size=args.batch_size, skip_embeddings=args.skip_embeddings)
    _insert_rows(rows)
    print(f"Imported {len(rows)} Danawa chunks.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
