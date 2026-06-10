"""모두모아 쇼핑 어시스턴트 에이전트 (ReAct 패턴).

이 파일은 기존 결정론적 파이프라인(analyze→retrieve→rank→generate)을
수동 StateGraph ReAct 루프(reason ⇄ tools, 최대 5회)로 교체한 버전이다.

[외부 인터페이스 — 변경 없음 / DO NOT CHANGE]
  - run_shopping_agent(query, conversation_messages) -> AgentResult
  - AgentResult(recommendation, products)
  routers/search.py 와 schemas.py 는 이 인터페이스에만 의존하므로 손대지 않는다.

[2-에이전트 + Hybrid Router]
  run_shopping_agent 진입 시 _classify_intent(룰+LLM)로 의도를 판별:
    - "search" → Spec Matching Agent (기존 검색 ReAct, 무변경)
    - "compare" → Comparison Agent (비교 ReAct, 신규)
  검색 경로는 그대로 보존되며(데모 안정성), 비교는 형제 그래프로 추가된다.

[Spec Matching Agent 도구 4종]
  1. search_products         : 다나와 DB 검색 (danawa_rag 재활용)
  2. map_language_to_specs   : 자연어 → 정량 스펙 (룰 + LLM 폴백 + 화이트리스트 검증)
  3. ask_clarifying_question : 모호한 요구 명확화 (대화형 핵심)
  4. compare_products        : 제품 비교(실제 스펙 조회)

[Comparison Agent 도구]
  search_products / retrieve_product_details / compare_products / prioritize_products
"""

import json
import os
import re
from dataclasses import dataclass, field
from typing import Annotated, Any, TypedDict

from dotenv import load_dotenv
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from services.danawa_rag import get_product_details, search_danawa_products

load_dotenv(override=True)

MAX_ITERATIONS = int(os.getenv("REACT_MAX_ITERATIONS", "5"))


# ============================================================================
# 섹션 1: 타입 정의 (기존 Product / AgentResult 유지)
# ============================================================================
class Product(TypedDict, total=False):
    product_id: str
    name: str
    brand: str
    price: int | None
    url: str
    thumbnail: str
    reason: str
    score: float


class ReactAgentState(TypedDict):
    """ReAct 상태. messages는 add_messages 리듀서로 자동 누적된다."""
    messages: Annotated[list[BaseMessage], add_messages]
    iteration: int
    # 도구가 채워두는 마지막 검색 결과. 최종 응답에서 products로 반환.
    last_products: list[Product]


@dataclass(frozen=True)
class AgentResult:
    recommendation: str
    products: list[Product]


# ============================================================================
# 섹션 2: LLM 초기화 (lazy + 폴백 안전장치)
# ============================================================================
_llm = None


def _get_llm() -> ChatOpenAI | None:
    global _llm
    if _llm is not None:
        return _llm
    # 전북대 멀티 LLM 게이트웨이(OpenAI 호환)를 통해 호출한다.
    api_key = os.getenv("GATEWAY_API_KEY") or os.getenv("GOOGLE_API_KEY", "")
    if not api_key or api_key in ("your_google_api_key", "your_gateway_api_key"):
        return None
    base_url = os.getenv(
        "GATEWAY_BASE_URL",
        "https://factchat-cloud.mindlogic.ai/v1/gateway",
    )
    model_name = os.getenv("SHOPPING_AGENT_MODEL", "gemini-2.5-flash")
    _llm = ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=base_url,
        temperature=0.2,
        max_retries=1,
        timeout=30,
    )
    return _llm


# ============================================================================
# 섹션 3: 룰 기반 매핑 자산 (14키 + size_pref 화이트리스트)
# ============================================================================
ALLOWED_SPEC_KEYS = {
    "connection_type", "is_gaming", "max_weight_g", "right_hand_only",
    "left_hand_ok", "min_dpi", "min_polling_rate_hz", "min_battery_hours",
    "is_silent", "has_rgb", "has_multi_pairing", "min_button_count",
    "grip_query", "color_query",
    "size_pref",   # ── PATCH: 크기 상대 디스크립터 'large'|'small' ──
}


