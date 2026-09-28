# Smart Ordering Agent

一个基于 LangChain、MySQL、Milvus 和 BGE-M3 构建的智能餐厅点餐与预订助手实验项目。

项目目标是让用户通过自然语言查询餐厅信息和菜品，根据口味偏好获得推荐，并在信息完整且经过确认后完成餐位预订。

## 功能规划

- 查询餐厅的地址、联系电话和营业时间等基础信息
- 从 MySQL 菜单库中查询特色菜及菜品详情
- 使用 BGE-M3 生成文本向量，通过 Milvus 进行口味语义检索
- 收集人数、到达时间、座位偏好、主菜偏好和备注等预订信息
- 下单前向用户展示预订内容并进行二次确认

## 当前进度

目前项目处于早期开发阶段。

- 已完成 MySQL 菜单表和预订单表的初始化脚本
- 已完成特色菜查询工具及结构化结果转换
- 已完成预订信息写入 MySQL 的工具
- 已加入餐厅助手的基础系统提示词
- 已加入 BGE-M3 模型和 Milvus 客户端的按需加载逻辑
- 已开始实现 MySQL 菜单数据同步和 Milvus HNSW 向量索引
- Agent 对话流程、完整数据同步和语义检索结果返回仍在开发中

## 技术栈

- Python 3.12+
- LangChain
- OpenAI 兼容模型接口
- MySQL / PyMySQL
- Milvus / PyMilvus
- BGE-M3 / Hugging Face Embeddings
- uv

## 项目结构

```text
smart-ordering-agent/
|-- agent/
|   |-- langchain_assitant.py       # Agent 和工具代码
|   |-- milvus_data_sync.py         # MySQL 菜单数据同步脚本（开发中）
|   `-- prompts/
|       `-- system_prompt.txt       # 餐厅助手系统提示词
|-- models/
|   `-- bge-m3/                     # 本地向量模型
|-- main.py                         # 项目入口（待完善）
|-- menu.sql                        # 菜单及预订单表结构和示例数据
|-- pyproject.toml                  # 项目依赖配置
`-- .env                            # 本地环境变量，不提交到 Git
```

## 本地运行

### 1. 安装依赖

项目使用 `uv` 管理 Python 环境和依赖：

```powershell
uv sync
```

### 2. 初始化 MySQL

先创建 `menu` 数据库：

```powershell
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS menu CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
```

然后导入项目根目录下的 `menu.sql`：

```powershell
cmd /c "mysql -u root -p menu < menu.sql"
```

### 3. 配置环境变量

在项目根目录创建 `.env` 文件：

```dotenv
# OpenAI 兼容接口
LLM_MODEL=gpt-4o-mini
LLM_BASE_URL=https://your-api-endpoint.example/v1
LLM_API_KEY=your-api-key

# MySQL
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USERNAME=root
MYSQL_PASSWORD=your-mysql-password
MYSQL_DATABASE=menu

# Milvus
MILVUS_URI=http://127.0.0.1:19530
MILVUS_TOKEN=
```

不要把包含真实密码或 API Key 的 `.env` 提交到 Git。

### 4. 准备本地向量模型

语义检索使用 `BAAI/bge-m3` 模型。模型权重不会提交到 Git，使用向量检索前需要自行下载，并放置在以下目录：

```text
models/bge-m3/
```

### 5. 测试特色菜查询

在项目根目录执行：

```powershell
uv run python .\agent\langchain_assitant.py
```

数据库配置正确时，程序会输出菜单中标记为特色菜的记录。

## 向量检索设计

项目计划使用以下流程完成基于口味偏好的菜品搜索：

1. 从 MySQL 的 `menu_items` 表读取菜品信息
2. 使用本地 BGE-M3 模型将菜品文本转换为 1024 维向量
3. 将菜品信息和向量写入 Milvus 的 `menu_items` Collection
4. 为向量字段创建 HNSW 索引
5. 将用户的口味描述转换为向量，并返回相似度最高的菜品

当前数据同步脚本仍在开发中，尚未作为正式初始化命令提供。

## 数据库说明

`menu.sql` 包含以下数据表：

- `menu_items`：保存菜名、价格、口味、辣度、主要食材、烹饪方式和过敏原等菜单信息
- `reservation_order`：保存人数、到达时间、座位偏好、主菜偏好和其他备注等预订信息

## 开发说明

该项目目前主要用于学习和验证基于 LangChain 的餐厅 Agent 工作流，不建议直接用于生产环境。正式部署前还需要补充参数校验、异常处理、权限控制、测试以及完整的预订状态管理。

## License

暂未指定开源许可证。
