"""FastAPI HTTP endpoints."""

import os
from difflib import SequenceMatcher

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional,List
from sqlalchemy import text
from datetime import datetime

from agent.langchain_assitant import assistant_query,mysql_connection


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
class MenuItem(BaseModel):
    id:int
    dish_name:str
    price:float
    formatted_price:str # 格式化后的价格，例如：¥12.50
    description:str
    category:str
    spice_level:int
    spice_text:str
    flavor:str
    main_ingredients:str
    cooking_method:str
    is_vegetarian:bool
    allergens:str
    is_available:bool


    # 定义菜品列表响应模型
class MenuListResponse(BaseModel):
    """菜品列表响应"""
    success: bool
    menu_items: List[MenuItem] # 菜品列表
    count: int # 菜品数
    message: str # 响应消息提示

class ReservationItem(BaseModel):
    id: int
    num_people: int
    num_children: int
    arrival_time: Optional[str] = None
    seat_preference: Optional[str] = None
    main_dish_preference: Optional[str] = None
    other_comments: Optional[str] = None
    created_at: Optional[str] = None

class ReservationListResponse(BaseModel):
    success: bool
    reservations: List[ReservationItem]
    count: int
    message: str

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
async def faq_endpoint(query: str, limit: int = 2):
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

@app.get("/reservation/list",response_model=ReservationListResponse)
async def reservation_list():
    """
    获取到预订列表
    """
    # 获取到sqlalchemy.engine.Connection，这个对象和pymysql.Connection有点区别
    with mysql_connection().connect() as conn:
        sql = """
        select
            id,
            num_people,
            num_children,
            arrival_time,
            seat_preference,
            main_dish_preference,
            other_comments,
            created_at
        from
            menu.reservation_order
        """
        # 直接通过conn.execute().fetchall() 获取到的是一个列表，列表的每个元素是一个元组
        # results = conn.execute(text(sql)).fetchall()
        # 通过conn.execute().mappings().fetchall() 获取到的是一个列表，列表的每个元素是一个字典
        results = conn.execute(text(sql)).mappings().fetchall()
        # 把results 转换为 ReservationItem 模型的列表
        item_list = []
        for result in results:
            item = ReservationItem(
                id=result["id"],
                num_people=result["num_people"],
                num_children=result["num_children"],
                arrival_time=datetime.strftime(result["arrival_time"],"%Y-%m-%d %H:%M:%S"),
                seat_preference=result["seat_preference"],
                main_dish_preference=result["main_dish_preference"],
                other_comments=result["other_comments"],
                created_at=datetime.strftime(result["created_at"],"%Y-%m-%d %H:%M:%S"),
            )
            item_list.append(item)

    return ReservationListResponse(
        success=True,
        reservations=item_list,
        count=len(item_list),
        message="success"
    )


@app.get("/menu/list",response_model=MenuListResponse)
async def menu_list():
    """
    获取到菜单列表
    """
    with mysql_connection().connect() as conn:
        sql = """
            SELECT 
                                id, dish_name, price, description, category, 
                                spice_level, flavor, main_ingredients, cooking_method, 
                                is_vegetarian, allergens, is_available
                                FROM menu_items 
                                WHERE is_available = 1
                                ORDER BY category, dish_name
        """
        results = conn.execute(text(sql)).mappings().fetchall()
        # 把results 转换为 MenuItem 模型的列表
        item_list = []

        for result in results:
            spice_levels = {0: "不辣", 1: "微辣", 2: "中辣", 3: "重辣"}
            spice_text = spice_levels.get(result["spice_level"], "未知")
            item = MenuItem(
                id=result["id"],
                dish_name=result["dish_name"],
                price=result["price"],
                formatted_price=f"¥{result['price']:.2f}",
                description=result["description"],
                category=result["category"],
                spice_level=result["spice_level"],
                spice_text=spice_text,
                flavor=result["flavor"],
                main_ingredients=result["main_ingredients"],
                cooking_method=result["cooking_method"],
                is_vegetarian=result["is_vegetarian"],
                allergens=result["allergens"],
                is_available=result["is_available"],
            )
            item_list.append(item)

    return MenuListResponse(
        success=True,
        menu_items=item_list,
        count=len(item_list),
        message="success"
    )

if __name__ == "__main__":
    res = _get_similarity_score("位置在哪里","大堂电话是多少")
    print(res)