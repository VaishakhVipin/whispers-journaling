from fastapi import APIRouter, Request
from services.gemini import summarize, mcp_search
from services.assembly import get_assemblyai_token_universal_streaming
from services.supabase import insert_session
import uuid
from datetime import datetime, timezone
import os
from supabase import create_client
from algoliasearch.search.client import SearchClientSync

router = APIRouter()

# Algolia setup (single index for all users)
ALGOLIA_APP_ID = os.environ.get("ALGOLIA_APP_ID")
ALGOLIA_API_KEY = os.environ.get("ALGOLIA_API_KEY")
ALGOLIA_INDEX_NAME = os.environ.get("ALGOLIA_INDEX_NAME", "journal_entries")

algolia_client = SearchClientSync(ALGOLIA_APP_ID, ALGOLIA_API_KEY)

# Supabase setup for journal_entries backup (optional)
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

@router.post("/start_session")
async def start_session():
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    date = now.strftime("%Y-%m-%d")
    created_at = now.isoformat()
    error = None
    try:
        insert_session(session_id, date, created_at)
    except Exception as e:
        error = str(e)
    resp = {"session_id": session_id, "date": date, "created_at": created_at}
    if error:
        resp["supabase_error"] = error
    return resp

@router.post("/index")
async def index_entry(request: Request):
    data = await request.json()
    required_fields = ["user_id", "session_id", "date", "timestamp", "title", "summary", "tags", "text"]
    missing = [f for f in required_fields if f not in data]
    if missing:
        return {"error": f"Missing required fields: {', '.join(missing)}"}
    # Prepare entry for Algolia
    entry = {
        "user_id": data["user_id"],
        "session_id": data["session_id"],
        "date": data["date"],
        "timestamp": data["timestamp"],
        "title": data["title"],
        "summary": data["summary"],
        "tags": data["tags"],
        "text": data["text"],
        "audio_url": data.get("audio_url", "")
    }
    # If editing, update by entry_id
    if "entry_id" in data:
        entry_id = data["entry_id"]
        entry["objectID"] = entry_id
        try:
            res = algolia_client.save_object(index_name=ALGOLIA_INDEX_NAME, body=entry)
            algolia_client.wait_for_task(index_name=ALGOLIA_INDEX_NAME, task_id=res.task_id)
            # Optionally update in Supabase
            try:
                supabase.table("journal_entries").update(entry).eq("entry_id", entry_id).execute()
            except Exception:
                pass
            return {"result": "updated", "entry_id": entry_id, "algolia": res.to_dict()}
        except Exception as e:
            return {"error": str(e)}
    # If creating, add new entry
    else:
        entry_id = str(uuid.uuid4())
        entry["entry_id"] = entry_id
        entry["objectID"] = entry_id
        try:
            res = algolia_client.save_object(index_name=ALGOLIA_INDEX_NAME, body=entry)
            algolia_client.wait_for_task(index_name=ALGOLIA_INDEX_NAME, task_id=res.task_id)
            # Optionally insert in Supabase
            try:
                supabase.table("journal_entries").insert(entry).execute()
            except Exception:
                pass
            return {"result": "created", "entry_id": entry_id, "algolia": res.to_dict()}
        except Exception as e:
            return {"error": str(e)}

@router.post("/search")
async def search(request: Request):
    data = await request.json()
    query = data.get("query", "")
    user_id = data.get("user_id")
    if not user_id:
        return {"error": "Missing required field: user_id"}
    try:
        # Use Gemini + MCP logic
        result = mcp_search(query, user_id=user_id)
        return result
    except Exception as e:
        return {"error": str(e)}

@router.post("/summarize")
async def summarize_text(request: Request):
    data = await request.json()
    title, summary, tags = summarize(data["text"])
    return {"title": title, "summary": summary, "tags": tags}

@router.get("/token")
async def get_token():
    token = get_assemblyai_token_universal_streaming()
    return {"token": token} 