def _rule_based_map(phrase: str) -> dict[str, Any]:
    """확실하고 빠른 룰 매핑. 흔한 표현은 여기서 결정적으로 처리(재현성)."""
    t = phrase.lower()
    specs: dict[str, Any] = {}

    if "무선" in t or "블루투스" in t:
        specs["connection_type"] = "무선"
    elif "유선" in t:
        specs["connection_type"] = "유선"

    if "게이밍" in t or "게임" in t or "fps" in t:
        specs["is_gaming"] = True
    if "가벼" in t or "초경량" in t or "fps" in t:
        specs["max_weight_g"] = 70
    if "오른손" in t:
        specs["right_hand_only"] = True
    if "왼손" in t or "양손" in t:
        specs["left_hand_ok"] = True
    if "dpi" in t or "고감도" in t:
        specs["min_dpi"] = 16000
    if "폴링" in t or "hz" in t:
        specs["min_polling_rate_hz"] = 1000
    if "배터리" in t:
        specs["min_battery_hours"] = 80
    if "무소음" in t or "저소음" in t or "조용" in t:
        specs["is_silent"] = True
    if "rgb" in t or "조명" in t or "led" in t:
        specs["has_rgb"] = True
    if "멀티페어링" in t or "멀티 페어링" in t:
        specs["has_multi_pairing"] = True
    if "버튼" in t or "매크로" in t:
        specs["min_button_count"] = 6
    # ── PATCH: 손목/팔목 통증·인체공학 효과 → 에르고 형태(housing_design 매칭) ──
    # 개별 표현(어깨/거북목/저림…)을 일일이 룰로 늘리지 않고, 효과를 "에르고"라는
    # 형태 카테고리로 수렴시킨다. 그 외 의미적 표현은 LLM 폴백이 같은 카테고리로 매핑.
    if any(k in t for k in ("팔목", "손목", "인체공학", "에르고", "버티컬", "수직",
                            "어깨", "거북목", "장시간", "오래 써도", "오래 쓰", "자세")):
        specs["grip_query"] = "에르고"
    elif "팜그립" in t or "팜 그립" in t:
        specs["grip_query"] = "팜"
    if "블랙" in t or "검정" in t:
        specs["color_query"] = "블랙"
    elif "화이트" in t or "흰색" in t:
        specs["color_query"] = "화이트"

    # ── PATCH: 명시적 크기 표현만 룰로 결정 (의미적 케이스는 LLM 폴백) ──
    if any(k in t for k in ("큰", "커다", "대형", "큼직", "손에 꽉")):
        specs["size_pref"] = "large"
    elif any(k in t for k in ("작은", "소형", "미니", "콤팩트", "작고")):
        specs["size_pref"] = "small"

    return specs


_SPEC_SCHEMA_DOC = """\
- connection_type: "무선" 또는 "유선" (둘 중 하나만, 그 외 금지)
- is_gaming: true (게이밍/FPS 용도일 때만)
- max_weight_g: 정수 (가벼움을 원하면 무게 상한. 예: 가벼운→80, 초경량→65)
- right_hand_only: true (오른손 전용 요구 시)
- left_hand_ok: true (왼손/양손 요구 시)
- min_dpi: 정수 (고감도/정밀 요구 시. 예: 16000)
- min_polling_rate_hz: 정수 (빠른 반응 요구 시. 예: 1000)
- min_battery_hours: 정수 (배터리 오래가는 것 요구 시. 예: 80)
- is_silent: true (조용함/무소음 요구 시)
- has_rgb: true (조명/RGB 요구 시)
- has_multi_pairing: true (멀티페어링 요구 시)
- min_button_count: 정수 (버튼 많이/매크로 요구 시. 예: 6)
- grip_query: 문자열. 마우스 형태/그립 매칭. 손목·팔목 통증 완화, 인체공학, 장시간 편안함이
  필요한 효과면 "에르고"(수직형/버티컬 포함). 특정 그립 방식이면 "팜"/"클로"/"핑거".
  손목 관련 효과는 무게 숫자를 지어내기보다 이 형태 카테고리("에르고")로 매핑하라.
- color_query: 문자열 (색상. 예: "블랙", "화이트")
- size_pref: "large" 또는 "small" (마우스 크기 선호. 손이 크다/그립에 꽉 차게/'할머니가 손에 꽉 차게 큰'→"large", 손이 작다/미니/휴대성→"small". 절대 치수가 아니라 둘 중 하나만 출력)"""


