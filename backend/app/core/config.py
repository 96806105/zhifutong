"""智服通 - 配置管理模块

基于 pydantic-settings 读取 .env 环境变量，提供类型安全配置。
所有密钥只从环境读取，禁止硬编码。

路径类配置支持相对路径，自动解析为基于项目根目录的绝对路径，
避免受进程启动目录影响（生产部署关键点）。
"""

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent

# 本地 embedding 离线加载（模型已缓存后不再尝试联网）
import os as _os

_hf_cache = BASE_DIR / "models" / "huggingface"
_os.environ.setdefault("HF_HOME", str(_hf_cache))
_os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", str(_hf_cache))
_os.environ.setdefault("HF_HUB_OFFLINE", "1")
_os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")


def _resolve(base: Path) -> Path:
    return base if base.is_absolute() else (BASE_DIR / base)


class Settings(BaseSettings):
    """全局配置。字段名对应 .env 中的变量名（大小写不敏感）。"""

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    # --- LLM（智谱 GLM，OpenAI 兼容接口）---
    zhipu_api_key: str = ""
    zhipu_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    llm_model: str = "glm-4-flash"
    llm_temperature: float = 0.3
    llm_max_tokens: int = 1024
    llm_timeout: float = 60.0

    # --- Embedding（本地模型，需下载一次，之后完全离线）---
    embedding_model: str = str(BASE_DIR / "models" / "bge-small-zh-v1.5")
    embedding_dim: int = 512
    hf_endpoint: str = "https://hf-mirror.com"

    # --- 服务器 ---
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_secret: str = "change_this_secret_key"
    app_debug: bool = True

    # --- 知识库 / 向量库 ---
    knowledge_base_dir: str = str(BASE_DIR / "knowledge_base")
    vector_store_dir: str = str(BASE_DIR / "data" / "chroma")
    chunk_size: int = 500
    chunk_overlap: int = 50
    top_k: int = 4

    # --- 检索阈值 ---
    retrieve_threshold: float = 0.45

    # --- 数据库 ---
    database_url: str = f"sqlite:///{BASE_DIR / 'data' / 'support.db'}"

    # --- 转人工 ---
    transfer_fail_threshold: int = 3

    # --- 会话 / 记忆 ---
    session_history_rounds: int = 6

    @field_validator("knowledge_base_dir", "vector_store_dir")
    @classmethod
    def _resolve_dir(cls, v: str) -> str:
        p = Path(v)
        return str(_resolve(p))

    @field_validator("embedding_model")
    @classmethod
    def _resolve_embedding(cls, v: str) -> str:
        # 若指向一个存在的本地目录则按相对项目根解析；repo id 保持原样
        p = Path(v)
        if v and "://" not in v and "/" in v or (p.exists()):
            resolved = _resolve(p)
            if resolved.exists():
                return str(resolved)
            return str(resolved)
        return v

    @field_validator("database_url")
    @classmethod
    def _resolve_db_url(cls, v: str) -> str:
        if v.startswith("sqlite:///"):
            raw = v[len("sqlite:///") :]
            if raw and not Path(raw).is_absolute():
                return "sqlite:///" + str(_resolve(Path(raw)))
        return v

    @property
    def knowledge_base_path(self) -> Path:
        return Path(self.knowledge_base_dir)

    @property
    def vector_store_path(self) -> Path:
        return Path(self.vector_store_dir)

    @property
    def llm_available(self) -> bool:
        return bool(self.zhipu_api_key)


@lru_cache
def get_settings() -> Settings:
    """获取全局配置单例。"""
    return Settings()
