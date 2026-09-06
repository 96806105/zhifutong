"""智服通 - LLM 客户端模块

基于 OpenAI 兼容接口封装智谱 GLM。
提供同步 chat 与流式 stream_chat 两种调用方式，统一异常处理。

多模型切换：可通过更换 base_url / api_key / model 接入任意
OpenAI 兼容服务（DeepSeek、通义、Ollama 本地等）。
"""

from collections.abc import Generator

from openai import OpenAI

from .config import get_settings
from .exceptions import LLMRateLimitError, LLMTimeoutError
from .logger import get_logger

logger = get_logger("llm")


class LLMClient:
    """大模型客户端（OpenAI 兼容）。"""

    def __init__(self) -> None:
        settings = get_settings()
        self._model = settings.llm_model
        self._temperature = settings.llm_temperature
        self._max_tokens = settings.llm_max_tokens
        self._timeout = settings.llm_timeout
        self._client = OpenAI(
            api_key=settings.zhipu_api_key,
            base_url=settings.zhipu_base_url,
            timeout=settings.llm_timeout,
        )

    @property
    def model(self) -> str:
        return self._model

    def chat(self, messages: list[dict]) -> str:
        """非流式调用，返回完整回答文本。"""
        logger.info("llm.chat non-stream, messages=%d", len(messages))
        try:
            resp = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=self._temperature,
                max_tokens=self._max_tokens,
            )
            content = resp.choices[0].message.content or ""
            return content
        except Exception as exc:  # noqa: BLE001 - 统一转换业务异常
            self._raise_llm_error(exc)

    def stream_chat(self, messages: list[dict]) -> Generator[str, None, None]:
        """流式调用，yield 增量文本。"""
        logger.info("llm.chat stream, messages=%d", len(messages))
        try:
            stream = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=self._temperature,
                max_tokens=self._max_tokens,
                stream=True,
            )
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as exc:  # noqa: BLE001
            self._raise_llm_error(exc)

    @staticmethod
    def _raise_llm_error(exc: Exception) -> None:
        """将底层异常转换为业务异常并抛出。"""
        name = type(exc).__name__
        text = str(exc)
        logger.error("llm call failed: %s: %s", name, text[:500])
        if "timed out" in text.lower() or "timeout" in name.lower():
            raise LLMTimeoutError(detail=text) from exc
        if "429" in text or "rate" in text.lower() or "balance" in text.lower():
            raise LLMRateLimitError(detail=text) from exc
        # 其他错误统一为限流/服务异常友好提示
        raise LLMRateLimitError(detail=text) from exc


_llm_client: LLMClient | None = None


def get_llm() -> LLMClient:
    """获取 LLM 客户端单例。"""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
