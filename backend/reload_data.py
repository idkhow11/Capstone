"""
reload_data.py — 모두모아 가격/링크 최신화 재적재

mouse_data_fixed__4_.csv 의 price, url 을 운영 danawa_products 에
product_id 기준으로 갱신한다. 더불어 신규 CSV에서 빠진 제품(타블렛/단종)을
정리하는 옵션을 제공한다.

설계 원칙(reload_sizes.py와 동일 정신):
  - product_id 로만 조인. price, url 두 컬럼만 갱신.
  - COALESCE(CSV값, 기존값): CSV에 값이 있으면 덮어쓰고, 없으면 기존 유지.
    (CSV가 price/url 100% 채움이라 사실상 항상 CSV 최신값으로 갱신됨)
  - 멱등. --dry-run 으로 먼저 미리보기 가능.

빠진 제품(신규 CSV에 없는 DB 행) 처리:
  --remove-tablets : 타블렛/비마우스(NON_MOUSE_PATTERN)만 삭제 (권장 청소)
  --remove-missing : 신규 CSV에 없는 모든 행 삭제 (현 카탈로그로 완전 동기화)
  (둘 다 안 주면 빠진 제품은 그대로 둠)

사용법 (backend 폴더, 가상환경):
    python reload_data.py --csv mouse_data_fixed__4_.csv --dry-run
    python reload_data.py --csv mouse_data_fixed__4_.csv --remove-tablets
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
# 비마우스(타블렛/액정) 식별 패턴 — danawa_rag.NON_MOUSE_PATTERN 과 동일
NON_MOUSE_PATTERN = r"(cintiq|신티크|kamvas|artist|inspiroy|deco|veikk|ugee|wacom|huion|xp-?pen|액정|타블렛|태블릿)"


def parse_price(v):
    v = (v or "").replace(",", "").strip()
    if v.lower() in EMPTY:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def parse_text(v):
    v = (v or "").strip()
    return v or None


def load_csv(path):
    with open(path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows or KEY not in rows[0]:
        sys.exit(f"[중단] '{KEY}' 컬럼이 없거나 비어있음: {path}")
    has_url = "url" in rows[0]
    staging, seen = [], set()
    for r in rows:
        pid = (r.get(KEY) or "").strip()
        if not pid or pid in seen:
            continue
        seen.add(pid)
        staging.append({
            "product_id": pid,
            "price": parse_price(r.get("price")),
            "url": parse_text(r.get("url")) if has_url else None,
        })
    return staging, has_url


def fill(conn, col):
    total = conn.execute(text(f"select count(*) from {TABLE}")).scalar()
    filled = conn.execute(text(f"select count({col}) from {TABLE}")).scalar()
    pct = (filled * 100 // total) if total else 0
    return f"{filled}/{total} ({pct}%)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="mouse_data_fixed__4_.csv")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--remove-tablets", action="store_true",
                    help="신규 CSV에 없는 행 중 타블렛/비마우스만 삭제")
    ap.add_argument("--remove-missing", action="store_true",
                    help="신규 CSV에 없는 모든 행 삭제(현 카탈로그로 완전 동기화)")
    args = ap.parse_args()

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        sys.exit("[중단] DATABASE_URL 이 .env 에 없음.")

    staging, has_url = load_csv(args.csv)
    print(f"CSV 로드: {len(staging)}개 product_id (url 포함: {has_url})")
    update_url = has_url

    engine = create_engine(db_url)
    conn = engine.connect()
    trans = conn.begin()
    try:
        before_total = conn.execute(text(f"select count(*) from {TABLE}")).scalar()
        print(f"\n── BEFORE ── 전체 {before_total}행")
        print(f"   price: {fill(conn,'price')}")
        if update_url:
            print(f"   url  : {fill(conn,'url')}")

        # staging temp table
        conn.execute(text("drop table if exists _data_staging"))
        conn.execute(text(
            "create temp table _data_staging "
            "(product_id text primary key, price double precision, url text) "
            "on commit drop"
        ))
        conn.execute(
            text("insert into _data_staging (product_id, price, url) "
                 "values (:product_id, :price, :url)"),
            staging,
        )

        matched = conn.execute(text(
            f"select count(*) from {TABLE} t join _data_staging s "
            f"on t.{KEY}::text = s.product_id"
        )).scalar()
        missing = conn.execute(text(
            f"select count(*) from {TABLE} t left join _data_staging s "
            f"on t.{KEY}::text = s.product_id where s.product_id is null"
        )).scalar()
        print(f"\n매칭: DB와 일치 {matched}개 / 신규 CSV에 없는 DB행 {missing}개")

        # surgical update: price (+ url)
        set_parts = ["price = coalesce(s.price, t.price)"]
        if update_url:
            set_parts.append("url = coalesce(s.url, t.url)")
        res = conn.execute(text(
            f"update {TABLE} t set {', '.join(set_parts)} "
            f"from _data_staging s where t.{KEY}::text = s.product_id"
        ))
        print(f"UPDATE 영향 행: {res.rowcount}")

        # 빠진 제품 처리
        if args.remove_missing:
            d = conn.execute(text(
                f"delete from {TABLE} t where not exists "
                f"(select 1 from _data_staging s where s.product_id = t.{KEY}::text)"
            ))
            print(f"삭제(신규 CSV에 없는 전체): {d.rowcount}행")
        elif args.remove_tablets:
            d = conn.execute(text(
                f"delete from {TABLE} t where not exists "
                f"(select 1 from _data_staging s where s.product_id = t.{KEY}::text) "
                f"and (product_name || ' ' || coalesce(brand,'')) ~* :nm"
            ), {"nm": NON_MOUSE_PATTERN})
            print(f"삭제(빠진 것 중 타블렛만): {d.rowcount}행")

        after_total = conn.execute(text(f"select count(*) from {TABLE}")).scalar()
        print(f"\n── AFTER ── 전체 {after_total}행")
        print(f"   price: {fill(conn,'price')}")
        if update_url:
            print(f"   url  : {fill(conn,'url')}")

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
