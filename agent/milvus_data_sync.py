"""
同步数据至Milvus中

"""
import os
from dotenv import load_dotenv
from pymysql.cursors import DictCursor
from pymilvus import DataType , IndexType
from decimal import Decimal
load_dotenv()
def insert_data():
    # 1.连接数据库，获取到menu_items中的所有数据
    import pymysql
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
        """
            cursor.execute(sql)
            results = cursor.fetchall()
            #将数据封装成json格式返回
            json_results = []
            for item in results:
                json_item = {}
                new_result = ""
                for key,value in item.items():
                    if type(value) == Decimal:
                        value = float(value)
                new_result += f"{key_name_mapping[key]}:{value}\n"
            json_results.append(new_result)

    # 2.连接Miluvs数据库，获取到client对象
    from pymilvus import MilvusClient
    client = MilvusClient(
        uri=os.getenv("MILVUS_HOST"),
        token=""
    )
    # 3.创建collection
    schema= MilvusClient.create_schema(
        auto_id=True
    )
    schema.add_field(field_name="id",datatype=DataType.INT64,is_primary=True)
    schema.add_field(field_name="vector",datatype=DataType.FLOAT_VECTOR,dim=1024)
    schema.add_field(field_name="text",datatype=DataType.VARCHAR,max_length=1500)
    index_params = MilvusClient.prepare_index_params()
    index_params.add_index(
        field_name="vector",
        index_type=IndexType.HNSW,
        metric_type = "L2"
    )

    res = client.create_collection(
        collection_name="menu_items",
        schema=schema,
        index_params=index_params
    )
    # 4.使用embedding模型对menu_items数据进行向量化
    from langchain_huggingface import HuggingFaceEmbeddings
    embedding_model = HuggingFaceEmbeddings(
        model = r"F:\Agent\项目\github\smart-ordering-agent\models\bge-m3"
    )
    vector_lists = []


    vector_lists = embedding_model.embed_documents(json_results)

    # 5.将向量化后的结果插入到Milvus当中去
    insert_data = []
    for vector, str_item in zip(vector_lists,json_results):
        insert_data.append(
            {
                "vector":vector,
                "text":str_item
            }
        )
    inser_res = client.insert(data=insert_data,collection_name="menu_items")
    print(inser_res)

if __name__ == "__main__":
    insert_data()
