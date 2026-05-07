import argparse
import csv
import os
import sys
from pathlib import Path
from typing import Any

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import execute_values

load_dotenv(override=True)

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


def _resolve_product_url(product_id: str, url: str | None) -> str:
    if url:
        return url
    return DANAWA_PRODUCT_URL_TEMPLATE.format(product_id=product_id)


def _read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        rows = []
        for row in reader:
            rows.append(
                {
                    "product_id": str(row["product_id"]),
                    "product_name": row["product_name"],
                    "brand": row.get("brand") or None,
                    "price": _clean_int(row.get("price")),
                    "tier": row.get("tier") or None,
                    "weight_g": _clean_float(row.get("weight_g")),
                    "length_mm": _clean_float(row.get("length_mm")),
                    "width_mm": _clean_float(row.get("width_mm")),
                    "height_mm": _clean_float(row.get("height_mm")),
                    "feet_material": row.get("feet_material") or None,
                    "sensor_model": row.get("sensor_model") or None,
                    "max_dpi": _clean_int(row.get("max_dpi")),
                    "max_ips": _clean_int(row.get("max_ips")),
                    "max_acceleration_g": _clean_int(row.get("max_acceleration_g")),
                    "max_polling_rate": _clean_int(row.get("max_polling_rate")),
                    "switch_type": row.get("switch_type") or None,
                    "connectivity": row.get("connectivity") or None,
                    "battery_max_hours": _clean_int(row.get("battery_max_hours")),
                    "charging_port": row.get("charging_port") or None,
                    "is_rechargeable": _clean_bool(row.get("is_rechargeable")),
                    "button_count": _clean_int(row.get("button_count")),
                    "is_gaming": _clean_bool(row.get("is_gaming")) or False,
                    "hand_orientation": row.get("hand_orientation") or None,
                    "avg_rating": _clean_float(row.get("avg_rating")),
                    "total_reviews": _clean_int(row.get("total_reviews")),
                    "key_pros": row.get("key_pros") or None,
                    "key_cons": row.get("key_cons") or None,
                    "has_rgb": _clean_bool(row.get("has_rgb")),
                    "color": row.get("color") or None,
                    "is_silent": _clean_bool(row.get("is_silent")),
                    "switch_brand": row.get("switch_brand") or None,
                    "has_multi_pairing": _clean_bool(row.get("has_multi_pairing")),
                    "grip_type": row.get("grip_type") or None,
                    "housing_design": row.get("housing_design") or None,
                    "reviews": row.get("reviews") or None,
                    "url": _resolve_product_url(str(row["product_id"]), row.get("url")),
                    "thumbnail": row.get("thumbnail") or None,
                }
            )
    return rows


def _insert_rows(rows: list[dict[str, Any]]) -> None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required.")

    columns = [
        "product_id",
        "product_name",
        "brand",
        "price",
        "tier",
        "weight_g",
        "length_mm",
        "width_mm",
        "height_mm",
        "feet_material",
        "sensor_model",
        "max_dpi",
        "max_ips",
        "max_acceleration_g",
        "max_polling_rate",
        "switch_type",
        "connectivity",
        "battery_max_hours",
        "charging_port",
        "is_rechargeable",
        "button_count",
        "is_gaming",
        "hand_orientation",
        "avg_rating",
        "total_reviews",
        "key_pros",
        "key_cons",
        "has_rgb",
        "color",
        "is_silent",
        "switch_brand",
        "has_multi_pairing",
        "grip_type",
        "housing_design",
        "reviews",
        "url",
        "thumbnail",
    ]
    values = [tuple(row[column] for column in columns) for row in rows]
    update_assignments = ",\n            ".join(
        f"{column} = excluded.{column}" for column in columns if column != "product_id"
    )

    statement = f"""
        insert into danawa_products ({", ".join(columns)})
        values %s
        on conflict (product_id) do update set
            {update_assignments},
            updated_at = now()
    """

    with psycopg2.connect(database_url) as connection:
        with connection.cursor() as cursor:
            execute_values(cursor, statement, values, page_size=500)
        connection.commit()


def main() -> int:
    parser = argparse.ArgumentParser(description="Import mouse_data.csv into Supabase.")
    parser.add_argument("csv_path", type=Path)
    args = parser.parse_args()

    rows = _read_csv(args.csv_path)
    if not rows:
        print("No rows found.")
        return 0

    _insert_rows(rows)
    print(f"Imported {len(rows)} Danawa products.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
