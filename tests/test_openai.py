import os
import sys
from dotenv import load_dotenv

# Add src to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.openai_provider import OpenAIProvider


def test_openai():
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")

    print("--- Testing OpenAI Provider ---")
    if not api_key:
        print("❌ Error: OPENAI_API_KEY is not set in your .env file.")
        return

    try:
        provider = OpenAIProvider(api_key=api_key)

        prompt = "Explain what an AI Agent is in one sentence."
        response = provider.generate(prompt)

        print(f"User: {prompt}")
        print(f"Assistant: {response['content']}")
        print("\n✅ OpenAI Provider is working correctly!")

    except Exception as e:
        print(f"\n❌ Error during execution: {e}")


if __name__ == "__main__":
    test_openai()
