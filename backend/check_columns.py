from database import engine
from sqlalchemy import text

with engine.connect() as conn:
    # 1) 전체 행 수
    total = conn.execute(text("select count(*) from danawa_products")).scalar()
    print("DB 제품 수:", total, "(CSV는 1030개)")
    print()

    # 2) 주요 컬럼 채움 비율 (CSV와 비교용)
    print("=== 컬럼별 채움 비율 ===")
    cols = ["weight_g", "length_mm", "width_mm", "height_mm",
            "max_dpi", "connectivity", "is_silent", "is_gaming",
            "hand_orientation", "grip_type", "price", "avg_rating"]
    for col in cols:
        filled = conn.execute(text(f"select count({col}) from danawa_products")).scalar()
        pct = round(filled / total * 100) if total else 0
        print(f"  {col}: {filled}/{total} ({pct}%)")
    print()

    # 3) 샘플 제품 5개 실제 값 확인
    print("=== 샘플 제품 5개 ===")
    rows = conn.execute(text(
        "select product_id, product_name, price, weight_g, connectivity, is_silent "
        "from danawa_products limit 5"
    ))
    for r in rows:
        print(f"  [{r[0]}] {r[1]} | {r[2]}원 | {r[3]}g | {r[4]} | silent={r[5]}")
    print()

    # 4) 값이 통째로 빈 컬럼(완전 누락) 탐지
    print("=== 완전히 비어있는(0%) 컬럼 점검 ===")
    for col in cols:
        filled = conn.execute(text(f"select count({col}) from danawa_products")).scalar()
        if filled == 0:
            print(f"  ⚠ {col}: 데이터 전혀 없음")
    print("점검 완료")