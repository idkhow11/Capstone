"""
reload_weight.py — 모두모아 무게(weight_g) 재적재

직접 채운 CSV의 weight_g 를 운영 danawa_products 에 product_id 기준으로 갱신한다.
reload_data.py(price/url) 와 동일 정신:
  - product_id 로만 조인. weight_g 한 컬럼만 갱신.
  - COALESCE(CSV값, 기존값): CSV에 값 있으면 덮어쓰고, 비어있으면 기존 유지.
    (→ CSV가 비어있는 행은 절대 기존 데이터를 지우지 않음. 안전.)
  - 멱등. --dry-run 으로 먼저 미리보기.

사용법 (backend 폴더, 가상환경):
    python reload_weight.py --csv mouse_data_fixed.csv --dry-run
    python reload_weight.py --csv mouse_data_fixed.csv
    # 다른 스펙도 직접 넣었으면 --cols 로 추가 (쉼표 구분):
    python reload_weight.py --csv mouse_data_fixed.csv --cols weight_g,max_dpi,battery_max_hours
"""

import argparse
import csv
import os
import sys

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(override=True)

KEY = "product_id"
TABLE = "danawa_products"
EMPTY = {"", "none", "nan", "null"}


def parse_num(v):
    v = (v or "").replace(",", "").strip()
    if v.lower() in EMPTY:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def load_csv(path, cols):
    with open(path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows or KEY not in rows[0]:
        sys.exit(f"[중단] '{KEY}' 컬럼이 없음: {path}")
    for c in cols:
        if c not in rows[0]:
            sys.exit(f"[중단] CSV에 '{c}' 컬럼이 없음. 헤더 확인 필요.")
    staging, seen = [], set()
    for r in rows:
        pid = (r.get(KEY) or "").strip()
        if not pid or pid in seen:
            continue
        seen.add(pid)
        row = {"product_id": pid}
        for c in cols:
            row[c] = parse_num(r.get(c))
        staging.append(row)
    return staging


def fill(conn, col):
    total = conn.execute(text(f"select count(*) from {TABLE}")).scalar()
    filled = conn.execute(text(f"select count({col}) from {TABLE}")).scalar()
    pct = (filled * 100 // total) if total else 0
    return f"{filled}/{total} ({pct}%)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="mouse_data_fixed.csv")
    ap.add_argument("--cols", default="weight_g",
                    help="갱신할 숫자 컬럼들 (쉼표 구분). 기본: weight_g")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cols = [c.strip() for c in args.cols.split(",") if c.strip()]

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        sys.exit("[중단] DATABASE_URL 이 .env 에 없음.")

    staging = load_csv(args.csv, cols)
    # CSV에서 실제 값이 채워진 행 수 (컬럼별)
    for c in cols:
        n = sum(1 for s in staging if s[c] is not None)
        print(f"CSV '{c}' 채워진 행: {n}/{len(staging)}")

    engine = create_engine(db_url)
    conn = engine.connect()
    trans = conn.begin()
    try:
        print(f"\n── BEFORE ──")
        for c in cols:
            print(f"   {c}: {fill(conn, c)}")

        # staging temp table (product_id + 숫자 컬럼들)
        coldefs = ", ".join(f"{c} double precision" for c in cols)
        conn.execute(text("drop table if exists _weight_staging"))
        conn.execute(text(
            f"create temp table _weight_staging "
            f"(product_id text primary key, {coldefs}) on commit drop"
        ))
        placeholders = ", ".join(f":{c}" for c in cols)
        conn.execute(
            text(f"insert into _weight_staging (product_id, {', '.join(cols)}) "
                 f"values (:product_id, {placeholders})"),
            staging,
        )

        matched = conn.execute(text(
            f"select count(*) from {TABLE} t join _weight_staging s "
            f"on t.{KEY}::text = s.product_id"
        )).scalar()
        print(f"\n매칭(product_id 일치): {matched}개")

        # surgical update: COALESCE(CSV, 기존) — 빈 CSV값은 기존 유지
        set_parts = [f"{c} = coalesce(s.{c}, t.{c})" for c in cols]
        res = conn.execute(text(
            f"update {TABLE} t set {', '.join(set_parts)} "
            f"from _weight_staging s where t.{KEY}::text = s.product_id"
        ))
        print(f"UPDATE 영향 행: {res.rowcount}")

        print(f"\n── AFTER ──")
        for c in cols:
            print(f"   {c}: {fill(conn, c)}")

        # Viper V4 검증 출력
        print(f"\n── Viper V4 확인 ──")
        viper = conn.execute(text(
            f"select product_name, {', '.join(cols)} from {TABLE} "
            f"where product_name ~* 'viper v4' order by product_name"
        )).fetchall()
        if viper:
            for row in viper:
                print("  ", dict(row._mapping))
        else:
            print("   (viper v4 매칭 제품 없음)")

        if args.dry_run:
            trans.rollback()
            print("\n[DRY-RUN] 롤백 완료. 실제 반영 안 됨. OK면 --dry-run 빼고 재실행.")
        else:
            trans.commit()
            print("\n[완료] 커밋됨.")
    except Exception:
        trans.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()