"""智服通 - API 鉴权中间件

简单 token 鉴权（管理接口）。演示环境默认放行，可配置开启。
"""

import time
from collections import defaultdict

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from ..core.config import get_settings
from ..core.logger import get_logger

logger = get_logger("middleware")


class TokenAuthMiddleware(BaseHTTPMiddleware):
    """管理接口鉴权。需请求头 X-Admin-Token 匹配 APP_SECRET。"""

    def __init__(
        self, app, *, admin_paths: tuple[str, ...] = ("/api/admin", "/api/kb")
    ):
        super().__init__(app)
        self.admin_paths = admin_paths
        self.secret = get_settings().app_secret

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if any(path.startswith(p) for p in self.admin_paths):
            token = request.headers.get("X-Admin-Token", "")
            if not self.secret or token != self.secret:
                logger.warning("auth rejected: %s", path)
                return JSONResponse(
                    status_code=401,
                    content={
                        "error": {"code": "SUPPORT_AUTH_FAIL", "message": "未授权访问"}
                    },
                )
        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """简单令牌桶限流（按客户端 IP）。"""

    def __init__(self, app, *, rate: int = 30, interval: float = 60.0):
        super().__init__(app)
        self.rate = rate
        self.interval = interval
        self._window: dict[str, list[float]] = defaultdict(list)
        self._lock = __import__("threading").Lock()

    async def dispatch(self, request: Request, call_next):
        # 只对写操作（chat、rebuild）限流
        if request.method in ("POST", "PUT", "DELETE"):
            ip = request.client.host if request.client else "unknown"
            now = time.monotonic()
            with self._lock:
                recent = [t for t in self._window[ip] if now - t < self.interval]
                if len(recent) >= self.rate:
                    return JSONResponse(
                        status_code=429,
                        content={
                            "error": {
                                "code": "SUPPORT_RATE_LIMIT",
                                "message": "请求过于频繁，请稍后再试",
                            }
                        },
                    )
                recent.append(now)
                self._window[ip] = recent
        return await call_next(request)


class LoggingMiddleware(BaseHTTPMiddleware):
    """请求日志。"""

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        duration = (time.perf_counter() - start) * 1000
        logger.info(
            "%s %s -> %d (%.1f ms)",
            request.method,
            request.url.path,
            response.status_code,
            duration,
        )
        return response
