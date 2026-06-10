"""
reload_sizes.py — 모두모아 크기 데이터 재적재 (surgical update)

mouse_data_fixed.csv 의 크기 컬럼(length_mm / width_mm / height_mm / weight_g)을
운영 danawa_products 테이블에 product_id 기준으로 갱신한다.

설계 원칙:
  - product_id 로만 조인. 크기 외 컬럼(connectivity, is_silent 등)은 절대 건드리지 않음.
  - COALESCE(CSV값, 기존값): CSV에 값이 있으면 덮어쓰고, 비었으면 기존 DB 값 유지.
    → 멀쩡히 채워진 셀을 NULL 로 날리는 일이 없음. 멱등(여러 번 돌려도 결과 동일).
  - danawa_products 에 실제로 존재하는 크기 컬럼만 자동 감지해서 갱신.
  - --dry-run: 트랜잭션을 롤백하여 실제 변경 없이 before/after 만 확인.

사용법 (backend 폴더, 가상환경 활성화 상태):
    py -3.11 reload_sizes.py --csv mouse_data_fixed.csv --dry-run   # 먼저 미리보기
    py -3.11 reload_sizes.py --csv mouse_data_fixed.csv             # 실제 반영

필요: DATABASE_URL (.env), sqlalchemy, python-dotenv  (기존 백엔드와 동일 스택)
"""

import argparse
import csv
import os
import sys

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(override=True)

# danawa_products 에서 갱신 후보가 되는 크기 컬럼
SIZE_COLS = ["length_mm", "width_mm", "height_mm", "weight_g"]
KEY = "product_id"
TABLE = "danawa_products"
EMPTY = {"", "none", "nan", "null"}


def parse_num(value):
    """빈/결측은 None, 그 외엔 float. 변환 실패도 None 처리(개수 집계용 별도 추적)."""
    if value is None:
        return None
    v = str(value).strip()
    if v.lower() in EMPTY:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def load_csv(path):
    with open(path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        sys.exit(f"[중단] CSV에 데이터가 없음: {path}")
    if KEY not in rows[0]:
        sys.exit(f"[중단] CSV에 '{KEY}' 컬럼이 없음. 헤더 확인 필요.")

    staging = []
    seen = set()
    dup = 0
    for r in rows:
        pid = (r.get(KEY) or "").strip()
        if not pid:
            continue
        if pid in seen:
            dup += 1
            continue
        seen.add(pid)
        rec = {"product_id": pid}
        for c in SIZE_COLS:
            rec[c] = parse_num(r.get(c))
        staging.append(rec)
    if dup:
        print(f"[경고] CSV 내 중복 product_id {dup}건은 첫 행만 사용함.")
    return staging


def detect_columns(conn):
    """danawa_products 에 실제 존재하는 크기 컬럼만 추린다."""
    existing = {
        row[0]
        for row in conn.execute(
            text(
                "select column_name from information_schema.columns "
                "where table_name = :t and table_schema = 'public'"
            ),
            {"t": TABLE},
        )
    }
    present = [c for c in SIZE_COLS if c in existing]
    missing = [c for c in SIZE_COLS if c not in existing]
    if missing:
        print(f"[안내] DB에 없는 컬럼은 건너뜀: {missing}")
    if not present:
        sys.exit("[중단] 갱신할 크기 컬럼이 DB에 하나도 없음.")
    return present


def fill_report(conn, cols, label):
    total = conn.execute(text(f"select count(*) from {TABLE}")).scalar()
    print(f"\n── {label} (전체 {total}행) ──")
    out = {}
    for c in cols:
        filled = conn.execute(
            text(f"select count({c}) from {TABLE}")
        ).scalar()
        pct = (filled * 100 // total) if total else 0
        out[c] = filled
        print(f"   {c:11} {filled}/{total} ({pct}%)")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="mouse_data_fixed.csv")
    ap.add_argument("--dry-run", action="store_true",
                    help="실제 반영 없이 before/after만 출력하고 롤백")
    args = ap.parse_args()

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        sys.exit("[중단] DATABASE_URL 이 .env 에 없음.")

    staging = load_csv(args.csv)
    print(f"CSV 로드: {len(staging)}개 product_id")

    engine = create_engine(db_url)
    conn = engine.connect()
    trans = conn.begin()
    try:
        cols = detect_columns(conn)
        before = fill_report(conn, cols, "BEFORE")

        # 1) 세션 임시 테이블 (product_id 는 text 로 두어 타입 불일치 회피)
        coldefs = ", ".join(f"{c} double precision" for c in cols)
        conn.execute(text("drop table if exists _size_staging"))
        conn.execute(text(
            f"create temp table _size_staging "
            f"(product_id text primary key, {coldefs}) on commit drop"
        ))

        # 2) 적재 (executemany)
        insert_cols = ", ".join(["product_id"] + cols)
        insert_vals = ", ".join([":product_id"] + [f":{c}" for c in cols])
        conn.execute(
            text(f"insert into _size_staging ({insert_cols}) values ({insert_vals})"),
            [{"product_id": r["product_id"], **{c: r[c] for c in cols}} for r in staging],
        )

        # 3) 매칭 통계
        matched = conn.execute(text(
            f"select count(*) from {TABLE} t "
            f"join _size_staging s on t.{KEY}::text = s.product_id"
        )).scalar()
        only_csv = conn.execute(text(
            f"select count(*) from _size_staging s "
            f"left join {TABLE} t on t.{KEY}::text = s.product_id where t.{KEY} is null"
        )).scalar()
        print(f"\n매칭: DB와 일치 {matched}개 / CSV에만 있고 DB엔 없음 {only_csv}개")

        # 4) surgical update — COALESCE(CSV, 기존). CSV값 우선, 없으면 기존 유지.
        set_clause = ", ".join(
            f"{c} = coalesce(s.{c}, t.{c})" for c in cols
        )
        result = conn.execute(text(
            f"update {TABLE} t set {set_clause} "
            f"from _size_staging s where t.{KEY}::text = s.product_id"
        ))
        print(f"UPDATE 영향 행: {result.rowcount}")

        after = fill_report(conn, cols, "AFTER")
        print("\n── 변화량 ──")
        for c in cols:
            print(f"   {c:11} +{after[c] - before[c]}")

        if args.dry_run:
            trans.rollback()
            print("\n[DRY-RUN] 롤백 완료. 실제 반영 안 됨. "
                  "결과가 OK면 --dry-run 빼고 다시 실행.")
        else:
            trans.commit()
            print("\n[완료] 커밋됨. danawa_products 크기 컬럼 갱신 반영.")
    except Exception:
        trans.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
