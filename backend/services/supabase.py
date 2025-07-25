import os
from supabase import create_client, Client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def insert_session(session_id, date, created_at):
    data = {"session_id": session_id, "date": date, "created_at": created_at}
    supabase.table("sessions").insert(data).execute() 