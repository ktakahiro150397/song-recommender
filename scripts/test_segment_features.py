"""
Test script to segment audio, extract features, and register vectors in ChromaDB.

Usage:
    uv run scripts/test_segment_features.py <audio_path>

Example:
    uv run scripts/test_segment_features.py ./sample.mp3 --segment-seconds 5 --mode balanced
"""

import argparse
import sys
from pathlib import Path

import librosa

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.db_manager import SongVectorDB
from core.feature_extractor import FeatureExtractor, FeatureMode


def build_segment_id(filename: str, index: int) -> str:
    return f"{filename}::seg_{index:04d}"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Segment audio, extract features, and register vectors in ChromaDB"
    )
    parser.add_argument("audio_path", type=str, help="Path to an audio file")
    parser.add_argument(
        "--segment-seconds",
        type=float,
        default=5.0,
        help="Segment duration in seconds (default: 5)",
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["minimal", "balanced", "full"],
        default="balanced",
        help="Feature mode",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=None,
        help="Duration to load in seconds (None for full)",
    )
    parser.add_argument(
        "--collection",
        type=str,
        default=None,
        help="Target collection name (default: songs_segments_<mode>)",
    )
    parser.add_argument(
        "--include-in-search",
        action="store_true",
        help="Include in search (default: excluded)",
    )
    parser.add_argument(
        "--source-dir",
        type=str,
        default=None,
        help="Value for source_dir (default: parent directory)",
    )

    args = parser.parse_args()

    audio_path = Path(args.audio_path)
    if not audio_path.exists():
        print(f"ERROR: File not found: {audio_path}")
        sys.exit(1)

    segment_seconds = float(args.segment_seconds)
    if segment_seconds <= 0:
        print("ERROR: --segment-seconds must be positive")
        sys.exit(1)

    mode: FeatureMode = args.mode  # type: ignore
    collection_name = args.collection or f"songs_segments_{mode}"
    excluded_from_search = not args.include_in_search
    source_dir = args.source_dir or str(audio_path.parent)

    print("=" * 60)
    print("Segment feature test")
    print(f"   File: {audio_path}")
    print(f"   Segment seconds: {segment_seconds}")
    print(f"   Mode: {mode}")
    print(f"   Collection: {collection_name}")
    print("=" * 60)

    db = SongVectorDB(collection_name=collection_name, distance_fn="cosine")
    extractor = FeatureExtractor(duration=args.duration, mode=mode)

    vectors = extractor.extract_segments_to_vectors(
        audio_path, segment_seconds=segment_seconds, mode=mode
    )

    if not vectors:
        print("WARNING: No segments generated")
        return

    full_duration = float(librosa.get_duration(path=str(audio_path)))
    if args.duration is None:
        effective_duration = full_duration
    else:
        effective_duration = min(full_duration, float(args.duration))
    if effective_duration <= 0:
        effective_duration = segment_seconds * len(vectors)

    added = 0
    skipped = 0
    filename = audio_path.name

    for index, vector in enumerate(vectors):
        start_sec = index * segment_seconds
        end_sec = min(start_sec + segment_seconds, effective_duration)

        segment_id = build_segment_id(filename, index)
        if db.get_song(song_id=segment_id, include_embedding=False) is not None:
            skipped += 1
            continue

        metadata = {
            "segment_index": index,
            "segment_start_sec": round(start_sec, 3),
            "segment_end_sec": round(end_sec, 3),
            "segment_seconds": round(segment_seconds, 3),
            "source_song_id": filename,
            "source_path": str(audio_path),
            "mode": mode,
        }

        db.add_song(
            song_id=segment_id,
            embedding=vector,
            excluded_from_search=excluded_from_search,
            source_dir=source_dir,
            metadata=metadata,
        )
        added += 1

    print("=" * 60)
    print("Summary")
    print(f"   Added: {added}")
    print(f"   Skipped: {skipped}")
    print(f"   Total segments: {len(vectors)}")
    print("Done")


if __name__ == "__main__":
    main()