def _llm_based_map(phrase: str) -> dict[str, Any]:
    """룰이 못 잡은 표현을 LLM으로 변환. 출력은 화이트리스트로 검증."""
    llm = _get_llm()
    if llm is None:
        return {}

    prompt = (
        "다음 사용자 표현을 PC 마우스 검색 스펙으로 변환하라.\n"
        "사용자는 보통 기능 이름이 아니라 '효과'로 말한다(예: '팔목이 아파'→손목 편한 에르고 형태, "
        "'애기가 자고 있어'→조용함, '오래 써도 안 피곤'→가벼움/에르고, "
        "'80대 할머니가 손에 꽉 차게'→큰 크기). "
        "표현이 암시하는 효과를 그 효과를 유발하는 기능 스펙으로 역추론하라. "
        "특히 손목·팔목·어깨·장시간 피로 같은 신체 부담 표현은 임의의 무게 숫자보다 "
        "grip_query='에르고'(인체공학 형태)로 매핑하는 것이 안전하다.\n"
        "아래 허용된 키만 사용하고, 해당하지 않으면 그 키는 생략하라.\n"
        "오직 JSON 객체만 출력하라 (설명/마크다운 금지).\n\n"
        f"[허용 키]\n{_SPEC_SCHEMA_DOC}\n\n"
        f'[사용자 표현]\n"{phrase}"\n\n'
        "[출력] JSON only:"
    )
    try:
        resp = llm.invoke(prompt)
        raw = getattr(resp, "content", str(resp))
        text = re.sub(r"```(?:json)?|```", "", str(raw)).strip()
        parsed = json.loads(text)
    except Exception as exc:
        print(f"map_language_to_specs LLM fallback skipped: {exc}")
        return {}

    if not isinstance(parsed, dict):
        return {}
    return _validate_specs(parsed)


def _normalize_spec_aliases(specs: dict[str, Any]) -> dict[str, Any]:
    """LLM이 직접 만든 spec_filters의 흔한 형식 변형을 표준 형식으로 흡수한다."""
    if not isinstance(specs, dict):
        return {}

    # 1) 키 별칭 → 표준 키
    key_aliases = {
        "weight_g": "max_weight_g",
        "weight": "max_weight_g",
        "max_weight": "max_weight_g",
        "dpi": "min_dpi",
        "max_dpi": "min_dpi",
        "polling_rate": "min_polling_rate_hz",
        "polling_rate_hz": "min_polling_rate_hz",
        "battery_hours": "min_battery_hours",
        "battery": "min_battery_hours",
        "button_count": "min_button_count",
        "buttons": "min_button_count",
        "connectivity": "connection_type",
        "connection": "connection_type",
        "grip": "grip_query",
        "grip_type": "grip_query",
        "color": "color_query",
        "size": "size_pref",
        "size_preference": "size_pref",
    }
    # 2) 값 별칭 (영어/변형 → 표준)
    conn_value_aliases = {
        "wireless": "무선", "bluetooth": "무선", "wired": "유선",
    }
    size_value_aliases = {
        "big": "large", "large": "large", "큰": "large", "넓은": "large",
        "compact": "small", "mini": "small", "small": "small",
        "작은": "small", "소형": "small",
    }

    out: dict[str, Any] = {}
    for raw_key, raw_value in specs.items():
        key = key_aliases.get(raw_key, raw_key)
        value = raw_value

        # 중첩 형식 {'max': 70} / {'min': 16000} / {'value': ...} 평탄화
        if isinstance(value, dict):
            for nk in ("max", "min", "value", "<=", ">="):
                if nk in value:
                    value = value[nk]
                    break

        # connection_type 영어값 → 한글
        if key == "connection_type" and isinstance(value, str):
            value = conn_value_aliases.get(value.lower(), value)

        # size_pref 변형 → large/small
        if key == "size_pref" and isinstance(value, str):
            value = size_value_aliases.get(value.lower(), value.lower())

        out[key] = value

    return out


