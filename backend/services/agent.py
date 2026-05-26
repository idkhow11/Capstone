"""모두모아 쇼핑 어시스턴트 에이전트 (ReAct 패턴).

이 파일은 기존 결정론적 파이프라인(analyze→retrieve→rank→generate)을
수동 StateGraph ReAct 루프(reason ⇄ tools, 최대 5회)로 교체한 버전이다.

[외부 인터페이스 — 변경 없음 / DO NOT CHANGE]
  - run_shopping_agent(query, conversation_messages) -> AgentResult
  - AgentResult(recommendation, products)
  routers/search.py 와 schemas.py 는 이 인터페이스에만 의존하므로 손대지 않는다.

[내부 구조 — ReAct]
  reason(LLM이 도구 선택/응답 판단) ⇄ tools(도구 실행), should_continue 분기.

[도구 4종]
  1. search_products         : 다나와 DB 검색 (danawa_rag 재활용)
  2. map_language_to_specs   : 자연어 → 정량 스펙 (룰 + LLM 폴백 + 14키 검증)
  3. ask_clarifying_question : 모호한 요구 명확화 (대화형 핵심)
  4. compare_products        : 제품 비교
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

from services.danawa_rag import search_danawa_products

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
#   기존 코드의 "LLM 죽어도 서비스 안 죽음" 정신은 유지하되,
#   "한 번 실패하면 영구 비활성화"는 완화 (요청 단위로만 폴백).
# ============================================================================
_llm = None


def _get_llm() -> ChatOpenAI | None:
    global _llm
    if _llm is not None:
        return _llm
    # 전북대 멀티 LLM 게이트웨이(OpenAI 호환)를 통해 호출한다.
    # 키는 GATEWAY_API_KEY 우선, 없으면 기존 GOOGLE_API_KEY도 허용(하위 호환).
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
# 섹션 3: 룰 기반 매핑 자산 (기존 danawa_rag._resolve_structured_filters에서
#   흩어져 있던 매핑을 도구용으로 응집. 14키 화이트리스트 기준.)
# ============================================================================
# SQL params가 기대하는 14개 키. 이 밖의 키는 검색 필터로 못 흘러간다.
ALLOWED_SPEC_KEYS = {
    "connection_type", "is_gaming", "max_weight_g", "right_hand_only",
    "left_hand_ok", "min_dpi", "min_polling_rate_hz", "min_battery_hours",
    "is_silent", "has_rgb", "has_multi_pairing", "min_button_count",
    "grip_query", "color_query",
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
    if "배터리" in t or "오래" in t:
        specs["min_battery_hours"] = 80
    if "무소음" in t or "저소음" in t or "조용" in t:
        specs["is_silent"] = True
    if "rgb" in t or "조명" in t or "led" in t:
        specs["has_rgb"] = True
    if "멀티페어링" in t or "멀티 페어링" in t:
        specs["has_multi_pairing"] = True
    if "버튼" in t or "매크로" in t:
        specs["min_button_count"] = 6
    if "팜그립" in t or "팜 그립" in t:
        specs["grip_query"] = "팜"
    if "블랙" in t or "검정" in t:
        specs["color_query"] = "블랙"
    elif "화이트" in t or "흰색" in t:
        specs["color_query"] = "화이트"

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
- grip_query: 문자열 (그립 방식. 예: "팜")
- color_query: 문자열 (색상. 예: "블랙", "화이트")"""


