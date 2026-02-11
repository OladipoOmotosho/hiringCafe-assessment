import os
import duckdb
import faiss
import json
import numpy as np
from app.config import settings

def main():
    jobs_jsonl_path = settings.JOBS_JSONL_PATH
    index_path = settings.index_path

    # Connect to DuckDB and create jobs table
    conn = duckdb.connect('jobs.db')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS jobs (
            row_index INTEGER,
            id TEXT,
            title TEXT,
            company TEXT,
            location TEXT,
            apply_url TEXT,
            preview TEXT
        )
    ''')

    embeddings = []
    job_records = []

    # Stream the jobs.jsonl file
    with open(jobs_jsonl_path, 'r') as file:
        for row_index, line in enumerate(file):
            job = json.loads(line)
            id = job['id']
            title = job['title']
            company = job['company']
            location = job['location']
            apply_url = job['apply_url']
            preview = job['preview']
            embedding = job.get('embedding', np.zeros(768))  # Example dimension for embeddings
            
            # Collect job metadata for batch insert
            job_records.append((row_index, id, title, company, location, apply_url, preview))
            embeddings.append(embedding)

    # Batch insert into DuckDB
    conn.executemany('INSERT INTO jobs VALUES (?, ?, ?, ?, ?, ?, ?)', job_records)

    # Build FAISS index
    embeddings = np.array(embeddings).astype('float32')  # Ensure correct dtype for FAISS
    index = faiss.IndexFlatL2(embeddings.shape[1])  # L2 distance
    index.add(embeddings)
    faiss.write_index(index, index_path)

if __name__ == "__main__":
    main()