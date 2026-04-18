# News Analytics

基于 **FastAPI + PostgreSQL** 的新闻**数据清洗与分析**后端服务，专注于关键词提取、事件聚类、相关推荐与全文搜索。

> 本项目是整个新闻系统的**分析层**，仅负责对已入库的原始数据进行处理，不涉及数据采集与定时调度。

## 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                      整体系统                            │
│                                                         │
│  ┌──────────────┐    写入原始数据    ┌────────────────┐  │
│  │  LatestNews  │ ───────────────▶  │  PostgreSQL    │  │
│  │  (数据源仓库) │                   │  (共享数据库)   │  │
│  └──────────────┘                   └───────┬────────┘  │
│                                             │           │
│  ┌──────────────┐    触发分析任务            │           │
│  │ ani-updater  │ ─────────────────────────▶│           │
│  │ (采集&调度)   │                           │           │
│  └──────────────┘                   ┌───────▼────────┐  │
│                                     │ news-analytics │  │
│                                     │ (数据清洗&分析) │  │
│                                     └────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

| 项目 | 职责 | 仓库 |
|------|------|------|
| **LatestNews** | 新闻原始数据源 | [bruceblink/LatestNews](https://github.com/bruceblink/LatestNews) |
| **ani-updater** | 数据采集 & 定时任务调度 | [bruceblink/ani-updater](https://github.com/bruceblink/ani-updater) |
| **news-analytics** | 数据清洗、关键词提取、事件聚类、搜索 API | 本项目 |

## 技术栈

| 层次 | 技术 |
|------|------|
| Web 框架 | FastAPI (async) |
| 数据库 | PostgreSQL 16 + SQLAlchemy (asyncpg) |
| 向量/ML | scikit-learn (TF-IDF + K-Means)、pgvector |
| 分词 | wordfreq-cn |
| 词云 | wordcloud + matplotlib |
| 认证 | JWT (python-jose) + RBAC |
| 部署 | Docker Compose / Fly.io |

## 项目结构

```
news-analytics/
├── main.py                    # 应用入口
├── app/
│   ├── config.py              # 环境配置 (pydantic-settings)
│   ├── models.py              # SQLAlchemy 表定义
│   ├── db.py                  # 数据库连接池
│   ├── auth/                  # JWT 签发 & Swagger 认证
│   ├── core/                  # RBAC 权限控制
│   ├── dao/                   # 数据访问层
│   ├── middleware/            # JWT 解析中间件
│   ├── routers/               # 路由层
│   │   ├── analysis.py        # 分析模块
│   │   ├── news.py            # 新闻详情 & 相关推荐
│   │   └── search.py          # 全文搜索
│   ├── services/              # 业务逻辑层
│   │   ├── analysis_service.py
│   │   └── extract_news_service.py
│   └── utils/                 # 工具函数
├── postgres/init/             # 数据库初始化 SQL（按时间戳排序）
├── docker-compose.yaml
├── Dockerfile
└── fly.toml
```

## 核心功能

> 上游数据由 [ani-updater](https://github.com/bruceblink/ani-updater) 采集并写入 `news_info` 表后，本服务接管以下流程：

- **新闻清洗**：从 `news_info` 原始 JSON 解析结构化 `news_item`，含 embedding 聚类（K-Means）
- **关键词提取**：TF-IDF 逐篇提取关键词，存入 `news_keywords`
- **事件聚类**：基于 cluster_id 归并同类新闻形成 `news_event`，支持跨日合并
- **相关推荐**：基于关键词权重交集计算新闻相似度
- **全文搜索**：分词后匹配 `news_keywords` 实现关键词搜索
- **RBAC 权限**：支持 `owner / admin / member` 三级角色

## 快速启动

### 本地开发

```bash
# 1. 克隆项目
git clone https://github.com/bruceblink/news-analytics.git
cd news-analytics

# 2. 安装依赖
pip install .

# 3. 配置环境变量（可复制 .env.example）
export DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/newsletter
export JWT_SECRET=your_secret_key

# 4. 启动服务
uvicorn main:app --reload --port 8001
```

### Docker Compose

```bash
# 复制并修改环境变量
cp .env.example .env

# 启动全部服务（PostgreSQL + App）
docker compose up -d
```

> 首次启动时 `postgres/init/` 下的 SQL 脚本会按文件名顺序自动执行，完成表结构初始化。

## 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `DATABASE_URL` | asyncpg 连接串 | `postgresql+asyncpg://postgres:myapp123@postgres:5432/newsletter` |
| `JWT_SECRET` | JWT 签名密钥 | `change_me`（**生产必须修改**） |
| `CORS_ORIGINS` | 跨域白名单，分号分隔 | 空 |
| `TFIDF_MAX_FEATURES` | TF-IDF 最大词特征数 | `2000` |
| `STATIC_DIR` | 静态文件目录 | `static` |
| `WORDCLOUD_DIR` | 词云图片输出目录 | `static/wordclouds` |

## 主要 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| POST | `/api/analysis/extract_news_item` | 从原始数据提取新闻条目 |
| POST | `/api/analysis/extract_news_event` | 提取 & 归并新闻事件 |
| GET | `/api/analysis/events` | 新闻事件列表（需权限） |
| GET | `/api/news/{news_id}` | 新闻详情 |
| GET | `/api/news/{news_id}/related` | 相关新闻推荐 |
| GET | `/api/search/news?q=关键词` | 新闻全文搜索 |

完整交互文档：[Swagger UI](https://news-analytics-gw35.onrender.com/docs)

## 部署

### Fly.io

```bash
fly deploy
```

配置见 `fly.toml`，数据库通过 `DATABASE_URL` Secret 注入。

## License

MIT

