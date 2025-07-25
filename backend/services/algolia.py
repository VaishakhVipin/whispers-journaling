import os
import requests
from dotenv import load_dotenv

load_dotenv()

ALGOLIA_APP_ID = os.getenv("ALGOLIA_APP_ID")
ALGOLIA_API_KEY = os.getenv("ALGOLIA_API_KEY")
ALGOLIA_INDEX_NAME = os.getenv("ALGOLIA_INDEX_NAME", "whispers_logs")
ALGOLIA_MCP_URL = f"https://{ALGOLIA_APP_ID}-dsn.algolia.net/1/indexes/{ALGOLIA_INDEX_NAME}"

# index a journal entry
def index_journal(entry_dict):
    """
    Index a journal entry (dict) to Algolia MCP.
    """
    headers = {
        "X-Algolia-API-Key": ALGOLIA_API_KEY,
        "X-Algolia-Application-Id": ALGOLIA_APP_ID,
        "Content-Type": "application/json"
    }
    url = f"{ALGOLIA_MCP_URL}"
    resp = requests.post(url, headers=headers, json=entry_dict, timeout=10)
    resp.raise_for_status()
    return resp.json()

# search journals (delegates to gemini.py for actual search logic)
def search_journals(query):
    from .gemini import search_journals as gemini_search_journals
    return gemini_search_journals(query)

def _test_index_journal():
    print("Running MCP connection test for index_journal...")
    # Subtest: Ensure Algolia SDK is NOT imported
    import sys
    assert 'algoliasearch' not in sys.modules, "Algolia SDK should not be imported; only HTTP MCP should be used."
    # Test: Index a unique journal entry
    entry = {
        "title": "MCP Test Entry",
        "summary": "This entry is for MCP connection testing only.",
        "tags": ["mcp", "test", "unique12345"],
        "timestamp": "2025-07-24T10:22:00Z"
    }
    try:
        response = index_journal(entry)
        print("Index response:", response)
        assert 'objectID' in response, "Response should contain objectID."
        print("MCP indexing test passed.")
    except Exception as e:
        print("MCP indexing test failed:", e)

def _test_search_journals():
    print("\n=== Running MCP search test for natural language query ===")
    from services.gemini import mcp_search
    query = "when did I feel burnt out"
    response = mcp_search(query)
    print("MCP search response:", response)
    print("=== End of MCP search test ===\n")

if __name__ == "__main__":
    _test_index_journal()
    _test_search_journals()