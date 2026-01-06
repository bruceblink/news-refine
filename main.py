import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import RedirectResponse

from app import settings
from app.middleware import JWTMiddleware
from app.routers import analysis, search, news

app = FastAPI(title="News Analytics API")

# 注册jwt提取的中间件
app.add_middleware(JWTMiddleware)
# 注册CORS白名单中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS, # 跨域白名单
    #allow_origin_regex=r"https://.*\.likanug\.top", # 跨域正则表达式
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 创建静态文件夹
os.makedirs(settings.WORDCLOUD_DIR, exist_ok=True)
# 挂载静态目录
app.mount("/static", StaticFiles(directory=settings.STATIC_DIR), name="static")

# include routers
app.include_router(analysis.router, tags=["分析模块"])
app.include_router(search.router, tags=["搜索模块"])
app.include_router(news.router, tags=["新闻模块"])


@app.get("/")
def root():
    return RedirectResponse(url="/docs")

@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
