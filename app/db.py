import logging
import re
import ssl
from typing import AsyncGenerator

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from .config import settings

# 获取日志器
logger = logging.getLogger(__name__)

DATABASE_URL = settings.DATABASE_URL
ENVIRONMENT = settings.ENVIRONMENT

connect_args = {}

if ENVIRONMENT.lower() in ["production", "prod"]:
    ssl_context = ssl.create_default_context()
    connect_args = {"ssl": ssl_context}
else:
    # 本地环境，不使用 SSL
    connect_args = {}


# --------------------------
# 3. 创建异步 Engine
# --------------------------
engine = create_async_engine(
    re.sub(r'^postgresql:', 'postgresql+asyncpg:', DATABASE_URL),
    # 根据环境决定是否打印SQL日志：开发/测试环境开启，生产环境关闭
    echo=ENVIRONMENT in ["development", "dev", "testing", "test", "staging", "local"],
    # 连接池配置：防止连接超时被服务器断开
    pool_recycle=300,           # 秒，连接在池中存活时间，应小于数据库的wait_timeout
    pool_pre_ping=True,         # 每次从池中取连接前执行简单SQL检查，确保连接有效
    pool_size=5,                # 连接池中保持的常驻连接数
    max_overflow=10,            # 超出pool_size后最多可创建的连接数
    pool_timeout=30,            # 秒，从池中获取连接的超时时间
    connect_args=connect_args
)

# 使用推荐的 async_sessionmaker 替代 sessionmaker
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False  # 避免在复杂事务中自动flush可能引起的混乱
)


# --------------------------
# 5. FastAPI 依赖注入函数
# --------------------------
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """异步生成器，提供数据库 session，增加错误处理和日志"""
    session = None
    try:
        async with AsyncSessionLocal() as session:
            logger.debug("Database session opened.")
            yield session
            # 在成功退出上下文管理器时，会自动commit或rollback
    except SQLAlchemyError as e:
        logger.error(f"Database session error: {e}", exc_info=True)
        # 如果会话在异常时仍然存在，尝试显式回滚
        if session and session.is_active:
            await session.rollback()
        # 将异常重新抛出，由上层（如FastAPI的异常处理器）处理
        raise
    finally:
        logger.debug("Database session closed.")