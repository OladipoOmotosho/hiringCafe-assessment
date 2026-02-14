from __future__ import annotations

import html
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, List, Tuple

import duckdb
import faiss
import numpy as np
from tqdm import tqdm

from app.config import settings

DIM = 1536
EXPLICIT_WEIGHT = 0.50
INFERRED_WEIGHT = 0.30
COMPANY_WEIGHT = 0.20

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class JobRow:
    """Normalized job row used for DuckDB storage and FAISS indexing."""

    row_index: int
    job_id: str
    title: str
    company: str
    location: str
    apply_url: str
    preview: str
    vector: np.ndarray


def _safe_get(dct: dict, *keys: str, default: str = "") -> str:
    """Return the first non-empty value from candidate keys."""
    for key in keys:
        value = dct.get(key)
        if value:
            return str(value)
    return default


def _deep_get(obj: object, path: Tuple[str, ...], default: str = "") -> str:
    """Resolve a nested path from a dict-like object."""
    cur: object = obj
    for key in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
    if cur is None:
        return default
    if isinstance(cur, (str, int, float)):
        return str(cur)
    return default


def _parse_preview(job: dict) -> str:
    """Extract and sanitize a short preview from raw job content."""
    job_info = job.get("job_information")
    if isinstance(job_info, dict):
        raw = _safe_get(job_info, "description", "description_html", "text", default="")
    else:
        raw = str(job_info or "")
    text = re.sub(r"<[^>]+>", " ", raw)
    text = html.unescape(text)
    return text[: settings.preview_chars].replace("\n", " ").strip()


def _merge_embedding(job: dict) -> np.ndarray:
    """Create a weighted embedding vector from explicit/inferred/company vectors."""
    v7 = job.get("v7_processed_job_data", {})
    explicit = np.array(v7.get("embedding_explicit_vector", []), dtype=np.float32)
    inferred = np.array(v7.get("embedding_inferred_vector", []), dtype=np.float32)
    company = np.array(v7.get("embedding_company_vector", []), dtype=np.float32)
    if explicit.size == DIM and inferred.size == DIM and company.size == DIM:
        vector = EXPLICIT_WEIGHT * explicit + INFERRED_WEIGHT * inferred + COMPANY_WEIGHT * company
        return vector.astype(np.float32)
    return np.zeros(DIM, dtype=np.float32)


def stream_jobs(path: Path) -> Iterator[JobRow]:
    """Yield normalized jobs from a JSONL file as a streaming iterator."""
    faiss_row_index = 0
    with path.open("r", encoding="utf-8") as handle:
        for line_index, line in enumerate(handle, start=1):
            job = json.loads(line)
            job_id = str(job.get("id", ""))
            v7_job = job.get("v7_processed_job_data") if isinstance(job.get("v7_processed_job_data"), dict) else {}
            v7_company = job.get("v5_processed_company_data") if isinstance(job.get("v5_processed_company_data"), dict) else {}
            job_info = job.get("job_information") if isinstance(job.get("job_information"), dict) else {}

            title = (
                _safe_get(job, "title", "job_title", default="")
                or _safe_get(v7_job, "title", "job_title", default="")
                or _safe_get(job_info, "title", default="")
            )
            company = (
                _safe_get(job, "company", "company_name", default="")
                or _safe_get(v7_company, "name", "company_name", default="")
                or _deep_get(job, ("v7_processed_job_data", "company_name"), default="")
            )
            location = (
                _safe_get(job, "location", "job_location", default="")
                or _safe_get(v7_job, "location", "job_location", "location_raw", default="")
                or _safe_get(job_info, "location", default="")
            )
            apply_url = _safe_get(job, "apply_url", default="")
            preview = _parse_preview(job)
            vector = _merge_embedding(job)
            if not job_id:
                logger.warning("Skipping row without job id at line=%d", line_index)
                continue
            yield JobRow(
                row_index=faiss_row_index,
                job_id=job_id,
                title=title,
                company=company,
                location=location,
                apply_url=apply_url,
                preview=preview,
                vector=vector,
            )
            faiss_row_index += 1


def init_db(conn: duckdb.DuckDBPyConnection) -> None:
    """Create the jobs table used by retrieval and ranking."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            row_index INTEGER,
            id TEXT,
            title TEXT,
            company TEXT,
            location TEXT,
            apply_url TEXT,
            preview TEXT
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_row_index ON jobs(row_index)")


def batch(iterable: Iterable[JobRow], size: int) -> Iterator[List[JobRow]]:
    """Yield fixed-size batches from a job iterator."""
    bucket: List[JobRow] = []
    for item in iterable:
        bucket.append(item)
        if len(bucket) >= size:
            yield bucket
            bucket = []
    if bucket:
        yield bucket


def build_index(force_rebuild: bool | None = None) -> None:
    """Build and persist DuckDB metadata and FAISS vector index artifacts."""
    settings.ensure_dirs()
    if settings.jobs_jsonl_path is None or not settings.jobs_jsonl_path.exists() or settings.jobs_jsonl_path.is_dir():
        raise FileNotFoundError("JOBS_JSONL_PATH must point to jobs.jsonl")

    should_rebuild = settings.rebuild_index if force_rebuild is None else force_rebuild

    if not should_rebuild and settings.db_path.exists() and settings.index_path.exists():
        logger.info("Using existing index artifacts db=%s index=%s", settings.db_path, settings.index_path)
        return

    conn = duckdb.connect(str(settings.db_path))
    conn.execute("DROP TABLE IF EXISTS jobs")
    init_db(conn)
    index = faiss.IndexFlatIP(DIM)

    rows_inserted = 0
    for chunk in tqdm(batch(stream_jobs(settings.jobs_jsonl_path), settings.batch_size), desc="Ingesting"):
        vectors = np.stack([row.vector for row in chunk])
        faiss.normalize_L2(vectors)
        index.add(vectors)
        conn.executemany(
            "INSERT INTO jobs VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (row.row_index, row.job_id, row.title, row.company, row.location, row.apply_url, row.preview)
                for row in chunk
            ],
        )
        rows_inserted += len(chunk)

    conn.commit()
    conn.close()
    faiss.write_index(index, str(settings.index_path))
    logger.info("Index build completed rows=%d db=%s index=%s", rows_inserted, settings.db_path, settings.index_path)


if __name__ == "__main__":
    build_index()