# app/routers/__init__.py
"""
路由模块统一入口。
"""

from .analysis import router as analysis_router
from .stats import router as stats_router

__all__ = ["analysis_router", "stats_router"]
