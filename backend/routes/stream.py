from fastapi import APIRouter, Request
from services.algolia import index_journal, search_journals
from services.gemini import summarize, mcp_search
from services.assembly import get_assemblyai_token

router = APIRouter()

@router.post("/index")
async def index_entry(request: Request):
    entry = await request.json()
    return index_journal(entry)

@router.post("/search")
async def search(request: Request):
    data = await request.json()
    query = data.get("query", "")
    return mcp_search(query)

@router.post("/summarize")
async def summarize_text(request: Request):
    data = await request.json()
    summary, tags = summarize(data["text"])
    return {"summary": summary, "tags": tags}

@router.get("/token")
async def get_token():
    token = await get_assemblyai_token()
    return {"token": token} 