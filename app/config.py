from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class Settings:
    data_dir: Path = Path(os.getenv("DATA_DIR", "data"))
    jobs_jsonl_path: Path = Path(os.getenv("JOBS_JSONL_PATH", ""))
    db_path: Path = Path(os.getenv("DB_PATH", "data/jobs.duckdb"))
    index_path: Path = Path(os.getenv("INDEX_PATH", "data/faiss.index"))
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    batch_size: int = int(os.getenv("BATCH_SIZE", "500"))
    preview_chars: int = int(os.getenv("PREVIEW_CHARS", "280"))

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()