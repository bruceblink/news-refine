# FastAPI News Analytics

## 快速跑起来（本地）

1. 准备 PostgreSQL，并确认 `DATABASE_URL` 环境变量指向你的 DB（示例: postgresql+asyncpg://user:pass@host:5432/db）
2. 安装依赖:
   pip install .
3. 运行:
   uvicorn app.main:app --reload --port 8001

## API 示例

- GET /health

[API文档](https://news-analytics-gw35.onrender.com/)

