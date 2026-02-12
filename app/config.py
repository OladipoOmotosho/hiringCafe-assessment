from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


def _env_path(name: str, default: str | None = None) -> Path | None:
    value = os.getenv(name)
    if value is None or not value.strip():
        if default is None:
            return None
        value = default
    path = Path(value)
    return path

@dataclass(frozen=True)
class Settings:
    data_dir: Path = Path(os.getenv("DATA_DIR", "data"))
    jobs_jsonl_path: Path | None = _env_path("JOBS_JSONL_PATH")
    db_path: Path = _env_path("DB_PATH", "data/jobs.duckdb") or Path("data/jobs.duckdb")
    index_path: Path = _env_path("INDEX_PATH", "data/faiss.index") or Path("data/faiss.index")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    batch_size: int = int(os.getenv("BATCH_SIZE", "500"))
    preview_chars: int = int(os.getenv("PREVIEW_CHARS", "280"))
    rebuild_index: bool = os.getenv("REBUILD_INDEX", "0") in {"1", "true", "TRUE", "yes", "YES"}

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.index_path.parent.mkdir(parents=True, exist_ok=True)


settings = Settings()