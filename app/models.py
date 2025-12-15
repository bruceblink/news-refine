from sqlalchemy import Table, Column, BigInteger, String, Date, Text, TIMESTAMP, MetaData, ForeignKey, JSON, \
    UniqueConstraint, Boolean, Float, Integer
from sqlalchemy.sql import func

metadata = MetaData()

news_info = Table(
    "news_info",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("name", String(50), nullable=False),
    Column("news_from", String(50), nullable=False),
    Column("news_date", Date, nullable=False),
    Column("data", JSON),
    Column("created_at", TIMESTAMP(timezone=True)),
    Column("updated_at", TIMESTAMP(timezone=True)),
    Column("extracted", Boolean, nullable=False, server_default="false"),
    Column("extracted_at", TIMESTAMP(timezone=True), nullable=True),
    Column("error", Text, nullable=True),
    UniqueConstraint("news_from", "news_date", name="uniq_news_info")
)

news_item = Table(
    "news_item",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("item_id", Text, nullable=False),
    Column("news_info_id", BigInteger, ForeignKey("news_info.id", ondelete="CASCADE")),
    Column("title", Text, nullable=False),
    Column("url", Text, nullable=False),
    Column("published_at", Date),
    Column("source", String(50)),
    Column("content", Text),
    Column("cluster_method", Text, nullable=True),
    Column("cluster_id", BigInteger, nullable=True),

    # ⭐ 新增字段
    Column("extracted", Boolean, nullable=False, server_default="false"),
    Column("extracted_at", TIMESTAMP(timezone=True), nullable=True),

    Column("created_at", TIMESTAMP(timezone=True), server_default=func.current_timestamp()),
    Column("updated_at", TIMESTAMP(timezone=True), server_default=func.current_timestamp()),
    UniqueConstraint("item_id", "published_at", name="uq_news_date"),
)

news_keywords = Table(
    "news_keywords",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("news_id",BigInteger,ForeignKey("news_item.id", ondelete="CASCADE"),nullable=False,),
    Column("keyword", Text, nullable=False),
    Column("weight", Float, nullable=True),
    Column("method", Text, nullable=False),
    Column("created_at",TIMESTAMP(timezone=True),server_default=func.current_timestamp(),nullable=False),
    Column("updated_at",TIMESTAMP(timezone=True),server_default=func.current_timestamp(),nullable=False),
    UniqueConstraint("news_id", "keyword", "method", name="uq_news_keywords"),
)

news_event = Table(
    "news_event",
    metadata,
    Column("id", BigInteger, primary_key=True),
    Column("event_date", Date),
    Column("cluster_id", BigInteger),
    Column("title", Text, nullable=False),
    Column("summary", Text, nullable=False),
    Column("news_count", Integer),
    Column("score", Float),
    Column("status", Integer),
    Column("parent_event_id", BigInteger, ForeignKey("news_event.id"), nullable=True),
    Column("created_at", TIMESTAMP(timezone=True)),
    Column("updated_at", TIMESTAMP(timezone=True)),
)

news_event_item = Table(
    "news_event_item",
    metadata,
    Column("event_id", BigInteger),
    Column("news_id", BigInteger),
)