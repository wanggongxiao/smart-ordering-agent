"""
用来定义agent的主要代码
"""
from langchain.tools import tool
import pymysql
from pymysql.cursors import DictCursor 
import os
from dotenv import load_dotenv
from pathlib import Path
from sqlalchemy import text
load_dotenv()
root_path = Path(__file__).parent.parent
embeddings=None
milvus_client = None
engine = None

def get_embeddings():
    global embeddings
    if embeddings is None:
        from langchain_huggingface import HuggingFaceEmbeddings
        embedding_model = HuggingFaceEmbeddings(model=str(root_path / 'models' / 'bge-m3'))
    return embeddings

def get_milvus_client():
    global milvus_client
    if milvus_client is None:
        from pymilvus import MilvusClient
        import pymilvus
        milvus_client = pymilvus.Milvus(uri=os.getenv("MILVUS_URI"),token=os.getenv("MILVUS_TOKEN"))
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
    基于用户的口味偏好来搜索菜品
    """
    import pymilvus
    from langchain_huggingface import HuggingFaceEmbeddings

    # 1、构建用户query的embedding向量
    embeddings = get_embeddings();
    query_vector = embeddings.embed_query(user_query)

    # 2、连接milvus数据库
    milvus_client = get_embeddings()
    # 3、在milvus中进行向量搜索
    search_res = milvus_client.search(
        collection_name="menu_items",
        data=[query_vector],
        anns_field="embedding",
        output_filds=["text"],
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
    num_people:int = Field(description="预约总人数")
    num_children:int = Field(description="预约的0-2岁儿童人数")
    arrival_time:str = Field(description="预约的到达时间，格式：YYYY-MM-DD HH")
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
    创建餐厅预订，并将预订信息写入 MySQL
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
    from langchain_openai import OpenAI

    with open(root_path / 'agent' / 'prompt.txt','r',encoding='utf-8') as f:
        system_prompt = f.read()
    llm = create_agent(
        model = "gpt-4o-mini",
        system_prompt = system_prompt,
        tools = []
    )


if __name__ == "__main__":
    import asyncio
    res1 = make_reservation.invoke({"num_people":1,"num_children":2,"arrival_time":"2026-04-01 13","seat_preference":"无所谓","main_dish_preference":"无所谓","comment":""})
    # res = search_main_dishes.invoke({})
    print(res1)
