"""智服通 - FastAPI 应用入口

- 注册 API 路由
- 全局限流 / 鉴权 / 日志中间件
- 全局异常处理（规范化错误响应）
- 服务端渲染客服界面（Jinja2）
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .api import admin, chat, history, kb
from .core.exceptions import SupportError
from .core.logger import get_logger
from .dialog.store import init_db
from .middleware.auth import LoggingMiddleware, RateLimitMiddleware, TokenAuthMiddleware

logger = get_logger("main")

BASE = Path(__file__).resolve().parent.parent  # backend/
TEMPLATES_DIR = BASE / "templates"
STATIC_DIR = TEMPLATES_DIR / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化数据库。"""
    init_db()
    logger.info("智服通 backend started")
    yield
    logger.info("智服通 backend stopped")


app = FastAPI(
    title="智服通 - 企业 IT 技术支持智能客服",
    description="基于 GLM + RAG 的企业 IT 智能客服系统",
    version="1.0.0",
    lifespan=lifespan,
)

# 中间件（后添加的先执行）
app.add_middleware(LoggingMiddleware)
app.add_middleware(RateLimitMiddleware, rate=30, interval=60.0)
app.add_middleware(TokenAuthMiddleware)

# 静态文件
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# --- 全局异常处理 ---
@app.exception_handler(SupportError)
async def support_error_handler(request: Request, exc: SupportError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {"code": exc.code, "message": exc.message},
            "detail": exc.detail,
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error("unhandled exception on %s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "SUPPORT_UNKNOWN",
                "message": "服务器开小差了，请稍后再试",
            }
        },
    )


# --- API 路由 ---
app.include_router(chat.router)
app.include_router(history.router)
app.include_router(kb.router)
app.include_router(admin.router)


# --- 页面（服务端渲染） ---
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {})


@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    from .core.config import get_settings

    ctx = {"app_secret": get_settings().app_secret}
    return templates.TemplateResponse(request, "admin.html", ctx)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "智服通"}
