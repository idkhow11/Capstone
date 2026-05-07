import sys
import os

# Ensure the backend directory is in the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.agent import run_shopping_agent

def main():
    print("Initializing agent...")
    print("Agent initialized. Invoking...")
    try:
        result = run_shopping_agent("가성비 무선 마우스 추천")
        print(result.recommendation)
        print(result.products)
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