def _validate_specs(specs: dict[str, Any]) -> dict[str, Any]:
    """화이트리스트 + 값 타입/도메인 검증. SQL 안전성의 마지막 방어선.

    검증 전에 _normalize_spec_aliases로 LLM의 형식 변형을 먼저 흡수한다.
    """
    specs = _normalize_spec_aliases(specs)
    clean: dict[str, Any] = {}
    for key, value in specs.items():
        if key not in ALLOWED_SPEC_KEYS or value is None:
            continue
        if key == "connection_type":
            if value in ("무선", "유선"):
                clean[key] = value
        elif key == "size_pref":
            if value in ("large", "small"):
                clean[key] = value
        elif key in {"is_gaming", "right_hand_only", "left_hand_ok",
                     "is_silent", "has_rgb", "has_multi_pairing"}:
            if value is True:
                clean[key] = True
        elif key in {"max_weight_g", "min_dpi", "min_polling_rate_hz",
                     "min_battery_hours", "min_button_count"}:
            try:
                clean[key] = int(value)
            except (TypeError, ValueError):
                continue
        elif key in {"grip_query", "color_query"}:
            if isinstance(value, str) and value.strip():
                clean[key] = value.strip()
    return clean


# ============================================================================
# 섹션 4: 도구
# ============================================================================
@tool
def map_language_to_specs(user_phrase: str) -> dict:
    """사용자의 일상 자연어 표현을 정량적인 마우스 검색 스펙으로 변환한다.

    "손목이 아파서", "조용한 거", "오래 써도 편한", "손에 꽉 차게 큰" 같은
    모호하거나 비정형적인 표현이 질의에 있을 때 먼저 호출하라. 변환된 스펙을
    search_products의 spec_filters 인자로 넘기면 정확한 검색이 가능하다.
    명확한 키워드("무선", "FPS")만 있으면 굳이 호출하지 않아도 된다.
    """
    specs = _rule_based_map(user_phrase)   # 1) 빠르고 확실한 룰 먼저
    if not specs:                          # 2) 룰이 못 잡으면 LLM 폴백
        specs = _llm_based_map(user_phrase)
    return _validate_specs(specs)


@tool
def search_products(
    query: str,
    budget_krw: int | None = None,
    spec_filters: dict | None = None,
) -> list[dict]:
    """다나와 DB에서 조건에 맞는 PC 마우스를 검색해 상위 후보를 반환한다.

    사용자가 충분한 정보를 줬을 때 호출하라. 정보가 부족하면 먼저
    ask_clarifying_question을 사용하라. 자연어 조건이 있으면 먼저
    map_language_to_specs로 변환한 결과를 spec_filters에 넣어라.
    """
    normalized = _validate_specs(spec_filters) if spec_filters else None
    products = search_danawa_products(
        query=query,
        budget_krw=budget_krw,
        spec_filters=normalized or None,
    )
    return products[:5]


@tool
def ask_clarifying_question(missing_aspect: str) -> str:
    """요구가 너무 모호해 검색이 어려울 때 사용자에게 되물을 질문을 생성한다.

    예: 용도(게임/사무/그래픽), 예산, 무선/유선 선호 등이 전혀 없을 때.
    missing_aspect에는 부족한 정보의 종류를 넣어라 (예: "use_case", "budget").
    """
    questions = {
        "use_case": "주로 어떤 용도로 사용하실 예정인가요? (게임 / 사무 / 그래픽 작업 등)",
        "budget": "생각하시는 예산대가 있으실까요?",
        "connection": "무선과 유선 중 선호하시는 방식이 있나요?",
        "preference": "특별히 중요하게 생각하시는 점이 있나요? (무게, 조용함, 버튼 수 등)",
    }
    return questions.get(
        missing_aspect,
        "원하시는 조건을 조금 더 구체적으로 알려주시면 정확히 추천드릴 수 있어요.",
    )


# 비교 시 사용할 기본 비교 축과, 사람이 말하는 우선순위 → 컬럼 매핑
_COMPARE_AXES = ["price", "weight_g", "length_mm", "max_dpi",
                 "max_polling_rate", "battery_max_hours", "button_count",
                 "connectivity", "is_silent"]
_PRIORITY_COLS = {
    "price": "price", "가격": "price", "저렴": "price", "cheap": "price",
    "weight": "weight_g", "무게": "weight_g", "가벼": "weight_g", "light": "weight_g",
    "battery": "battery_max_hours", "배터리": "battery_max_hours",
    "dpi": "max_dpi", "감도": "max_dpi",
    "polling": "max_polling_rate", "반응": "max_polling_rate",
    "button": "min_button_count", "버튼": "button_count",
    "size": "length_mm", "크기": "length_mm",
}
# 작을수록 좋은 축(낮은 값 우선)
_LOWER_IS_BETTER = {"price", "weight_g"}


