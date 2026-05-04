import os
from typing import Literal
from tavily import TavilyClient
from deepagents import create_deep_agent
from dotenv import load_dotenv

load_dotenv(override=True)

# We expect these to be set in the environment or .env
tavily_api_key = os.getenv("TAVILY_API_KEY", "")
tavily_client = None

if tavily_api_key and tavily_api_key != "your_tavily_api_key":
    tavily_client = TavilyClient(api_key=tavily_api_key)

def internet_search(
    query: str,
    max_results: int = 5,
    topic: Literal["general", "news", "finance"] = "general",
    include_raw_content: bool = False,
):
    """Run a web search"""
    if not tavily_client:
        return "Search is currently unavailable because TAVILY_API_KEY is not set."
    
    return tavily_client.search(
        query,
        max_results=max_results,
        include_raw_content=include_raw_content,
        topic=topic,
    )

research_instructions = """You are a specialized Korean Shopping Assistant ("쇼핑 도우미"). 
Your job is to help the user find the best products (especially groceries and food items) based on their natural language queries.

You have access to an internet search tool to find current product information, prices, and recommendations from platforms like Danawa or general Korean web.

## `internet_search`

Use this to run an internet search for a given query. You can specify the max number of results to return.
Always try to find actual products and reasonable price estimates. Provide your final response in Korean.
"""

_agent = None

def get_agent():
    global _agent
    if _agent is not None:
        return _agent
    
    # Model string format for Gemini
    model_string = "google_genai:gemini-2.0-flash"
    
    # Check if API key is properly set
    api_key = os.getenv("GOOGLE_API_KEY", "")
    if not api_key or api_key == "your_google_api_key":
        print("WARNING: GOOGLE_API_KEY is not set. The agent will fail if called.")
        
    _agent = create_deep_agent(
        model=model_string,
        tools=[internet_search],
        system_prompt=research_instructions,
    )
    return _agent

