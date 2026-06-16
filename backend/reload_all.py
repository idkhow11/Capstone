"""reload_all.py — danawa_products의 모든 스펙 컬럼을 CSV로 갱신하는 범용 로더.

기존 reload_weight.py가 일부 컬럼만 받던 것을, CSV에 있는 모든 스펙 컬럼을
product_id 기준으로 한 번에 갱신하도록 확장한 버전.

[안전 장치]
- COALESCE: CSV 칸이 비어 있으면 기존 DB 값을 유지(덮어쓰지 않음).
- product_id로 조인하여 해당 행만 갱신.
- --dry-run: 트랜잭션을 롤백해 실제 반영 없이 미리보기.
- 타입 자동 변환: 숫자/불리언/문자 컬럼을 컬럼별 규칙으로 안전 변환.

[사용법]
  python reload_all.py --csv mouse_data_fixed.csv --dry-run   # 미리보기
  python reload_all.py --csv mouse_data_fixed.csv             # 실제 반영
  python reload_all.py --csv mouse_data_fixed.csv --cols weight_g,length_mm  # 특정 컬럼만
"""

import argparse
import csv
import sys
from decimal import Decimal, InvalidOperation

from database import engine
from sqlalchemy import text

# ── 갱신 대상 컬럼과 타입 분류 ──────────────────────────────────────────────
# product_id는 조인 키(갱신 안 함). reviews는 길어서 기본 제외(원하면 --cols로 포함).
NUMERIC_INT_COLS = {
    "price", "max_dpi", "max_ips", "max_polling_rate",
    "battery_max_hours", "button_count", "total_reviews",
}
NUMERIC_FLOAT_COLS = {
    "weight_g", "length_mm", "width_mm", "height_mm",
    "max_acceleration_g", "avg_rating",
}
BOOL_COLS = {
    "is_rechargeable", "is_gaming", "has_rgb", "is_silent", "has_multi_pairing",
}
TEXT_COLS = {
    "url", "product_name", "brand", "tier", "feet_material", "sensor_model",
    "switch_type", "connectivity", "charging_port", "hand_orientation",
    "key_pros", "key_cons", "color", "switch_brand", "grip_type",
    "housing_design", "reviews",
}
ALL_UPDATABLE = NUMERIC_INT_COLS | NUMERIC_FLOAT_COLS | BOOL_COLS | TEXT_COLS

# Viper V4 등 확인용으로 출력할 컬럼
CHECK_COLS = ["product_name", "weight_g", "length_mm", "height_mm", "connectivity"]


def _clean(value: str) -> str:
    return (value or "").strip()


def _to_int(v: str):
    v = _clean(v).replace(",", "").rstrip("gG").strip()
    if not v:
        return None
    try:
        return int(float(v))
    except (ValueError, TypeError):
        return None


def _to_float(v: str):
    # "49g", "49.0g", "1,200" 같은 입력에서 숫자만 추출
    v = _clean(v).replace(",", "").rstrip("gG").strip()
    if not v:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def _to_bool(v: str):
    v = _clean(v).lower()
    if not v:
        return None
    if v in ("true", "1", "y", "yes", "o", "있음", "지원"):
        return True
    if v in ("false", "0", "n", "no", "x", "없음", "미지원"):
        return False
    return None


def _to_text(v: str):
    v = _clean(v)
    return v if v else None


def _convert(col: str, raw: str):
    if col in NUMERIC_INT_COLS:
        return _to_int(raw)
    if col in NUMERIC_FLOAT_COLS:
        return _to_float(raw)
    if col in BOOL_COLS:
        return _to_bool(raw)
    return _to_text(raw)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, help="갱신할 CSV 파일 경로")
    ap.add_argument("--cols", default=None,
                    help="갱신할 컬럼만 콤마로 지정 (생략 시 CSV의 모든 갱신가능 컬럼)")
    ap.add_argument("--dry-run", action="store_true", help="미리보기(롤백, 반영 안 함)")
    args = ap.parse_args()

    # CSV 읽기
    try:
        with open(args.csv, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []
            rows = list(reader)
    except FileNotFoundError:
        print(f"[에러] CSV 파일을 찾을 수 없음: {args.csv}")
        sys.exit(1)

    if "product_id" not in headers:
        print("[에러] CSV에 product_id 컬럼이 없습니다.")
        sys.exit(1)

    # 갱신할 컬럼 결정
    if args.cols:
        target_cols = [c.strip() for c in args.cols.split(",") if c.strip()]
    else:
        target_cols = [c for c in headers if c in ALL_UPDATABLE]

    # CSV에 실제 존재하고 갱신 가능한 컬럼만
    target_cols = [c for c in target_cols if c in headers and c in ALL_UPDATABLE]
    if not target_cols:
        print("[에러] 갱신할 컬럼이 없습니다. CSV 헤더와 --cols를 확인하세요.")
        print(f"  CSV 헤더: {headers}")
        sys.exit(1)

    print(f"갱신 대상 컬럼 ({len(target_cols)}개): {', '.join(target_cols)}")

    # CSV에서 컬럼별 채워진 행 수
    for col in target_cols:
        filled = sum(1 for r in rows if _clean(r.get(col, "")))
        print(f"  CSV '{col}' 채워진 행: {filled}/{len(rows)}")

    # BEFORE 채움률
    print("── BEFORE ──")
    with engine.connect() as conn:
        total = conn.execute(text("select count(*) from danawa_products")).scalar()
        for col in target_cols:
            n = conn.execute(text(
                f"select count({col}) from danawa_products"
            )).scalar()
            print(f"   {col}: {n}/{total} ({round(n*100/total)}%)")

    # UPDATE 실행 (COALESCE로 빈 값은 기존 유지)
    set_clause = ", ".join(
        f"{col} = COALESCE(:{col}, {col})" for col in target_cols
    )
    update_sql = text(
        f"update danawa_products set {set_clause} where product_id::text = :pid"
    )

    # dry-run은 connection + 수동 롤백, 실제 반영은 begin(자동 커밋)
    conn = engine.connect()
    trans = conn.begin()
    try:
        affected = 0
        for r in rows:
            pid = _clean(r.get("product_id", ""))
            if not pid:
                continue
            params = {"pid": pid}
            for col in target_cols:
                params[col] = _convert(col, r.get(col, ""))
            res = conn.execute(update_sql, params)
            affected += res.rowcount

        print(f"매칭/영향 행: {affected}")

        # AFTER 채움률 (같은 트랜잭션 내)
        print("── AFTER ──")
        total = conn.execute(text("select count(*) from danawa_products")).scalar()
        for col in target_cols:
            n = conn.execute(text(
                f"select count({col}) from danawa_products"
            )).scalar()
            print(f"   {col}: {n}/{total} ({round(n*100/total)}%)")

        # Viper V4 확인
        print("── Viper V4 확인 ──")
        check = conn.execute(text(
            f"select {', '.join(CHECK_COLS)} from danawa_products "
            "where product_name ilike '%viper v4%'"
        )).fetchall()
        for row in check:
            print("  ", dict(zip(CHECK_COLS, row)))

        if args.dry_run:
            trans.rollback()
            print("[DRY-RUN] 롤백 완료. 실제 반영 안 됨. OK면 --dry-run 빼고 재실행.")
        else:
            trans.commit()
            print("[커밋 완료] DB에 반영됨.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()