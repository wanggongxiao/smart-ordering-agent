"""
用来定义agent的主要代码
"""
from langchain.tools import tool
import pymysql
from pymysql.cursors import DictCursor 
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()
root_path = Path(__file__).parent.parent

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
    embedding_model = HuggingFaceEmbeddings(model=str(root_path / 'models' / 'bge-m3'))
    query_vector = embedding_model.embed_query(user_query)

    # 2、连接milvus数据库
    milvus_client = pymilvus.Milvus(uri=os.getenv("MILVUS_URI"),token=os.getenv("MILVUS_TOKEN"))

    # 3、在milvus中进行向量搜索
    milvus_client.search(
        collection_name="menu_items",
        data=[query_vector],
        anns_field="embedding",
        output_filds=["text"],
        limit=3
    )



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
    res = search_main_dishes.invoke({})
    print(res)
