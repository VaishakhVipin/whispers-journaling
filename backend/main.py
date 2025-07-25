from fastapi import FastAPI
from routes.stream import router as stream_router

app = FastAPI()
app.include_router(stream_router)