@tool
def retrieve_product_details(product_ids: list[str]) -> list[dict]:
    """비교/검토할 제품 id들의 상세 스펙을 다나와 DB에서 직접 조회한다.

    비교 대상의 정확한 스펙이 필요할 때 호출하라. 반환값(실제 DB 값)만
    근거로 삼고, 여기에 없는 수치는 절대 지어내지 마라.
    """
    return get_product_details(product_ids)


@tool
def compare_products(product_ids: list[str], criteria: list[str] | None = None) -> dict:
    """제품들의 실제 스펙을 DB에서 가져와 기준별로 정리한 비교 데이터를 만든다.

    사용자가 "둘 중 뭐가 나아", "비교해줘" 등 비교를 요청할 때 호출하라.
    product_ids는 비교 대상 제품 id 목록이다(앞선 검색 결과의 product_id).
    """
    details = get_product_details(product_ids)
    if not details:
        return {
            "table": [],
            "criteria": criteria or _COMPARE_AXES,
            "note": "해당 id의 제품을 DB에서 찾지 못했습니다. 스펙을 지어내지 말고 "
                    "사용자에게 대상을 다시 확인하세요.",
        }

    axes = criteria or _COMPARE_AXES
    table = []
    for d in details:
        row = {
            "product_id": d.get("product_id"),
            "name": d.get("product_name"),
            "brand": d.get("brand"),
        }
        for ax in axes:
            row[ax] = d.get(ax)
        table.append(row)

    return {
        "criteria": axes,
        "table": table,
        "note": "위 표의 실제 값만 근거로, 각 차이를 사용자에게 주는 '효과'로 풀어 "
                "설명하라. 표에 없는(None) 값은 '정보 없음'으로 두고 지어내지 마라.",
    }


@tool
def prioritize_products(product_ids: list[str], priority: str) -> dict:
    """주어진 우선순위 기준으로 제품을 정렬한다.

    priority 예: "price"(가격), "weight"(무게), "battery"(배터리), "dpi" 등.
    가격·무게는 낮을수록, 그 외는 높을수록 우선한다.
    """
    details = get_product_details(product_ids)
    col = _PRIORITY_COLS.get(priority.lower().strip(), "price")
    reverse = col not in _LOWER_IS_BETTER

    rankable = [d for d in details if d.get(col) is not None]
    try:
        ranked = sorted(rankable, key=lambda d: float(d[col]), reverse=reverse)
    except (TypeError, ValueError):
        ranked = rankable

    return {
        "priority": col,
        "order": "낮은 값 우선" if not reverse else "높은 값 우선",
        "ranked": [
            {"product_id": d.get("product_id"), "name": d.get("product_name"), col: d.get(col)}
            for d in ranked
        ],
        "note": "이 정렬 순서를 근거로, 왜 이 순위인지 효과 언어로 설명하라.",
    }


@tool
def compare_products_search(query: str, spec_filters: dict | None = None) -> list[dict]:
    """비교 대상 후보를 새로 찾아야 할 때 검색한다(search_products와 동일).

    대화 맥락에 비교할 제품이 없으면 먼저 이걸로 후보를 찾은 뒤
    compare_products로 비교하라.
    """
    normalized = _validate_specs(spec_filters) if spec_filters else None
    products = search_danawa_products(query=query, spec_filters=normalized or None)
    return products[:6]


# 검색 에이전트 / 비교 에이전트 도구 집합
SEARCH_TOOLS = [map_language_to_specs, search_products, ask_clarifying_question, compare_products]
COMPARISON_TOOLS = [compare_products_search, retrieve_product_details, compare_products, prioritize_products]

# 도구 디스패치는 이름 기준 — 두 에이전트 도구를 모두 등록(없는 도구는 호출 안 됨)
_ALL_TOOLS = [
    map_language_to_specs, search_products, ask_clarifying_question,
    compare_products, retrieve_product_details, prioritize_products,
    compare_products_search,
]
_TOOLS_BY_NAME = {t.name: t for t in _ALL_TOOLS}

# 하위호환: 기존에 TOOLS를 참조하던 코드가 있으면 검색 도구를 가리키게 둔다.
TOOLS = SEARCH_TOOLS


