"""
同步数据至Milvus中

"""
import os
from dotenv import load_dotenv
from pymysql.cursors import DictCursor
from pymilvus import DataType , IndexType
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
                for key,value in item.items():
                    json_item[key_name_mapping[key]] = value
                json_results.append(json_item)

    # 2.连接Miluvs数据库，获取到client对象
    from pymilvus import MilvusClient
    client = MilvusClient(
        uri=os.getenv("MILVUS_HOST"),
        user=os.getenv("MYSQL_USERNAME"),
        password=os.getenv("MYSQL_PASSWORD")
    )
    # 3.创建collection
    schema= MilvusClient.create_schema(
        auto_id=True
    )
    schema.add_field(field_name="id",datatype=DataType.INT64,is_prmary=True)
    schema.add_field(field_name="vector",datatype=DataType.FLOAT_VECTOR,dim=1024)
    schema.add_field(field_name="text",datatype=DataType.JSON)
    index_params = MilvusClient.prepare_index_params()
    index_params.add_index(
        field_name="vector",
        index_type=IndexType.HNSW,
        metric_type = "L2"
    )

    client.create_collection(
        collection_name="menu_items",
        schema=schema,
        index_params=index_params
    )
    # 4.使用embedding模型对menu_items数据进行向量化
    # 5.将向量化后的结果插入到Milvus当中去
