def redis_comand_demo():
    """
    redis相关的命令demo演示
    """
    from redis import Redis
    # 1、获取到client对象
    client = Redis.from_url("redis://127.0.0.1:6379",decode_responses=True)

    # 通过client，获取到pipeline对象
    pipeline = client.pipeline()

    # 2、使用client执行一些命令
    # 2.1执行set命令，创建一个value类型的string的ley-vaule对
    pipeline.set("name","张三")
    # 2.2 执行get命令，获取到key为name的valus
    name = client.get("name")
    print(name)

    #2.2创建以恶calue的hash map 的key-value对
    pipeline.hset(
        "faq:items:address:test",
        mapping={
            "question":"地址是多少",
            "answer":"北京市海淀区"
        }

    )
    reslut = pipeline.execute()
    # 获取到某一个key所对应hash_map
    faq_item = client.hgetall("faq:items:address:test")
    print(faq_item)

if __name__ == "__main__":
    redis_comand_demo()