import os
import re
from dataclasses import dataclass
from typing import Any, TypedDict

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, START, StateGraph

from services.danawa_rag import search_danawa_products

load_dotenv(override=True)


class Product(TypedDict, total=False):
    product_id: str
    name: str
    brand: str
    price: int | None
    url: str
    thumbnail: str
    reason: str
    score: float


class QueryAnalysis(TypedDict, total=False):
    category: str | None
    budget_krw: int | None
    intent: str
    constraints: list[str]
    ranking_priorities: list[str]


class AgentState(TypedDict, total=False):
    query: str
    conversation_messages: list[dict[str, str]]
    analysis: QueryAnalysis
    candidates: list[Product]
    products: list[Product]
    recommendation: str


@dataclass(frozen=True)
class AgentResult:
    recommendation: str
    products: list[Product]


SHOPPING_SYSTEM_PROMPT = """You are a Korean shopping assistant for Danawa product search.
Answer in Korean. Use only the product candidates supplied in the prompt.
Prioritize concrete recommendations, price/value tradeoffs, and concise buying reasons.
If product data is insufficient, say so clearly instead of inventing products."""


_graph = None
_llm = None
_llm_unavailable = False


def _extract_budget_krw(query: str) -> int | None:
    match = re.search(r"(\d+(?:\.\d+)?)\s*만\s*원", query)
    if match:
        return int(float(match.group(1)) * 10000)

    match = re.search(r"(\d{2,})\s*원", query)
    if match:
        return int(match.group(1))

    return None


def _infer_category(query: str) -> str | None:
    category_keywords = [
        "노트북",
        "마우스",
        "키보드",
        "모니터",
        "이어폰",
        "헤드폰",
        "스피커",
        "냉장고",
        "세탁기",
        "청소기",
        "공기청정기",
        "그래픽카드",
        "cpu",
        "ssd",
        "ram",
        "메모리",
    ]
    lowered_query = query.lower()
    for keyword in category_keywords:
        if keyword.lower() in lowered_query:
            return keyword
    return None


def _infer_priorities(query: str) -> list[str]:
    priorities: list[str] = []
    priority_map = {
        "가성비": "가성비",
        "저렴": "낮은 가격",
        "싼": "낮은 가격",
        "성능": "성능",
        "고성능": "성능",
        "휴대": "휴대성",
        "가벼": "휴대성",
        "게임": "게이밍 성능",
        "게이밍": "게이밍 성능",
        "조용": "저소음",
        "무소음": "저소음",
        "후기": "사용자 후기",
        "리뷰": "사용자 후기",
    }
    for keyword, priority in priority_map.items():
        if keyword in query and priority not in priorities:
            priorities.append(priority)
    return priorities or ["가격 대비 만족도"]


def _infer_constraints(query: str) -> list[str]:
    constraints = []
    constraint_keywords = [
        "무선",
        "유선",
        "유선+무선",
        "저소음",
        "무소음",
        "게이밍",
        "게임",
        "fps",
        "가벼운",
        "가벼",
        "초경량",
        "오른손",
        "왼손",
        "충전식",
        "AA",
        "블루투스",
        "고감도",
        "dpi",
        "폴링",
    ]
    for keyword in constraint_keywords:
        if keyword.lower() in query.lower() and keyword not in constraints:
            constraints.append(keyword)
    return constraints


def analyze_query(state: AgentState) -> dict[str, QueryAnalysis]:
    query = state["query"]
    analysis: QueryAnalysis = {
        "category": _infer_category(query),
        "budget_krw": _extract_budget_krw(query),
        "intent": "product_recommendation",
        "constraints": _infer_constraints(query),
        "ranking_priorities": _infer_priorities(query),
    }
    return {"analysis": analysis}


def retrieve_danawa_products(query: str, analysis: QueryAnalysis) -> list[Product]:
    """Retrieve grounded product candidates from the Danawa RAG corpus."""
    return search_danawa_products(
        query=query,
        category=analysis.get("category"),
        budget_krw=analysis.get("budget_krw"),
        constraints=analysis.get("constraints"),
        ranking_priorities=analysis.get("ranking_priorities"),
    )


def retrieve_products(state: AgentState) -> dict[str, list[Product]]:
    return {
        "candidates": retrieve_danawa_products(
            query=state["query"],
            analysis=state.get("analysis", {}),
        )
    }


def _normalize_product(product: Product, analysis: QueryAnalysis) -> Product:
    normalized: Product = {
        "product_id": str(product.get("product_id") or ""),
        "name": str(product.get("name") or "상품명 미상"),
        "brand": str(product.get("brand") or ""),
        "price": product.get("price"),
        "url": str(product.get("url") or ""),
        "thumbnail": str(product.get("thumbnail") or ""),
        "reason": str(product.get("reason") or ""),
        "score": float(product.get("score") or 0),
    }

    if not normalized["reason"]:
        priorities = ", ".join(analysis.get("ranking_priorities", []))
        normalized["reason"] = f"{priorities} 기준으로 후보에 포함"

    return normalized