def _llm_based_map(phrase: str) -> dict[str, Any]:
    """룰이 못 잡은 표현을 LLM으로 변환. 출력은 14키 화이트리스트로 검증."""
    llm = _get_llm()
    if llm is None:
        return {}

    prompt = (
        "다음 사용자 표현을 PC 마우스 검색 스펙으로 변환하라.\n"
        "사용자는 보통 기능 이름이 아니라 '효과'로 말한다(예: '팔목이 아파'→가벼움/편함, "
        "'애기가 자고 있어'→조용함, '오래 써도 안 피곤'→가벼움/저소음). "
        "표현이 암시하는 효과를 그 효과를 유발하는 기능 스펙으로 역추론하라.\n"
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
    """LLM이 직접 만든 spec_filters의 흔한 형식 변형을 표준 형식으로 흡수한다.

    LLM이 map_language_to_specs를 거치지 않고 search_products의 spec_filters를
    직접 만들면, 영어 값('wireless')·키 별칭('weight_g')·중첩 형식({'max':70})을
    쓰는 경우가 있다. 이를 우리 14키 표준 형식으로 되돌린다.
    """
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
    }
    # 2) 값 별칭 (영어 → 한글)
    conn_value_aliases = {
        "wireless": "무선", "bluetooth": "무선", "wired": "유선",
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

        out[key] = value

    return out


def _validate_specs(specs: dict[str, Any]) -> dict[str, Any]:
    """14키 화이트리스트 + 값 타입/도메인 검증. SQL 안전성의 마지막 방어선.

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
# 섹션 4: 도구 4종
# ============================================================================
@tool
def map_language_to_specs(user_phrase: str) -> dict:
    """사용자의 일상 자연어 표현을 정량적인 마우스 검색 스펙으로 변환한다.

    "손목이 아파서", "조용한 거", "오래 써도 편한" 같은 모호하거나 비정형적인
    표현이 질의에 있을 때 먼저 호출하라. 변환된 스펙을 search_products의
    spec_filters 인자로 넘기면 정확한 검색이 가능하다.
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
    # 방어선: spec_filters를 직접 만들었더라도(영어값/중첩/키별칭 등)
    # 표준 14키 형식으로 정규화·검증한 뒤 검색에 넘긴다.
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


@tool
def compare_products(product_ids: list[str], criteria: list[str] | None = None) -> dict:
    """앞서 검색된 제품들을 주요 기준으로 비교 정리한다.

    사용자가 "둘 중 뭐가 나아", "비교해줘" 등 비교를 요청할 때 호출하라.
    product_ids는 비교 대상 제품 id 목록이다.
    """
    # 단일 에이전트 구현: 검색 결과를 기준 축으로 정리해 LLM이 설명하도록 넘긴다.
    return {
        "product_ids": product_ids,
        "criteria": criteria or ["price", "weight_g", "max_dpi", "battery"],
        "note": "비교 대상과 기준을 정리했으니 표 형태로 설명하라.",
    }


TOOLS = [map_language_to_specs, search_products, ask_clarifying_question, compare_products]
_TOOLS_BY_NAME = {t.name: t for t in TOOLS}


# ============================================================================
# 섹션 5: 시스템 프롬프트 (에이전트 행동의 80%를 여기서 결정)
# ============================================================================
SYSTEM_PROMPT = """당신은 다나와 기반 PC 마우스 쇼핑 어시스턴트입니다. 한국어로 답하세요.

[행동 원칙]
1. 사용자 요구가 모호하면(용도·예산·선호 전무) ask_clarifying_question으로 되물으세요.
2. "손목 아픔", "조용한" 같은 자연어 조건은 map_language_to_specs로 정량 스펙으로 바꾸세요.
3. 조건이 충분하면 search_products로 검색하세요. 변환한 스펙은 spec_filters에 넣으세요.
   spec_filters는 직접 지어내지 말고, 가능하면 map_language_to_specs가 반환한 값을
   그대로 사용하세요. (키는 max_weight_g, min_dpi, connection_type='무선'/'유선' 등
   정해진 형식만 쓰며, 중첩 객체나 영어 값은 쓰지 마세요.)
4. 검색 결과만 근거로 추천하세요. DB에 없는 제품을 지어내지 마세요.
5. 조건에 맞는 제품이 없으면 솔직히 없다고 말하세요(정직한 거절이 거짓 추천보다 낫습니다).
6. 도구는 꼭 필요할 때만 호출하고, 충분한 정보를 얻으면 최종 추천을 작성하세요.

[추천 설명 원칙 — 가장 중요]
기능(스펙)을 그대로 나열하지 말고, 그 기능이 사용자에게 주는 '효과'로 풀어 설명하세요.
사람은 기능이 아니라 효과를 기준으로 제품을 고릅니다.
- 나쁜 예: "58g, 1000Hz 폴링레이트, 옵티컬 센서"
- 좋은 예: "58g으로 가벼워 장시간 써도 손목 부담이 적고, 반응 속도가 빨라 빠른 조작에 유리합니다"
사용자가 말한 요구(예: 손목 통증, 조용한 환경, 오래 사용)와 각 제품의 스펙을
직접 연결해, 왜 이 제품이 그 요구를 해결하는지 효과 중심으로 설명하세요.

최종 추천은 상위 2~3개를 골라, 각 제품의 가격과 함께 '어떤 효과로 사용자의 요구를
충족하는지'를 중심으로 제시하세요."""


# ============================================================================
# 섹션 6: ReAct 노드 — reason / tools / should_continue
# ============================================================================
def reason(state: ReactAgentState) -> dict[str, Any]:
    """LLM이 다음 행동(도구 호출 or 최종 응답)을 결정하는 추론 노드."""
    messages = state["messages"]
    if not any(isinstance(m, SystemMessage) for m in messages):
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + list(messages)

    llm = _get_llm()
    if llm is None:
        # LLM 불가 → 폴백 응답을 AIMessage로 직접 넣고 종료시킨다.
        return {
            "messages": [AIMessage(content=_fallback_text(state))],
            "iteration": state.get("iteration", 0) + 1,
        }

    llm_with_tools = llm.bind_tools(TOOLS)
    try:
        response = llm_with_tools.invoke(messages)
    except Exception as exc:
        print(f"reason node LLM fallback: {exc}")
        response = AIMessage(content=_fallback_text(state))

    return {"messages": [response], "iteration": state.get("iteration", 0) + 1}


def tools_node(state: ReactAgentState) -> dict[str, Any]:
    """도구를 실행하고, search_products 결과는 last_products에 보존한다."""
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

        if name == "search_products" and isinstance(result, list):
            captured = result  # 최종 products 반환용으로 캡처

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
# 섹션 7: 폴백 (LLM 불가 시 검색 결과를 텍스트로 — 기존 정신 유지)
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
# 섹션 8: 그래프 빌드 (reason ⇄ tools 루프)
# ============================================================================
_graph = None


def get_agent():
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


# ============================================================================
# 섹션 9: 외부 진입점 (인터페이스 유지 — routers/search.py 무변경)
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
    """기존과 동일한 시그니처/반환. 내부만 ReAct."""
    graph = get_agent()
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