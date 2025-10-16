from __future__ import annotations

import os
from dotenv import load_dotenv
from dataclasses import dataclass


# Load .env once at import
load_dotenv()


def _getenv(name: str, default: str | None = None) -> str | None:
    val = os.getenv(name)
    return val if val is not None and val != "" else default


@dataclass
class Settings:
    # Data paths
    PDF_SOURCE_DIR: str = _getenv("PDF_SOURCE_DIR", "training_data") or "training_data"
    CHROMA_PATH: str = _getenv("CHROMA_PATH", os.path.join("data", "chroma")) or os.path.join("data", "chroma")

    # Model runners
    LLM_RUNNER: str = _getenv("LLM_RUNNER", "lmstudio") or "lmstudio"
    LLM_BASE_URL: str = _getenv("LLM_BASE_URL", "http://localhost:1234") or "http://localhost:1234"

    EMBEDDINGS_PROVIDER: str = _getenv("EMBEDDINGS_PROVIDER", "lmstudio") or "lmstudio"
    EMBEDDINGS_BASE_URL: str = _getenv("EMBEDDINGS_BASE_URL", "http://localhost:1234") or "http://localhost:1234"
    EMBEDDINGS_MODEL_ID: str = _getenv("EMBEDDINGS_MODEL_ID", "text-embedding-qwen3-embedding-4b") or "text-embedding-qwen3-embedding-4b"

    # Optional VLM assist
    VLM_PROVIDER: str = _getenv("VLM_PROVIDER", "openai") or "openai"
    OPENAI_API_KEY: str | None = _getenv("OPENAI_API_KEY")
    VLM_MODEL_ID: str = _getenv("VLM_MODEL_ID", "gpt-5-mini") or "gpt-5-mini"
    OCR_VLM_ENABLED: bool = (_getenv("OCR_VLM_ENABLED", "true") or "true").lower() in {"1", "true", "yes", "on"}

    # Retrieval defaults
    TOP_K: int = int(_getenv("TOP_K", "8") or 8)
    SIMILARITY_THRESHOLD: float = float(_getenv("SIMILARITY_THRESHOLD", "0.7") or 0.7)


def get_settings() -> Settings:
    return Settings()
