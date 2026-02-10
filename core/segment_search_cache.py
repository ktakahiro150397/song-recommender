"""
Segment search cache utilities.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Iterable

from sqlalchemy import select

from core.database import get_session
from core.models import SegmentSearchCache


def build_params_hash(params: dict) -> str:
    payload = json.dumps(params, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _serialize_results(results: Iterable[tuple[str, float, int, float, float]]) -> str:
    items = [
        {
            "song_id": song_id,
            "score": float(score),
            "count": int(count),
            "coverage": float(coverage),
            "density": float(density),
        }
        for song_id, score, count, coverage, density in results
    ]
    return json.dumps(items, ensure_ascii=True, separators=(",", ":"))


def _deserialize_results(
    payload: str,
) -> list[tuple[str, float, int, float, float]]:
    items = json.loads(payload)
    results: list[tuple[str, float, int, float, float]] = []
    for item in items:
        results.append(
            (
                item.get("song_id", ""),
                float(item.get("score", 0.0)),
                int(item.get("count", 0)),
                float(item.get("coverage", 0.0)),
                float(item.get("density", 0.0)),
            )
        )
    return results


def get_segment_search_cache(
    collection_name: str,
    song_id: str,
    params_hash: str,
) -> list[tuple[str, float, int, float, float]] | None:
    with get_session() as session:
        row = (
            session.execute(
                select(SegmentSearchCache).where(
                    SegmentSearchCache.collection_name == collection_name,
                    SegmentSearchCache.song_id == song_id,
                    SegmentSearchCache.params_hash == params_hash,
                )
            )
            .scalars()
            .first()
        )
        if not row:
            return None
        try:
            return _deserialize_results(row.results_json)
        except Exception:
            return None


def save_segment_search_cache(
    collection_name: str,
    song_id: str,
    params_hash: str,
    results: Iterable[tuple[str, float, int, float, float]],
) -> None:
    payload = _serialize_results(results)
    now = datetime.now()

    with get_session() as session:
        row = (
            session.execute(
                select(SegmentSearchCache).where(
                    SegmentSearchCache.collection_name == collection_name,
                    SegmentSearchCache.song_id == song_id,
                    SegmentSearchCache.params_hash == params_hash,
                )
            )
            .scalars()
            .first()
        )
        if row:
            row.results_json = payload
            row.updated_at = now
            if row.created_at is None:
                row.created_at = now
        else:
            session.add(
                SegmentSearchCache(
                    collection_name=collection_name,
                    song_id=song_id,
                    params_hash=params_hash,
                    results_json=payload,
                    created_at=now,
                    updated_at=now,
                )
            )
