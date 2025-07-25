from fastapi import APIRouter, Request
from services.algolia import index_journal, search_journals
from services.gemini import summarize, mcp_search
from services.assembly import get_assemblyai_token_universal_streaming

router = APIRouter()

@router.post("/index")
async def index_entry(request: Request):
    entry = await request.json()
    return index_journal(entry)

@router.post("/search")
async def search(request: Request):
    data = await request.json()
    return mcp_search(data["query"])

@router.post("/summarize")
async def summarize_text(request: Request):
    data = await request.json()
    title, summary, tags = summarize(data["text"])
    return {"title": title, "summary": summary, "tags": tags}

@router.get("/token")
async def get_token():
    token = get_assemblyai_token_universal_streaming()
    return {"token": token} 