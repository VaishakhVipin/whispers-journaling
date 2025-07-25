import os
import requests
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ALGOLIA_APP_ID = os.getenv("ALGOLIA_APP_ID")
ALGOLIA_API_KEY = os.getenv("ALGOLIA_API_KEY")
ALGOLIA_SEARCH_KEY = os.getenv("ALGOLIA_SEARCH_KEY")
ALGOLIA_INDEX_NAME = os.getenv("ALGOLIA_INDEX_NAME", "whispers_logs")
ALGOLIA_MCP_URL = f"https://{ALGOLIA_APP_ID}-dsn.algolia.net/1/indexes/{ALGOLIA_INDEX_NAME}/query"

# --- Gemini summarization ---
def summarize(text):
    """
    Summarize text using Gemini API (model: gemini-2.0-flash). Generate a short title, a concise summary, and 3-5 tags. Return only a JSON object with keys: 'title', 'summary', 'tags'.
    """
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    headers = {"Content-Type": "application/json"}
    prompt = (
        "Given the following journal entry, generate: "
        "1. A short, relevant title (3-7 words, no punctuation). "
        "2. A concise summary (1-2 sentences, no advice or analysis). "
        "3. 3-5 tags (single words or short phrases). "
        "Return ONLY a valid JSON object with keys: 'title', 'summary', 'tags'. "
        "Do NOT include any markdown, code block, or extra text. "
        "Example: {\"title\": \"Burnout at work\", \"summary\": \"Felt burnt out after a long week.\", \"tags\": [\"burnout\", \"work\"]} "
        "\n\nJournal Entry:\n" + text
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 256}
    }
    params = {"key": GEMINI_API_KEY}
    resp = requests.post(url, headers=headers, params=params, json=payload, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    # Try to parse JSON from Gemini's response
    import json as pyjson
    try:
        response_text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        parsed = pyjson.loads(response_text)
        title = parsed.get("title", "")
        summary = parsed.get("summary", "")
        tags = parsed.get("tags", [])
    except Exception:
        title = ""
        summary = response_text
        tags = []
    return title, summary, tags

# --- Algolia MCP search ---
def search_journals(query):
    """
    Search Algolia MCP index and return list of journal dicts.
    """
    headers = {
        "X-Algolia-API-Key": ALGOLIA_SEARCH_KEY or ALGOLIA_API_KEY,
        "X-Algolia-Application-Id": ALGOLIA_APP_ID,
        "Content-Type": "application/json"
    }
    payload = {"params": f"query={query}"}
    resp = requests.post(ALGOLIA_MCP_URL, headers=headers, json=payload, timeout=10)
    resp.raise_for_status()
    hits = resp.json().get("hits", [])
    # format as required
    results = []
    for hit in hits:
        results.append({
            "title": hit.get("title", ""),
            "summary": hit.get("summary", ""),
            "tags": hit.get("tags", []),
            "timestamp": hit.get("timestamp", "")
        })
    return results

# --- Gemini tool-calling for Algolia MCP ---
def search_with_tool_call(query):
    """
    Use Gemini-2.0-Flash tool-calling to search Algolia MCP via a tool schema.
    Returns Gemini's response (may include tool call results).
    """
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    headers = {"Content-Type": "application/json"}
    # Define the tool schema for Algolia search
    tool_schema = [
        {
            "function_declarations": [
                {
                    "name": "search_algolia",
                    "description": "Searches the user's journal entries using Algolia MCP and returns a list of relevant entries.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "The search query."}
                        },
                        "required": ["query"]
                    }
                }
            ]
        }
    ]
    # Prompt Gemini to use the tool
    prompt = f"""
You are an AI assistant for a journaling app. When the user asks a question about their past journals, use the search_algolia tool to find relevant entries. Only use the tool, do not answer from your own knowledge.
User query: {query}
"""
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "tools": tool_schema,
        "generationConfig": {"maxOutputTokens": 512}
    }
    params = {"key": GEMINI_API_KEY}
    resp = requests.post(url, headers=headers, params=params, json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()

def mcp_search(query):
    """
    Enhanced MCP tool-calling loop for Gemini:
    1. Ask Gemini to extract only the most relevant, specific search terms from the user query (not generic words), and let Gemini decide the number of terms dynamically.
    2. If it's a search, use those terms to query Algolia individually; otherwise, answer directly.
    3. Always include a simple Gemini response in the output, even for Algolia queries.
    4. Return a clean, deduplicated, and readable response.
    """
    import json as pyjson
    import re
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    headers = {"Content-Type": "application/json"}
    # Step 1: Ask Gemini to extract search terms and decide if it's a search
    extraction_prompt = (
        "Given the following user query, do the following: "
        "1. Decide if this is a search query about past journal entries (answer 'yes' or 'no' as 'is_search'). "
        "2. If yes, extract a concise list of only the most relevant, specific search terms, keywords, or tags (avoid generic words like 'journal', 'diary', 'entries', 'when', 'date', etc.). Let the number of terms be dynamic, based on the query. "
        "3. Provide a simple, direct Gemini response to the query as 'gemini_response'. "
        "Return ONLY a valid JSON object with keys: 'is_search' (yes/no), 'search_terms' (list), and 'gemini_response' (string). "
        "Do NOT include any markdown, code block, or extra text. "
        "Example: For the query 'when was I burnt out', good search_terms would be ['burnt out', 'burnout', 'exhaustion', 'stress'], not ['journal', 'date', 'when', 'entries']. "
        f"\n\nUser query: {query}"
    )
    extraction_payload = {
        "contents": [{"parts": [{"text": extraction_prompt}]}],
        "generationConfig": {"maxOutputTokens": 512}
    }
    params = {"key": GEMINI_API_KEY}
    resp = requests.post(url, headers=headers, params=params, json=extraction_payload, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    try:
        response_text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        # Strip code block markers if present
        cleaned = re.sub(r"^```(?:json)?|```$", "", response_text.strip(), flags=re.MULTILINE).strip()
        parsed = pyjson.loads(cleaned)
        is_search = parsed.get("is_search", "no").strip().lower() == "yes"
        search_terms = parsed.get("search_terms", [])
        gemini_response = parsed.get("gemini_response", "")
    except Exception:
        is_search = False
        search_terms = []
        gemini_response = ""
    # Debug print
    print("User query:", query)
    print("Gemini full response_text:", response_text)
    print("Gemini search_terms:", search_terms)
    print("is_search:", is_search)
    # Step 2: If it's a search, use search_terms to query Algolia individually
    algolia_results = []
    seen_ids = set()
    if is_search and search_terms:
        headers_algolia = {
            "X-Algolia-API-Key": ALGOLIA_SEARCH_KEY or ALGOLIA_API_KEY,
            "X-Algolia-Application-Id": ALGOLIA_APP_ID,
            "Content-Type": "application/json"
        }
        for term in search_terms:
            print(f"Searching Algolia for term: '{term}' ...", end=' ')
            payload_algolia = {"params": f"query={term}"}
            resp_algolia = requests.post(ALGOLIA_MCP_URL, headers=headers_algolia, json=payload_algolia, timeout=10)
            resp_algolia.raise_for_status()
            hits = resp_algolia.json().get("hits", [])
            print(f"found {len(hits)} results.")
            for hit in hits:
                obj_id = hit.get("objectID")
                if obj_id and obj_id not in seen_ids:
                    # Only keep relevant fields for the API response
                    clean_hit = {
                        "objectID": obj_id,
                        "title": hit.get("title", ""),
                        "summary": hit.get("summary", ""),
                        "tags": hit.get("tags", []),
                        "timestamp": hit.get("timestamp", "")
                    }
                    algolia_results.append(clean_hit)
                    seen_ids.add(obj_id)
    print("Final Algolia results:", algolia_results)
    # Step 3: Return both Gemini's response and Algolia results (if any), formatted
    return {
        "gemini_response": gemini_response,
        "results": algolia_results,
        "search_terms": search_terms,
        "is_search": is_search
    } 