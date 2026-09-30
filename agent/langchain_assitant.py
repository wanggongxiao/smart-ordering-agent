"""
用来定义agent的主要代码
"""
import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from langchain.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
import pymysql
from pymysql.cursors import DictCursor 
from sqlalchemy import text

load_dotenv()
root_path = Path(__file__).parent.parent
embeddings=None
milvus_client = None
engine = None
agent_instance = None
agent_checkpointer = InMemorySaver()
agent_lock = asyncio.Lock()

def get_embeddings():
    global embeddings
    if embeddings is None:
        from sentence_transformers import SentenceTransformer
        embeddings = SentenceTransformer("BAAI/bge-m3")
    return embeddings

def get_milvus_client():
    global milvus_client
    if milvus_client is None:
        from pymilvus import MilvusClient
        import pymilvus
        milvus_client = pymilvus.MilvusClient(uri=os.getenv("MILVUS_HOST"),token=os.getenv("MILVUS_TOKEN"))
    return milvus_client

def mysql_connection():
    global engine
    if engine is None:
        from sqlalchemy import create_engine
        engine = create_engine(
            url=f"mysql+pymysql://{os.getenv('MYSQL_USERNAME')}:{os.getenv('MYSQL_PASSWORD')}@{os.getenv('MYSQL_HOST')}:{os.getenv('MYSQL_PORT')}/{os.getenv('MYSQL_DATABASE')}",
            pool_size=15
        )
    return engine

@tool
def search_main_dishes():
    """
    用来搜索餐当中的主菜
    """
    print("进入搜索主菜工具")
    key_name_mapping={
        "dish_name":"菜名",
        "price":"价格",
        "description":"描述",
        "spice_level":"辣度",
        "flavor":"口味",
        "main_ingredients":"主要食材",
        "cooking_method":"烹饪方式",
        "is_vegetarian":"是否素食",
        "allergens":"过敏原"
    }
    with pymysql.connect(
        host=os.getenv("MYSQL_HOST"),
        user=os.getenv("MYSQL_USERNAME"),
        password=os.getenv("MYSQL_PASSWORD"),
    ) as conn:
        with conn.cursor(DictCursor) as cursor:
            sql ="""
        select 
            dish_name, 
            price,
            description, 
            spice_level, 
            flavor, 
            main_ingredients,
            cooking_method,
            is_vegetarian,
            allergens
        from
            menu.menu_items
        where
            is_featured = 1
        """
            cursor.execute(sql)
            results = cursor.fetchall()
            #将数据封装成json格式返回
            json_results = []
            for item in results:
                json_item = {}
                for key,value in item.items():
                    json_item[key_name_mapping[key]] = value
                json_results.append(json_item)
            return json_results

@tool
def user_flavar_search(user_query:str):
    
    """
    基于用户的口味偏好来搜索相关菜品
    """
    import pymilvus
    from langchain_huggingface import HuggingFaceEmbeddings

    print("进入口味偏好工具")
    # 1、构建用户query的embedding向量
    embeddings = get_embeddings()
    query_vector = embeddings.encode(
    user_query,
    normalize_embeddings=True,
    ).tolist()

    # 2、连接milvus数据库
    milvus_client = get_milvus_client()
    # 3、在milvus中进行向量搜索
    search_res = milvus_client.search(
        collection_name="menu_items",
        data=[query_vector],
        anns_field="vector",
        output_fields=["text"],
        limit=3
    )

    # 4.解析搜索结果
    if search_res:
        all_results = search_res[0]
        # all_results：列表
        final_result =[]

        for item in all_results:
            item_str = item["entity"]['text']
            final_result.append(item)

        return final_result
    else:
        return "在当前库里没有找到用户喜好相关菜品。"