# ============================================================================
# 섹션 5: 시스템 프롬프트
# ============================================================================
SYSTEM_PROMPT = """당신은 다나와 기반 PC 마우스 쇼핑 어시스턴트입니다. 한국어로 답하세요.

[행동 원칙]
1. 사용자 요구가 모호하면(용도·예산·선호 전무) ask_clarifying_question으로 되물으세요.
2. "손목 아픔", "조용한", "손에 꽉 차게 큰" 같은 자연어 조건은 map_language_to_specs로
   정량 스펙으로 바꾸세요.
3. 조건이 충분하면 search_products로 검색하세요. 변환한 스펙은 spec_filters에 넣으세요.
   spec_filters는 직접 지어내지 말고, 가능하면 map_language_to_specs가 반환한 값을
   그대로 사용하세요. (키는 max_weight_g, min_dpi, connection_type='무선'/'유선',
   size_pref='large'/'small' 등 정해진 형식만 쓰며, 중첩 객체나 영어 값은 쓰지 마세요.)
4. 검색 결과만 근거로 추천하세요. DB에 없는 제품을 지어내지 마세요.
5. 조건에 맞는 제품이 없으면 솔직히 없다고 말하세요(정직한 거절이 거짓 추천보다 낫습니다).
6. 도구는 꼭 필요할 때만 호출하고, 충분한 정보를 얻으면 최종 추천을 작성하세요.

[스펙 변환 규칙 — 반드시 지킬 것]
- 자연어·효과 표현("손목 아픔", "오래 써도 편한", "조용한", "어깨 결림" 등)이 있으면
  spec_filters를 직접 만들지 말고, 반드시 map_language_to_specs를 먼저 호출해
  그 반환값을 그대로 search_products의 spec_filters에 넣으세요.
- "오래 써도 편한", "장시간 사용", "오래 사용해도" 같은 표현은 절대 배터리(min_battery_hours)로
  해석하지 마세요. 이는 신체 피로·편안함을 뜻하므로 인체공학(grip_query='에르고')에 해당합니다.
  min_battery_hours는 사용자가 "배터리"라는 단어를 명시했을 때만 사용하세요.
- 확신이 없으면 스펙을 추가하지 말고 비워 두세요(과도한 조건은 결과를 0개로 만듭니다).

[추천 설명 원칙 — 가장 중요]
기능(스펙)을 그대로 나열하지 말고, 그 기능이 사용자에게 주는 '효과'로 풀어 설명하세요.
사람은 기능이 아니라 효과를 기준으로 제품을 고릅니다.
- 나쁜 예: "58g, 1000Hz 폴링레이트, 옵티컬 센서"
- 좋은 예: "58g으로 가벼워 장시간 써도 손목 부담이 적고, 반응 속도가 빨라 빠른 조작에 유리합니다"
사용자가 말한 요구(예: 손목 통증, 조용한 환경, 손에 꽉 차는 크기)와 각 제품의 스펙을
직접 연결해, 왜 이 제품이 그 요구를 해결하는지 효과 중심으로 설명하세요.

최종 추천은 상위 2~3개를 골라, 각 제품의 가격과 함께 '어떤 효과로 사용자의 요구를
충족하는지'를 중심으로 제시하세요."""


COMPARISON_SYSTEM_PROMPT = """당신은 다나와 기반 PC 마우스 비교 어시스턴트입니다. 한국어로 답하세요.
사용자가 여러 제품을 견주거나 그중 무엇이 더 나은지 물을 때 동작합니다.

[행동 원칙]
1. 비교 대상이 무엇인지 먼저 정하세요. 직전 대화에서 언급·추천된 제품이 있으면 그것을
   대상으로 삼고, 새로 찾아야 하면 compare_products_search로 후보를 검색하세요.
2. 비교/정렬은 반드시 compare_products(또는 retrieve_product_details)로 DB의 실제 스펙을
   가져와서 하세요. 스펙을 기억이나 추측으로 지어내지 마세요. DB에 없으면 없다고 하세요.
3. 우선순위 기준(가격·무게·배터리 등)이 분명하면 prioritize_products로 정렬하세요.
4. 도구가 돌려준 실제 값만 근거로 삼으세요(정직한 비교가 그럴듯한 거짓보다 낫습니다).
5. 도구는 꼭 필요할 때만 호출하고, 근거가 모이면 최종 비교 결론을 작성하세요.

[설명 원칙 — 가장 중요]
스펙 숫자를 나열만 하지 말고, 각 차이가 사용자에게 주는 '효과'로 풀어 설명하세요.
- 나쁜 예: "A는 58g, B는 74g"
- 좋은 예: "A가 16g 더 가벼워 장시간 사용 시 손목 부담이 더 적습니다"
최종적으로 어떤 제품이 어떤 사용자에게 왜 더 나은지 효과 중심으로 결론지으세요.
표가 필요하면 도구가 돌려준 실제 값으로만 작성하세요."""


