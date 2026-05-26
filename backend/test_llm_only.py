"""DB 없이 LLM/도구 호출만 검증하는 스크립트.

목적:
  - Gemini가 실제로 도구를 자율 호출하는지 (ReAct 루프)
  - map_language_to_specs가 "팔목 아파서" 같은 효과 표현을 스펙으로 변환하는지
  - ask_clarifying_question이 모호한 질의에 되묻는지

특징:
  - 서버(uvicorn)를 띄우지 않는다. run_shopping_agent를 직접 호출.
  - database.engine을 가짜로 막아 DB 연결을 시도하지 않게 한다.
  - search_products(다나와 검색)는 가짜 데이터를 반환하도록 패치.
    → 실제 제품은 안 나오지만, "어떤 도구가 불렸는가"는 그대로 관찰된다.

사용법 (가상환경 켜고, backend 폴더에서):
  python test_llm_only.py
  python test_llm_only.py --q "조용한 사무용 마우스"
"""

import argparse
import sys
import types


# ── 1) database.engine 스텁 주입 (import 시 DB 연결 막기) ──────────────────
def _install_db_stub() -> None:
    class _FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def execute(self, *a, **k):
            from sqlalchemy.exc import SQLAlchemyError
            raise SQLAlchemyError("DB stub (no real connection in LLM-only test)")

    class _FakeEngine:
        def connect(self):
            return _FakeConn()

        def begin(self):
            return _FakeConn()

    db_mod = types.ModuleType("database")
    db_mod.engine = _FakeEngine()

    class _Base:
        class metadata:
            @staticmethod
            def create_all(*a, **k):
                pass

    db_mod.Base = _Base
    db_mod.get_db = lambda: iter([])
    sys.modules["database"] = db_mod


_install_db_stub()


# ── 2) search_products 도구를 가짜 데이터로 패치 ──────────────────────────
# (DB가 없으니 실제 검색은 못 하지만, LLM이 이 도구를 부르는지/어떤 인자로
#  부르는지는 그대로 관찰된다. 호출되면 콘솔에 인자를 출력.)
import services.agent as agent  # noqa: E402

_FAKE_PRODUCTS = [
    {"product_id": "1001", "name": "(예시) 경량 무선 마우스 A", "brand": "테스트",
     "price": 39000, "url": "", "thumbnail": "", "reason": "58g, 무선, 저소음", "score": 0.95},
    {"product_id": "1002", "name": "(예시) 인체공학 마우스 B", "brand": "테스트",
     "price": 52000, "url": "", "thumbnail": "", "reason": "버티컬, 65g", "score": 0.88},
]


def _patch_search_tool():
    """agent.TOOLS 안의 search_products를 가짜로 교체하고 호출 로그를 남긴다."""
    from langchain_core.tools import tool

    @tool
    def search_products(query: str, budget_krw: int | None = None,
                        spec_filters: dict | None = None) -> list[dict]:
        """다나와 DB에서 조건에 맞는 PC 마우스를 검색해 상위 후보를 반환한다.

        사용자가 충분한 정보를 줬을 때 호출하라. 정보가 부족하면 먼저
        ask_clarifying_question을 사용하라. 자연어 조건이 있으면 먼저
        map_language_to_specs로 변환한 결과를 spec_filters에 넣어라.
        """
        print("\n  [TOOL CALL] search_products")
        print(f"     query       = {query!r}")
        print(f"     budget_krw  = {budget_krw}")
        print(f"     spec_filters= {spec_filters}")
        return _FAKE_PRODUCTS

    # 원래 map_language_to_specs / ask_clarifying_question 도 로그를 남기게 감싼다
    orig_map = agent._TOOLS_BY_NAME["map_language_to_specs"]
    orig_ask = agent._TOOLS_BY_NAME["ask_clarifying_question"]

    @tool
    def map_language_to_specs(user_phrase: str) -> dict:
        """사용자의 일상 자연어 표현을 정량적인 마우스 검색 스펙으로 변환한다.

        "손목이 아파서", "조용한 거", "오래 써도 편한" 같은 모호하거나 비정형적인
        표현이 질의에 있을 때 먼저 호출하라.
        """
        result = orig_map.invoke({"user_phrase": user_phrase})
        print(f"\n  [TOOL CALL] map_language_to_specs(user_phrase={user_phrase!r})")
        print(f"     → 변환 결과: {result}")
        return result

    @tool
    def ask_clarifying_question(missing_aspect: str) -> str:
        """요구가 너무 모호해 검색이 어려울 때 사용자에게 되물을 질문을 생성한다."""
        result = orig_ask.invoke({"missing_aspect": missing_aspect})
        print(f"\n  [TOOL CALL] ask_clarifying_question(missing_aspect={missing_aspect!r})")
        print(f"     → 생성된 질문: {result}")
        return result

    new_tools = [map_language_to_specs, search_products, ask_clarifying_question,
                 agent._TOOLS_BY_NAME["compare_products"]]
    agent.TOOLS = new_tools
    agent._TOOLS_BY_NAME = {t.name: t for t in new_tools}
    # 그래프 캐시 초기화 (새 도구 반영)
    agent._graph = None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--q", default=None, help="테스트할 질의")
    args = parser.parse_args()

    _patch_search_tool()

    # 키 확인 (게이트웨이 키 우선, GOOGLE_API_KEY도 허용)
    import os
    key = os.getenv("GATEWAY_API_KEY") or os.getenv("GOOGLE_API_KEY", "")
    if not key or key in ("your_google_api_key", "your_gateway_api_key"):
        print("!! API 키가 .env에 없습니다. GATEWAY_API_KEY를 채워주세요.")
        print("   (.env 파일이 backend 폴더에 있고 키가 채워졌는지 확인하세요.)")
        return

    print(f"사용 모델: {os.getenv('SHOPPING_AGENT_MODEL', 'gemini-2.0-flash')}")
    print("=" * 70)

    if args.q:
        queries = [args.q]
    else:
        queries = [
            "팔목이 아파서 편한 마우스 추천해줘",   # 효과→기능 매핑 기대
            "마우스 추천",                          # 모호 → 되묻기 기대
            "FPS 게임용 가벼운 무선 마우스",         # 명확 → 바로 검색 기대
        ]

    from services.agent import run_shopping_agent

    for q in queries:
        print(f"\n{'='*70}\n[질의] {q}\n{'-'*70}")
        try:
            result = run_shopping_agent(q)
            print(f"\n  [최종 추천]\n  {result.recommendation}")
            print(f"\n  [products 개수] {len(result.products)} (가짜 데이터라 예시 제품)")
        except Exception as exc:
            import traceback
            print(f"  !! 에러 발생: {exc}")
            traceback.print_exc()


if __name__ == "__main__":
    main()