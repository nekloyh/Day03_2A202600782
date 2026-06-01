import os
import sys
from dotenv import load_dotenv

# Load env variables from root
load_dotenv()

from src.core.openai_provider import OpenAIProvider
from src.agent.agent import ReActAgent
from src.tools.academic_tools import (
    search_arxiv,
    search_semantic_scholar,
    academic_polisher,
    format_citation
)

def get_research_tools():
    return [
        {
            "name": "search_arxiv",
            "description": "Search arXiv database for preprints and drafts. Args: query (str), limit (int, optional, default 3). Returns paper titles, authors, years, IDs, PDF links, and abstract snippets.",
            "func": search_arxiv
        },
        {
            "name": "search_semantic_scholar",
            "description": "Search Semantic Scholar database for peer-reviewed journal papers with citation numbers. Args: query (str), limit (int, optional, default 3). Returns paper titles, authors, years, citation count, URLs, and abstracts.",
            "func": search_semantic_scholar
        },
        {
            "name": "academic_polisher",
            "description": "Polishes raw text or draft notes into premium, publication-grade academic style. Args: text (str), tone (str, optional, default 'formal academic style'). Returns polished text.",
            "func": academic_polisher
        },
        {
            "name": "format_citation",
            "description": "Formats paper metadata into standard citation styles (APA, IEEE, or BibTeX). Args: title (str), authors (str, comma-separated), year (int), style (str, optional, default 'APA'). Returns formatted string.",
            "func": format_citation
        }
    ]

def main():
    print("="*60)
    print("🔬 AI SCIENTIFIC RESEARCH ASSISTANT AGENT (ReAct CLI) 🔬")
    print("="*60)
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ Error: OPENAI_API_KEY is not set in your .env file.")
        sys.exit(1)
        
    print("🤖 Initializing OpenAI LLM Brain (gpt-4o)...")
    try:
        # We use gpt-4o as configured in your working test
        llm = OpenAIProvider(model_name="gpt-4o", api_key=api_key)
        tools = get_research_tools()
        agent = ReActAgent(llm=llm, tools=tools, max_steps=7)
        print("✅ OpenAI LLM Brain and 4 Academic Tools registered successfully!\n")
    except Exception as e:
        print(f"❌ Error during initialization: {e}")
        sys.exit(1)
        
    # Check if prompt passed via CLI arguments
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        print(f"📥 Received CLI Request: '{query}'")
        print("\n🚀 Starting Agentic Reasoning Loop...")
        final_answer = agent.run(query)
        print("\n" + "="*50)
        print("🏁 FINAL RESPONSE:")
        print("="*50)
        print(final_answer)
        print("="*50)
        return

    # Otherwise run interactive CLI loop
    print("💡 Enter your research request below (or type 'exit' or 'quit' to stop).")
    print("💡 Examples:")
    print("   - 'Find 2 recent papers on Retrieval-Augmented Generation (RAG) and summarize them.'")
    print("   - 'Search for papers about Attention Is All You Need and format citation in BibTeX style.'")
    print("   - 'Polish this text: we ran tests on deep learning and got 95% accuracy which is cool.'")
    print("-" * 60)

    while True:
        try:
            query = input("\n🧑‍🔬 Research Prompt > ").strip()
            if not query:
                continue
            if query.lower() in ["exit", "quit", "q"]:
                print("\n👋 Goodbye!")
                break
                
            print("\n🚀 Agent is thinking...")
            final_answer = agent.run(query)
            
            print("\n" + "="*50)
            print("🏁 FINAL RESPONSE:")
            print("="*50)
            print(final_answer)
            print("="*50)
            
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    main()
