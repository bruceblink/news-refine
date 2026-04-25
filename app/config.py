import os

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 环境判断
    ENVIRONMENT: str = os.getenv("APP_ENV", "production")
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:myapp123@postgres:5432/newsletter",
    )
    STATIC_DIR: str = os.getenv("STATIC_DIR", "static")
    WORDCLOUD_DIR: str = os.getenv(
        "WORDCLOUD_DIR", os.path.join(STATIC_DIR, "wordclouds")
    )
    TFIDF_MAX_FEATURES: int = int(os.getenv("TFIDF_MAX_FEATURES", "1000"))
    # 项目根目录
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # 跨域请求白名单
    CORS_ORIGINS: list[str] = [
        origin for origin in
        (os.getenv("FRONTEND_DOMAINS") or os.getenv("CORS_ORIGINS") or "").split(';')
        if origin
    ]
    # 停词表文件
    STOPWORDS_FILE: str = os.path.join(BASE_DIR, "chinese_stopwords.txt")


settings = Settings()