# ============================================================================
# 섹션 6: ReAct 노드 — reason / tools / should_continue
# ============================================================================
def reason(state: ReactAgentState) -> dict[str, Any]:
    """검색 에이전트 추론 노드 (기존 동작 유지)."""
    messages = state["messages"]
    if not any(isinstance(m, SystemMessage) for m in messages):
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + list(messages)

    llm = _get_llm()
    if llm is None:
        return {
            "messages": [AIMessage(content=_fallback_text(state))],
            "iteration": state.get("iteration", 0) + 1,
        }

    llm_with_tools = llm.bind_tools(SEARCH_TOOLS)
    try:
        response = llm_with_tools.invoke(messages)
    except Exception as exc:
        print(f"reason node LLM fallback: {exc}")
        response = AIMessage(content=_fallback_text(state))

    return {"messages": [response], "iteration": state.get("iteration", 0) + 1}


def reason_compare(state: ReactAgentState) -> dict[str, Any]:
    """비교 에이전트 추론 노드 (비교 프롬프트 + 비교 도구 바인딩)."""
    messages = state["messages"]
    if not any(isinstance(m, SystemMessage) for m in messages):
        messages = [SystemMessage(content=COMPARISON_SYSTEM_PROMPT)] + list(messages)

    llm = _get_llm()
    if llm is None:
        return {
            "messages": [AIMessage(content=_fallback_text(state))],
            "iteration": state.get("iteration", 0) + 1,
        }

    llm_with_tools = llm.bind_tools(COMPARISON_TOOLS)
    try:
        response = llm_with_tools.invoke(messages)
    except Exception as exc:
        print(f"reason_compare node LLM fallback: {exc}")
        response = AIMessage(content=_fallback_text(state))

    return {"messages": [response], "iteration": state.get("iteration", 0) + 1}


def tools_node(state: ReactAgentState) -> dict[str, Any]:
    """도구를 실행하고, 제품 리스트 결과는 last_products에 보존한다."""
    last_msg = state["messages"][-1]
    tool_messages: list[ToolMessage] = []
    captured: list[Product] = list(state.get("last_products", []))

    for call in getattr(last_msg, "tool_calls", []) or []:
        name = call["name"]
        args = call.get("args", {}) or {}
        tool_fn = _TOOLS_BY_NAME.get(name)
        if tool_fn is None:
            result: Any = f"알 수 없는 도구: {name}"
        else:
            try:
                result = tool_fn.invoke(args)
            except Exception as exc:
                result = f"도구 실행 오류({name}): {exc}"

        # 검색류 도구가 제품 리스트를 돌려주면 최종 products로 캡처
        if name in ("search_products", "compare_products_search") and isinstance(result, list):
            captured = result

        tool_messages.append(
            ToolMessage(
                content=json.dumps(result, ensure_ascii=False),
                tool_call_id=call["id"],
            )
        )

    return {"messages": tool_messages, "last_products": captured}


def should_continue(state: ReactAgentState) -> str:
    """다음 단계 결정: 도구 호출이 있고 반복 한도 내면 tools, 아니면 end."""
    if state.get("iteration", 0) >= MAX_ITERATIONS:
        return "end"
    last_msg = state["messages"][-1]
    if getattr(last_msg, "tool_calls", None):
        return "tools"
    return "end"


# ============================================================================
# 섹션 7: 폴백 (LLM 불가 시 검색 결과를 텍스트로)
# ============================================================================
def _fallback_text(state: ReactAgentState) -> str:
    products = state.get("last_products", [])
    if not products:
        return (
            "현재 추천 엔진(LLM)에 연결할 수 없어 정확한 추천을 드리기 어려워요. "
            "잠시 후 다시 시도해 주세요."
        )
    lines = ["조건에 맞는 후보입니다."]
    for i, p in enumerate(products, 1):
        price = p.get("price")
        price_text = f"{price:,}원" if isinstance(price, int) else "가격 정보 없음"
        lines.append(f"{i}. {p.get('name')} - {price_text}: {p.get('reason')}")
    return "\n".join(lines)


