# nts-analytics

> **News TimeStream Platform** 的分析层服务（v1.2）

基于 **FastAPI + PostgreSQL** 的新闻数据加工与分析 API，负责从原始新闻数据中提取关键词、聚合事件、提供搜索与推荐接口。本服务以**被动触发**模式运行，由 Agora 的定时任务通过 HTTP 调用驱动，不主动轮询数据源。

## 系统架构

```txt
                    ┌─────────────────────┐
                    │      Frontend       │
                    │   (Web / App，规划)  │
                    └──────────┬──────────┘
                               ↓
                    ┌─────────────────────┐
                    │     BFF Service     │  ⭐ 编排层（规划中，Java Spring Boot）
                    │  数据聚合 + 前端适配  │
                    └───────┬─────────────┘
                            │                      │
                            ↓                      ↓
             ┌──────────────────────┐   ┌──────────────────────┐
             │        Agora         │   │    news-analytics    │
             │  Rust（已运行）       │   │   Python（已运行）    │
             │  定时调度 + 数据入库   │   │   数据清洗 & 分析 API  │
             │  + Web API + 认证    │   │                      │
             └──────────┬───────────┘   └──────────────────────┘
                  主动拉取 ↑  触发分析 HTTP POST ↗
             ┌──────────────────────┐
             │      LatestNews      │
             │  Node.js（已运行）    │
             │  多源新闻数据聚合     │
             └──────────────────────┘

            数据流向：LatestNews → Agora → nts-analytics（单向）
```

### 各系统职责

| 系统 | 语言 | 状态 | 职责 | 仓库 |
|------|------|------|------|------|
| **LatestNews** | Node.js / TypeScript | ✅ 运行中 | 多源新闻抓取，提供查询 API | [bruceblink/LatestNews](https://github.com/bruceblink/LatestNews) |
| **Agora** | Rust | ✅ 运行中 | cron 调度、数据入库、用户认证（Keylo）| [bruceblink/agora](https://github.com/bruceblink/agora) |
| **nts-analytics** | Python | ✅ 运行中（Render）| 数据清洗、关键词提取、事件聚合、分析 API | 本项目 |
| **BFF** | Java Spring Boot | 🚧 规划中 | 面向前端的编排层，聚合 Agora + analytics 数据 | — |

> **认证说明**：用户认证统一由 Agora 内置的 **Keylo** 能力（OAuth2 / JWT / RBAC）提供，BFF 通过调用 Agora `/auth/*` 端点完成鉴权，news-analytics 本身**不直接服务前端**，无需独立认证。

### Agora 已注册定时任务

| 任务名 | 频率 | 说明 |
|--------|------|------|
| `health_check` | 每 10 分钟 | 保活 Render 上的 nts-analytics 服务 |
| `fetch_all_news` | 每小时整点 | 拉取 LatestNews 全部数据源写入 news_info |
| `extract_transform_news_info_to_item` | 每 10 分钟（6-23 点）| 触发 analytics 提取 news_item |
| `extract_keywords_to_news_keywords` | 每 30 分钟（6-23 点）| 触发 analytics 提取关键词 |
| `extract_news_event` | 每 30 分钟（6-23 点）| 触发 analytics 提取新闻事件 |
| `merge_cross_day_news_events` | 每天凌晨 1 点 | 触发 analytics 合并跨天事件 |

## 技术栈

| 层次 | 技术 |
|------|------|
| Web 框架 | FastAPI (async) |
| 数据库 | PostgreSQL 16 + SQLAlchemy Core (asyncpg) |
| 向量/ML | scikit-learn (TF-IDF + K-Means)、pgvector |
| 分词 | wordfreq-cn |
| 词云 | wordcloud + matplotlib |
| 部署 | Docker Compose / Render / Fly.io |

## 项目结构

```txt
nts-analytics/
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

上游数据由 **Agora** 定时拉取 LatestNews 并写入 `news_info` 表，随后 HTTP 触发本服务执行以下分析流程：

- **新闻清洗**：从 `news_info` 原始 JSON 解析结构化 `news_item`，含 embedding + K-Means 聚类
- **关键词提取**：TF-IDF 逐篇提取关键词，存入 `news_keywords`
- **事件聚合**：基于 `cluster_id` 归并同类新闻形成 `news_event`，支持跨日合并
- **词云生成**：基于指定时间范围的新闻语料生成词云图片
- **相关推荐**：基于关键词权重交集计算新闻相似度排序
- **全文搜索**：中文分词后匹配 `news_keywords` 实现关键词检索

## 快速启动

### 本地开发

```bash
# 1. 克隆项目
git clone https://github.com/bruceblink/news-analytics.git
cd nts-analytics

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
| `JWT_SECRET` | JWT 签名密钥（内部预留） | `change_me` |
| `CORS_ORIGINS` | 跨域白名单，分号分隔 | 空 |
| `TFIDF_MAX_FEATURES` | TF-IDF 最大词特征数 | `2000` |
| `STATIC_DIR` | 静态文件目录 | `static` |
| `WORDCLOUD_DIR` | 词云图片输出目录 | `static/wordclouds` |

## 主要 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查（供 Agora 保活使用） |
| POST | `/api/analysis/extract_news_item` | 从 news_info 提取清洗后的 news_item |
| POST | `/api/analysis/tfidf` | TF-IDF 关键词提取并写入 news_keywords |
| POST | `/api/analysis/extract_news_event` | 从 news_item 聚合事件到 news_event |
| POST | `/api/analysis/merge_event` | 合并近 N 天的跨天事件 |
| GET | `/api/analysis/events` | 新闻事件列表（分页、排序） |
| GET | `/api/analysis/events/{event_id}` | 新闻事件详情 |
| GET | `/api/analysis/wordcloud` | 生成词云图片并返回 URL |
| GET | `/api/news/{news_id}` | 新闻详情 |
| GET | `/api/news/{news_id}/related` | 相关新闻推荐 |
| GET | `/api/search/news?q=关键词` | 全文关键词搜索 |

完整交互文档：[Swagger UI](https://nts-analytics.onrender.com/docs)

## 部署

### Render（当前生产环境）

服务部署于 [Render](https://render.com)，Agora 通过 HTTP 定时触发分析接口。

### Docker Compose（本地开发）

```bash
# 复制并修改环境变量
cp .env.example .env

# 启动全部服务（PostgreSQL + App）
docker compose up -d
```

> 首次启动时 `postgres/init/` 下的 SQL 脚本会按文件名顺序自动执行，完成表结构初始化。

### Fly.io

```bash
fly deploy
```

配置见 `fly.toml`，数据库通过 `DATABASE_URL` Secret 注入。

## 演进路线

| 阶段 | 重点 |
|------|------|
| Phase 1（当前）| BFF 上线，接入 Agora 认证，打通 Feed 接口 |
| Phase 2 | 用户订阅系统，个性化 Feed 算法 |
| Phase 3 | Redis 缓存层（BFF 层），热点分析增强 |
| Phase 4 | 实时推送（WebSocket） |
| Phase 5 | Kafka 事件流，推荐系统 |

## License

MIT
