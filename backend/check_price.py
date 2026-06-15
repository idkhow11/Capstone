from database import engine
from sqlalchemy import text

with engine.connect() as conn:
    # "무선" 으로만 검색하면 product 경로가 78개를 잡나?
    n = conn.execute(text("""
        SELECT COUNT(*) FROM danawa_products
        WHERE price >= 100000
          AND (connectivity ILIKE '%무선%' OR connectivity ILIKE '%블루투스%')
          AND (search_vector @@ plainto_tsquery('simple', '무선 마우스')
               OR product_name ILIKE '%무선%')
    """)).scalar()
    print(f"'무선 마우스' 검색어로 잡히는 10만원+ 무선: {n}개")