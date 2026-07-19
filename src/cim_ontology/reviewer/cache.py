"""LLM 响应 SQLite 缓存（设计规范 §5.7）。"""
from __future__ import annotations

import sqlite3
from pathlib import Path


_SCHEMA = """
CREATE TABLE IF NOT EXISTS llm_reviews (
    case_id TEXT PRIMARY KEY,
    response TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""


class LLMCache:
    """基于 SQLite 的 LLM 响应缓存。"""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._path) as conn:
            conn.execute(_SCHEMA)
            conn.commit()

    def get(self, case_id: str) -> str | None:
        """获取缓存的响应。"""
        with sqlite3.connect(self._path) as conn:
            row = conn.execute(
                "SELECT response FROM llm_reviews WHERE case_id = ?", (case_id,)
            ).fetchone()
            return row[0] if row else None

    def put(self, case_id: str, response: str) -> None:
        """存储响应。"""
        with sqlite3.connect(self._path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO llm_reviews (case_id, response) VALUES (?, ?)",
                (case_id, response),
            )
            conn.commit()