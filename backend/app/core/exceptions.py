"""智服通 - 业务异常体系

统一错误码，便于接口规范化返回与前端处理。
"""


class SupportError(Exception):
    """业务异常基类。"""

    status_code = 500
    code = "SUPPORT_UNKNOWN"
    message = "服务内部错误，请稍后再试"

    def __init__(self, message: str | None = None, *, detail: str | None = None):
        self.message = message or self.message
        self.detail = detail
        super().__init__(self.message)


class LLMTimeoutError(SupportError):
    """LLM 调用超时。"""

    status_code = 503
    code = "SUPPORT_LLM_TIMEOUT"
    message = "智能服务响应超时，请稍后重试"


class LLMRateLimitError(SupportError):
    """LLM 限流 / 余额不足。"""

    status_code = 503
    code = "SUPPORT_LLM_LIMIT"
    message = "智能服务当前负载较高或额度不足，请稍后再试"


class RetrieveError(SupportError):
    """检索失败。"""

    status_code = 500
    code = "SUPPORT_RETRIEVE_FAIL"
    message = "知识检索服务异常，请稍后再试"


class ParamError(SupportError):
    """参数校验失败。"""

    status_code = 400
    code = "SUPPORT_PARAM_ERROR"
    message = "请求参数不合法"


class AuthError(SupportError):
    """鉴权失败。"""

    status_code = 401
    code = "SUPPORT_AUTH_FAIL"
    message = "未授权访问"
