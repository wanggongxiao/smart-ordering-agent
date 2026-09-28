"""FastAPI HTTP endpoints."""

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agent.langchain_assitant import assistant_query

app = FastAPI()


class ChatRequest(BaseModel):
    query: str


@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    """Stream an Agent response using server-sent events."""
    return StreamingResponse(
        assistant_query(request.query),
        media_type="text/event-stream",
    )
