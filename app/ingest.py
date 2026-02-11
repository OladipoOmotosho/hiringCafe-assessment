from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, List, Tuple

import duckdb
import faiss
import numpy as np
from tqdm import tqdm

from app.config import settings

DIM = 1536

@dataclass(frozen=True)
class JobRow:
    row_index: int
    job_id: str
    title: str
    company: str
    location: str
    apply_url: str
    preview: str
    vector: np.ndarray

def _safe_get(dct: dict, *keys: str, default: str = "") -> str:
    for key in keys:
        value = dct.get(key)
        if value:
            return str(value)
    return default

def _parse_preview(job: dict) -> str:
    raw = _safe_get(job, "job_information", default="")
    return raw[: settings.preview_chars].replace("\n", " ").strip()

def _merge_embedding(job: dict) -> np.ndarray:
    v7 = job.get("v7_processed_job_data", {})
    explicit = np.array(v7.get("embedding_explicit_vector", []), dtype=np.float32)
    inferred = np.array(v7.get("embedding_inferred_vector", []), dtype=np.float32)
    company = np.array(v7.get("embedding_company_vector", []), dtype=np.float32)
    if explicit.size == DIM and inferred.size == DIM and company.size == DIM:
        vector = 0.5 * explicit + 0.3 * inferred + 0.2 * company
        return vector.astype(np.float32)
    return np.zeros(DIM, dtype=np.float32)

def stream_jobs(path: Path) -> Iterator[JobRow]:
    with path.open("r", encoding="utf-8") as handle:
        for row_index, line in enumerate(handle):
            job = json.loads(line)
            job_id = str(job.get("id", ""))
            title = _safe_get(job, "title", default=_safe_get(job, "job_title"))
            company = _safe_get(job, "company", default=_safe_get(job, "company_name"))
            location = _safe_get(job, "location", default=_safe_get(job, "job_location"))
            apply_url = _safe_get(job, "apply_url", default="")
            preview = _parse_preview(job)
            vector = _merge_embedding(job)
            if not job_id:
                continue
            yield JobRow(
                row_index=row_index,
                job_id=job_id,
                title=title,
                company=company,
                location=location,
                apply_url=apply_url,
                preview=preview,
                vector=vector,
            )

def init_db(conn: duckdb.DuckDBPyConnection) -> None:
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

def batch(iterable: Iterable[JobRow], size: int) -> Iterator[List[JobRow]]:
    bucket: List[JobRow] = []
    for item in iterable:
        bucket.append(item)
        if len(bucket) >= size:
            yield bucket
            bucket = []
    if bucket:
        yield bucket

def build_index() -> None:
    settings.ensure_dirs()
    if not settings.jobs_jsonl_path or not settings.jobs_jsonl_path.exists():
        raise FileNotFoundError("JOBS_JSONL_PATH must point to jobs.jsonl")

    conn = duckdb.connect(str(settings.db_path))
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


if __name__ == "__main__":
    build_index()