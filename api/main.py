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
    top_k =2
    faq_items = await _load_faq_item_from_redis()
    # 2、将这些书中question和用户的query,进行比较，得到相识度得分
    score_list = []
    for faq_item in faq_items:
        score = faq_item["score"] = get_similary_score(query,faq_item["question"])
        score_list.append((score, faq_item))

    score_list.sort(key=lambda x:x[0],reverse=True)

    top_k_item = score_list[:top_k]
    return FAQResponse(
        success=True,
        query=query,
        sugggest=[faq_item for score, faq_item in top_k_item]
    )
