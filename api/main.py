"""FastAPI HTTP endpoints."""

import os
from difflib import SequenceMatcher

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agent.langchain_assitant import assistant_query


load_dotenv()

app = FastAPI()
client = None


def _get_redis_client():
    global client
    if client is None:
        from redis.asyncio import Redis

        client = Redis.from_url(
            os.getenv("REDIS_URL", "redis://localhost:6379"),
            decode_responses=True,
        )
    return client


class ChatRequest(BaseModel):
    query: str


class FaqItem(BaseModel):
    question: str
    answer: str


class FAQResponse(BaseModel):
    success: bool
    query: str
    suggestions: list[FaqItem]


async def _load_faq_items_from_redis():
    # 获取客户端
    redis_client = _get_redis_client()
    pipeline = redis_client.pipeline()
    # 从redis获取faq数据
    faq_keys = await redis_client.smembers("faq:all_items")
    # 加载faq_keys所对应的所有faq
    for faq_key in sorted(faq_keys):
        pipeline.hgetall(faq_key)
    all_faq_items = await pipeline.execute()

    return [
        FaqItem(
            question=item["question"],
            answer=item["answer"],
        )
        for item in all_faq_items
        if item.get("question") and item.get("answer")
    ]


def _get_similarity_score(query: str, faq_question: str) -> float:
    """
    使用简单的字符串匹配算法，计算query和faq_question的相似度的分
    """
    if not query or not faq_question:
        return 0.0

    # 使用包：difflib.sequenceMatcher
    sequence_matcher = SequenceMatcher(None, query, faq_question)
    score = sequence_matcher.ratio()
    query_chars = set(query)
    faq_chars = set(faq_question)
    union = query_chars | faq_chars
    jaccard_score = len(query_chars & faq_chars) / len(union) if union else 0.0

    # 3、对这两个分数做一个加权
    return 0.6 * score + 0.4 * jaccard_score


@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    """Stream an Agent response using server-sent events."""
    return StreamingResponse(
        assistant_query(request.query),
        media_type="text/event-stream",
    )

@app.get("/faq/suggest", response_model=FAQResponse)
async def faq_endpoint(query: str, limit: int = 5):
    # 1、从redis中获取的所有Faq数据
    top_k = max(1, min(limit, 20))
    faq_items = await _load_faq_items_from_redis()
    # 2、将这些书中question和用户的query,进行比较，得到相识度得分
    score_list = []
    for faq_item in faq_items:
        score = _get_similarity_score(query, faq_item.question)
        score_list.append((score, faq_item))

    score_list.sort(key=lambda item: item[0], reverse=True)

    top_k_item = score_list[:top_k]
    return FAQResponse(
        success=True,
        query=query,
        suggestions=[faq_item for _, faq_item in top_k_item],
    )
