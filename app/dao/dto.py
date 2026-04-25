from datetime import date, datetime
from typing import Any, Iterator

from pydantic import BaseModel, ConfigDict, field_validator


class RowModel(BaseModel):
    model_config = ConfigDict(extra="ignore")

    def __getitem__(self, key: str):
        return getattr(self, key)

    def get(self, key: str, default=None):
        return getattr(self, key, default)

    def keys(self):
        return self.model_fields.keys()

    def items(self):
        return self.model_dump().items()

    def __iter__(self) -> Iterator[tuple[str, Any]]:
        yield from self.model_dump().items()


class NewsKeywordsDTO(RowModel):
    news_id: int
    keyword: str
    weight: float
    method: str


class NewsItemDTO(RowModel):
    id: int
    title: str | None
    url: str | None
    source: str | None
    published_at: str | None
    score: float

    @field_validator("published_at", mode="before")
    @classmethod
    def _published_at_to_str(cls, v):
        if isinstance(v, (date, datetime)):
            return v.isoformat()
        return v


class NewsInfoRowDTO(RowModel):
    id: int
    name: str | None
    news_from: str
    news_date: date | None
    data: Any
    extracted: bool | None
    error: str | None


class NewsInfoDetailDTO(RowModel):
    id: int
    name: str | None
    news_from: str
    news_date: str | None
    data: Any
    extracted: bool | None
    error: str | None

    @field_validator("news_date", mode="before")
    @classmethod
    def _news_date_to_str(cls, v):
        if isinstance(v, (date, datetime)):
            return v.isoformat()
        return v


class NewsItemExtractDTO(RowModel):
    id: int
    title: str | None
    url: str | None
    published_at: str | None
    source: str | None
    content: str | None

    @field_validator("published_at", mode="before")
    @classmethod
    def _published_at_to_str(cls, v):
        if isinstance(v, (date, datetime)):
            return v.isoformat()
        return v


class NewsItemDetailDTO(RowModel):
    id: int
    news_info_id: int | None
    title: str | None
    url: str | None
    published_at: str | None
    source: str | None
    content: str | None

    @field_validator("published_at", mode="before")
    @classmethod
    def _published_at_to_str(cls, v):
        if isinstance(v, (date, datetime)):
            return v.isoformat()
        return v


class NewsEventDTO(RowModel):
    id: int
    event_date: date | None
    title: str | None
    summary: str | None
    news_count: int | None
    score: float | None
    status: int | None


class NewsEventRecordDTO(RowModel):
    id: int
    event_date: date | None
    cluster_id: int | None
    title: str | None
    summary: str | None
    news_count: int | None
    score: float | None
    status: int | None
    parent_event_id: int | None


class NewsItemInEventDTO(RowModel):
    id: int
    title: str | None
    source: str | None
    published_at: date | None
    url: str | None


class HotEventDTO(RowModel):
    id: int
    event_date: date | None
    title: str | None
    summary: str | None
    news_count: int | None
    score: float | None


class TopNewsItemDTO(RowModel):
    id: int
    title: str | None
    source: str | None
    published_at: str | None
    url: str | None

    @field_validator("published_at", mode="before")
    @classmethod
    def _published_at_to_str(cls, v):
        if isinstance(v, (date, datetime)):
            return v.isoformat()
        return v


class DayTrendKeywordDTO(RowModel):
    keyword: str
    weight: float
    count: int


class DayTrendDTO(RowModel):
    date: str
    keywords: list[DayTrendKeywordDTO]
