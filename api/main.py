"""FastAPI HTTP endpoints."""

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agent.langchain_assitant import assistant_query

app = FastAPI()


class ChatRequest(BaseModel):
    query: str

class FaqItem(BaseModel):
    question:str
    answer:str
class FAQResponse(BaseModel):
    success:bool
    query: str
    # 针对用户的一个问题，需要给多个faq
    sugggest:list[FaqItem]


@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    """Stream an Agent response using server-sent events."""
    return StreamingResponse(
        assistant_query(request.query),
        media_type="text/event-stream",
    )

@app.post("/fap")
async def faq_endpoint(resquest:ChatRequest):
    query = resquest.query
    # 1、从redis中获取的所有Faq数据

