import sys
import os

# Ensure the backend directory is in the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.agent import get_agent

def main():
    print("Initializing agent...")
    agent = get_agent()
    print("Agent initialized. Invoking...")
    try:
        result = agent.invoke({"messages": [{"role": "user", "content": "hello"}]})
        print(result["messages"][-1].content)
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
