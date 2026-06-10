from database import engine
from sqlalchemy import text

with engine.connect() as conn:
    rows = conn.execute(text("""
        SELECT DISTINCT housing_design, COUNT(*) 
        FROM danawa_products 
        WHERE housing_design IS NOT NULL 
        GROUP BY housing_design ORDER BY COUNT(*) DESC
    """)).fetchall()
    for r in rows:
        print(f"  {r[0]}: {r[1]}개")
    
    # grip_type 도
    print("--- grip_type ---")
    rows = conn.execute(text("""
        SELECT DISTINCT grip_type, COUNT(*) 
        FROM danawa_products 
        WHERE grip_type IS NOT NULL 
        GROUP BY grip_type ORDER BY COUNT(*) DESC
    """)).fetchall()
    for r in rows:
        print(f"  {r[0]}: {r[1]}개")