def rank_products(state: AgentState) -> dict[str, list[Product]]:
    analysis = state.get("analysis", {})
    budget = analysis.get("budget_krw")
    products = [_normalize_product(product, analysis) for product in state.get("candidates", [])]

    if budget:
        products = [
            product
            for product in products
            if product.get("price") is None or product.get("price", 0) <= budget
        ]

    products.sort(
        key=lambda product: (
            float(product.get("score") or 0),
            -(product.get("price") or 10**12),
        ),
        reverse=True,
    )
    return {"products": products[:5]}


def _get_llm():
    global _llm
    if _llm_unavailable:
        return None

    if _llm is not None:
        return _llm

    api_key = os.getenv("GOOGLE_API_KEY", "")
    if not api_key or api_key == "your_google_api_key":
        return None

    model_name = os.getenv("SHOPPING_AGENT_MODEL", "gemini-2.5-flash")
    _llm = ChatGoogleGenerativeAI(
        model=model_name,
        temperature=0.2,
        retries=0,
        request_timeout=30,
    )
    return _llm


def _format_products(products: list[Product]) -> str:
    lines = []
    for index, product in enumerate(products, start=1):
        price = product.get("price")
        price_text = f"{price:,}원" if isinstance(price, int) else "가격 정보 없음"
        reason = str(product.get("reason") or "")
        if len(reason) > 180:
            reason = reason[:177] + "..."
        lines.append(
            f"{index}. {product.get('name')} | {price_text} | "
            f"reason: {reason}"
        )
    return "\n".join(lines)


def _format_conversation_messages(messages: list[dict[str, str]], limit: int = 10) -> str:
    formatted_messages = []
    for message in messages[-limit:]:
        role = "User" if message.get("role") == "user" else "Assistant"
        content = str(message.get("content") or "").strip()
        if not content:
            continue
        if len(content) > 600:
            content = content[:597] + "..."
        formatted_messages.append(f"{role}: {content}")
    return "\n".join(formatted_messages)


def _fallback_recommendation(query: str, products: list[Product]) -> str:
    if not products:
        return (
            "현재 Danawa DB 검색 인덱스가 연결되어 있지 않아 실제 상품 후보를 찾지 못했어요.\n"
            f"요청하신 조건: {query}\n\n"
            "다음 단계에서 Danawa 상품 테이블과 임베딩 검색을 연결하면, 예산과 용도에 맞는 "
            "실제 상품명, 가격, 구매 링크를 기준으로 추천할 수 있습니다."
        )

    lines = ["Danawa DB 후보 기준 추천입니다."]
    for index, product in enumerate(products, start=1):
        price = product.get("price")
        price_text = f"{price:,}원" if isinstance(price, int) else "가격 정보 없음"
        lines.append(f"{index}. {product.get('name')} - {price_text}: {product.get('reason')}")
    return "\n".join(lines)


def generate_answer(state: AgentState) -> dict[str, str]:
    global _llm_unavailable

    query = state["query"]
    products = state.get("products", [])
    conversation_context = _format_conversation_messages(
        state.get("conversation_messages", [])
    )
    if not products:
        return {"recommendation": _fallback_recommendation(query, products)}

    llm = _get_llm()
    if llm is None:
        return {"recommendation": _fallback_recommendation(query, products)}

    context_block = (
        f"Recent conversation context:\n{conversation_context}\n\n"
        if conversation_context
        else ""
    )
    prompt = (
        f"{SHOPPING_SYSTEM_PROMPT}\n\n"
        f"{context_block}"
        f"User query:\n{query}\n\n"
        f"Product candidates:\n{_format_products(products)}\n\n"
        "Use the recent conversation only to resolve follow-up references. "
        "Return a concise Korean recommendation with the best 2-3 picks and why."
    )
    try:
        response = llm.invoke(prompt)
    except Exception as exc:
        print(f"Shopping agent LLM fallback: {exc}")
        _llm_unavailable = True
        return {"recommendation": _fallback_recommendation(query, products)}

    content = getattr(response, "content", str(response))
    return {"recommendation": str(content)}


def get_agent():
    global _graph
    if _graph is not None:
        return _graph

    graph = StateGraph(AgentState)
    graph.add_node("analyze_query", analyze_query)
    graph.add_node("retrieve_products", retrieve_products)
    graph.add_node("rank_products", rank_products)
    graph.add_node("generate_answer", generate_answer)

    graph.add_edge(START, "analyze_query")
    graph.add_edge("analyze_query", "retrieve_products")
    graph.add_edge("retrieve_products", "rank_products")
    graph.add_edge("rank_products", "generate_answer")
    graph.add_edge("generate_answer", END)

    _graph = graph.compile()
    return _graph


def run_shopping_agent(
    query: str,
    conversation_messages: list[dict[str, str]] | None = None,
) -> AgentResult:
    graph = get_agent()
    result: dict[str, Any] = graph.invoke(
        {
            "query": query,
            "conversation_messages": conversation_messages or [],
        }
    )
    return AgentResult(
        recommendation=result.get("recommendation", ""),
        products=result.get("products", []),
    )