from pydantic import BaseModel,Field
class ReservationToolArgsInfo(BaseModel):
    num_people:int = Field(ge=1, description="预约总人数")
    num_children:int = Field(default=0, ge=0, description="预约的0-2岁儿童人数；未提及时为0")
    arrival_time:str = Field(description="预约的准确到达时间，格式：YYYY-MM-DD HH")
    seat_preference:str = Field(description="预约的座位偏好，当用户没有特殊需求时，传空字符串")
    main_dish_preference:str = Field(description="预约的主菜偏好，当用户没有特殊需求时，传空字符串")
    comment:str = Field(description="预约的其他备注，当用户没有特殊需求时，传空字符串")
@tool(args_schema=ReservationToolArgsInfo)
def make_reservation(
    num_people: int,
    num_children: int,
    arrival_time: str,
    seat_preference: str,
    main_dish_preference: str,
    comment: str,
):
    """
    用户明确确认完整预订信息后，创建餐厅预订并写入 MySQL。
    """
    engine = mysql_connection()

    sql = text("""
        INSERT INTO reservation_order (
            num_people,
            num_children,
            arrival_time,
            seat_preference,
            main_dish_preference,
            other_comments
        )
        VALUES (
            :num_people,
            :num_children,
            :arrival_time,
            :seat_preference,
            :main_dish_preference,
            :comment
        )
    """)

    with engine.begin() as conn:
        conn.execute(sql, {
            "num_people": num_people,
            "num_children": num_children,
            "arrival_time": arrival_time,
            "seat_preference": seat_preference,
            "main_dish_preference": main_dish_preference,
            "comment": comment,
        })

    return "预定成功"

async def create_agent():

    from langchain.agents import create_agent
    from langchain_mcp_adapters.client import MultiServerMCPClient
    from langchain_openai import ChatOpenAI
    client = MultiServerMCPClient(
        connections={
            "amap_map": {
            "transport": "sse",
            "url": "https://mcp.api-inference.modelscope.net/ccaef2a2308042/sse"
            }
        }
    )
    prompt_path = root_path / "agent" / "prompts" / "system_prompt.txt"
    with prompt_path.open("r", encoding="utf-8") as f:
        system_prompt = f.read()
    mcp_tools = await client.get_tools()
    llm = ChatOpenAI(
        model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
        api_key=os.getenv("LLM_API_KEY"),
        base_url=os.getenv("LLM_BASE_URL"),
    )
    return create_agent(
        model=llm,
        system_prompt=system_prompt,
        tools=[search_main_dishes, make_reservation,user_flavar_search] + mcp_tools,
        checkpointer=agent_checkpointer,
    )


async def get_agent():
    """Create the Agent once so its checkpointer survives across requests."""
    global agent_instance
    if agent_instance is None:
        async with agent_lock:
            if agent_instance is None:
                agent_instance = await create_agent()
    return agent_instance

async def test_agent():
    agent = await get_agent()
    config = {"configurable": {"thread_id": "123"}}
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": "你能为我做什么？"}]},
        config=config,
    )
    print(result["messages"][-1].content)

async def assistant_query(user_query: str, thread_id: str):
    """
    接受来自前端的用户querry,使用agent来进行回复
    """
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from langchain.messages import ToolMessage
    agent = await get_agent()
    config = {"configurable": {"thread_id": thread_id}}
    current_time = datetime.now(ZoneInfo("Asia/Shanghai")).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    time_system_prompt = {
        "role": "system",
        "content": f"当前时间为 {current_time}(Asia/Shanghai)。",
    }
    # result = await agent.ainvoke(
    #     {
    #         "messages": [
    #             time_system_prompt,
    #             {"role": "user", "content": user_query},
    #         ]
    #     },
    #     config=config,
    async for chunk in agent.astream({"messages": [time_system_prompt,{"role": "user", "content": user_query},]},config=config,stream_mode="messages"):
        # 首先chunk是一个tuple:(AIMessageChunk/ToolMessage,_)
        message = chunk[0]
        if type(message) == ToolMessage:
            continue
        # 然后给到前端 SSE
        # SSE的数据结构：data:{"type":"token","content":"你好"}
        # 能快速额产生的token，给到后端
        import json
        payload = {"content":message.content,"type":"token"}
        payload_str = json.dumps(payload,ensure_ascii=False)
        yield f'data: {payload_str}\n\n'


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_agent())