# ============================================================================
# 섹션 8: Hybrid Router (Rule + LLM 의도 분류)
# ============================================================================
_COMPARE_KEYWORDS = (
    "비교", "vs", " vs ", "둘 중", "셋 중", "그중", "어느 게", "어느게",
    "뭐가 나아", "뭐가 더", "뭐가 좋", "차이가", "차이점", "compare",
)


def _classify_intent(query: str, conversation_messages: list[dict[str, str]] | None = None) -> str:
    """질의 의도를 'search' 또는 'compare'로 분류한다(Rule + LLM 폴백).

    명시적 비교 신호가 있으면 룰로 결정. 애매하면 LLM에 한 번 물어보되,
    LLM 불가 시 안전하게 'search'(검증된 경로)로 떨어진다.
    """
    t = (query or "").lower()
    if any(k in t for k in _COMPARE_KEYWORDS):
        return "compare"

    llm = _get_llm()
    if llm is None:
        return "search"
    try:
        resp = llm.invoke(
            "다음 사용자 메시지의 의도를 분류하라. 이미 언급된 여러 제품을 견주거나 "
            "그중 무엇이 나은지 고르는 '비교'면 compare, 새 제품을 찾는 거면 search. "
            "오직 한 단어(compare 또는 search)만 출력하라.\n\n"
            f'메시지: "{query}"'
        )
        label = re.sub(r"[^a-z]", "", str(getattr(resp, "content", "")).lower())
        return "compare" if "compare" in label else "search"
    except Exception as exc:
        print(f"intent classify fallback (→search): {exc}")
        return "search"


# ============================================================================
# 섹션 9: 그래프 빌드 (검색 / 비교 두 그래프)
# ============================================================================
_graph = None
_compare_graph = None


def get_agent():
    """Spec Matching Agent (검색). 기존과 동일."""
    global _graph
    if _graph is not None:
        return _graph

    graph = StateGraph(ReactAgentState)
    graph.add_node("reason", reason)
    graph.add_node("tools", tools_node)

    graph.add_edge(START, "reason")
    graph.add_conditional_edges("reason", should_continue, {"tools": "tools", "end": END})
    graph.add_edge("tools", "reason")

    _graph = graph.compile()
    return _graph


def get_comparison_agent():
    """Comparison Agent (비교). 검색 그래프와 동일 골격, 비교 노드/도구."""
    global _compare_graph
    if _compare_graph is not None:
        return _compare_graph

    graph = StateGraph(ReactAgentState)
    graph.add_node("reason", reason_compare)
    graph.add_node("tools", tools_node)

    graph.add_edge(START, "reason")
    graph.add_conditional_edges("reason", should_continue, {"tools": "tools", "end": END})
    graph.add_edge("tools", "reason")

    _compare_graph = graph.compile()
    return _compare_graph


# ============================================================================
# 섹션 10: 외부 진입점 (인터페이스 유지 — routers/search.py 무변경)
# ============================================================================
def _to_messages(conversation_messages: list[dict[str, str]] | None, query: str) -> list[BaseMessage]:
    messages: list[BaseMessage] = []
    for m in conversation_messages or []:
        role = m.get("role")
        content = str(m.get("content") or "")
        if not content:
            continue
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role in ("assistant", "ai"):
            messages.append(AIMessage(content=content))
    messages.append(HumanMessage(content=query))
    return messages


def run_shopping_agent(
    query: str,
    conversation_messages: list[dict[str, str]] | None = None,
) -> AgentResult:
    """기존과 동일한 시그니처/반환. 내부에서 Hybrid Router로 에이전트를 고른다."""
    intent = _classify_intent(query, conversation_messages)
    graph = get_comparison_agent() if intent == "compare" else get_agent()

    result: dict[str, Any] = graph.invoke(
        {
            "messages": _to_messages(conversation_messages, query),
            "iteration": 0,
            "last_products": [],
        }
    )

    # 최종 recommendation = 마지막 AIMessage(텍스트) 내용
    recommendation = ""
    for msg in reversed(result.get("messages", [])):
        if isinstance(msg, AIMessage) and not getattr(msg, "tool_calls", None):
            recommendation = str(getattr(msg, "content", "") or "")
            if recommendation:
                break

    return AgentResult(
        recommendation=recommendation or _fallback_text(result),
        products=result.get("last_products", []),
    )