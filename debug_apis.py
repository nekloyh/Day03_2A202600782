import requests
import sys

def test_api(name, url):
    print("=" * 60)
    print(f"🔍 Testing {name} API...")
    print(f"URL: {url}")
    print("=" * 60)
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        
        print(f"Status Code: {response.status_code}")
        print(f"Reason: {response.reason}")
        print("\nHeaders:")
        for k, v in response.headers.items():
            print(f"  {k}: {v}")
            
        print("\nResponse Body (first 1000 chars):")
        print("-" * 50)
        print(response.text[:1000])
        print("-" * 50)
        
        if response.status_code == 429:
            print("\n🚨 DIAGNOSIS: 429 Too Many Requests (Rate Limited)")
            print("Explanation: The server has blocked requests from this IP address because it has received too many requests in a short period.")
            print("In cloud/sandbox development environments, multiple active sandboxes share a single external IP address.")
            print("If other active agents or users in the network are querying arXiv/Semantic Scholar, the API server will rate-limit the shared IP.")
        else:
            print("\n✅ Connection successful!")
            
    except Exception as e:
        print(f"❌ Connection failed with error: {e}")
    print("\n")

if __name__ == "__main__":
    # Test arXiv
    test_api(
        "arXiv", 
        "http://export.arxiv.org/api/query?search_query=all:cancer&max_results=1"
    )
    
    # Test Semantic Scholar
    test_api(
        "Semantic Scholar", 
        "https://api.semanticscholar.org/graph/v1/paper/search?query=cancer&limit=1"
    )
