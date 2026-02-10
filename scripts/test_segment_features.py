"""
Test script to segment audio, extract features, and register vectors in ChromaDB.

Usage:
    uv run scripts/test_segment_features.py <audio_path>

Example:
    uv run scripts/test_segment_features.py ./sample.mp3 --segment-seconds 5 --mode balanced
"""

import argparse
import sys
from collections import Counter
from pathlib import Path

import librosa

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.db_manager import SongVectorDB
from core.feature_extractor import FeatureExtractor, FeatureMode


def build_segment_id(filename: str, index: int) -> str:
    return f"{filename}::seg_{index:04d}"


def get_audio_files_recursive(base_dir: Path) -> list[Path]:
    audio_files: list[Path] = []
    for path in base_dir.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".wav", ".mp3"}:
            audio_files.append(path)
    return audio_files


def fetch_segments_by_filename(
    db: SongVectorDB, filename: str
) -> list[tuple[str, list[float], dict]]:
    result = db.collection.get(  # type: ignore[attr-defined]
        where={"source_song_id": filename},
        include=["embeddings", "metadatas"],
    )

    segment_items: list[tuple[str, list[float], dict]] = []
    for seg_id, embedding, metadata in zip(
        result.get("ids", []),
        result.get("embeddings", []),
        result.get("metadatas", []),
    ):
        if embedding is None or metadata is None:
            continue
        segment_items.append((seg_id, embedding, metadata))

    segment_items.sort(key=lambda item: item[2].get("segment_index", 0))
    return segment_items


def filter_segments_for_search(
    segment_items: list[tuple[str, list[float], dict]],
    max_duration_sec: float,
    skip_initial_sec: float,
    skip_end_sec: float,
) -> list[tuple[str, list[float], dict]]:
    if max_duration_sec <= 0 and skip_initial_sec <= 0 and skip_end_sec <= 0:
        return segment_items

    max_end_sec = 0.0
    if skip_end_sec > 0:
        for _, _, metadata in segment_items:
            end_sec = metadata.get("segment_end_sec")
            if end_sec is None:
                continue
            max_end_sec = max(max_end_sec, float(end_sec))
        if max_end_sec <= 0:
            max_end_sec = 0.0

    filtered_items: list[tuple[str, list[float], dict]] = []
    for seg_id, embedding, metadata in segment_items:
        start_sec = metadata.get("segment_start_sec")
        end_sec = metadata.get("segment_end_sec")
        if start_sec is None:
            filtered_items.append((seg_id, embedding, metadata))
            continue
        start_sec = float(start_sec)
        if skip_end_sec > 0 and end_sec is not None and max_end_sec > 0:
            if float(end_sec) > max_end_sec - skip_end_sec:
                continue
        if skip_initial_sec > 0 and start_sec < skip_initial_sec:
            continue
        if max_duration_sec <= 0 or start_sec < max_duration_sec:
            filtered_items.append((seg_id, embedding, metadata))

    return filtered_items


def normalize_distance_score(distance: float, max_distance: float = 0.1) -> float:
    if distance <= 0:
        return 100.0
    if max_distance <= 0:
        return 0.0
    if distance >= max_distance:
        return 0.0
    return 100.0 * (1.0 - (distance / max_distance))


def print_similarity_results(
    db: SongVectorDB,
    segment_id: str,
    query_embedding: list[float],
    top_k: int,
    exclude_source_song_id: str | None = None,
) -> list[tuple[str, int, float]]:
    where_filter = None
    if exclude_source_song_id:
        where_filter = {"source_song_id": {"$ne": exclude_source_song_id}}

    results = db.search_similar(
        query_embedding=query_embedding, n_results=top_k + 1, where=where_filter
    )
    ids = results.get("ids", [[]])[0]
    distances = results.get("distances", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]

    filtered: list[tuple[str, float, dict | None]] = []
    for song_id, distance, metadata in zip(ids, distances, metadatas):
        if song_id == segment_id:
            continue
        filtered.append((song_id, distance, metadata))
        if len(filtered) >= top_k:
            break

    if not filtered:
        print("   No similar segments found")
        return []

    result_items: list[tuple[str, int, float]] = []
    for rank, (song_id, distance, metadata) in enumerate(filtered, start=1):
        print(f"   {rank:02d}. {song_id} | dist={distance:.6f}")
        # if metadata:
        #     print(f"       meta={metadata}")
        result_items.append((song_id, rank, float(distance)))

    return result_items


def process_audio_file(
    audio_path: Path,
    segment_seconds: float,
    mode: FeatureMode,
    collection_name: str,
    excluded_from_search: bool,
    source_dir: str | None,
    duration: float | None,
) -> tuple[int, int, int]:
    if not audio_path.exists():
        print(f"ERROR: File not found: {audio_path}")
        return 0, 0, 0

    print(f"\n[debug] Processing file: {audio_path}")
    db = SongVectorDB(collection_name=collection_name, distance_fn="cosine")
    extractor = FeatureExtractor(duration=duration, mode=mode)

    vectors = extractor.extract_segments_to_vectors(
        audio_path, segment_seconds=segment_seconds, mode=mode
    )

    if not vectors:
        print("WARNING: No segments generated")
        return 0, 0, 0

    full_duration = float(librosa.get_duration(path=str(audio_path)))
    if duration is None:
        effective_duration = full_duration
    else:
        effective_duration = min(full_duration, float(duration))
    if effective_duration <= 0:
        effective_duration = segment_seconds * len(vectors)

    added = 0
    skipped = 0
    filename = audio_path.name
    file_source_dir = source_dir or str(audio_path.parent)

    for index, vector in enumerate(vectors):
        start_sec = index * segment_seconds
        end_sec = min(start_sec + segment_seconds, effective_duration)

        print(
            f"[debug] Segment {index:04d} | {filename} | {start_sec:.3f}-{end_sec:.3f}s"
        )

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
            source_dir=file_source_dir,
            metadata=metadata,
        )
        added += 1

    return added, skipped, len(vectors)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Segment audio, extract features, and register vectors in ChromaDB"
    )
    parser.add_argument(
        "audio_path",
        type=str,
        nargs="?",
        help="Path to an audio file",
    )
    parser.add_argument(
        "--dir",
        type=str,
        default=None,
        help="Directory to scan recursively for audio files",
    )
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
    parser.add_argument(
        "--search-filename",
        type=str,
        default=None,
        help="Filename to load segments from collection and run similarity search",
    )
    parser.add_argument(
        "--search-collection",
        type=str,
        default=None,
        help="Collection name for search (default: same as --collection)",
    )
    parser.add_argument(
        "--search-topk",
        type=int,
        default=5,
        help="Top K similar segments to show (default: 5)",
    )
    parser.add_argument(
        "--search-max-seconds",
        type=float,
        default=120.0,
        help="Max seconds from start to include in search (default: 120)",
    )
    parser.add_argument(
        "--search-skip-seconds",
        type=float,
        default=10.0,
        help="Skip initial seconds in search (default: 10)",
    )
    parser.add_argument(
        "--search-skip-end-seconds",
        type=float,
        default=10.0,
        help="Skip ending seconds in search (default: 10)",
    )
    parser.add_argument(
        "--exclude-same-song",
        action="store_true",
        help="Exclude segments from the same source song in similarity search",
    )
    parser.add_argument(
        "--distance-max",
        type=float,
        default=0.1,
        help="Distance threshold for zero score (default: 0.1)",
    )

    args = parser.parse_args()

    if not args.audio_path and not args.dir and not args.search_filename:
        print("ERROR: Provide an audio_path, --dir, or --search-filename")
        sys.exit(1)

    segment_seconds = float(args.segment_seconds)
    if segment_seconds <= 0:
        print("ERROR: --segment-seconds must be positive")
        sys.exit(1)

    mode: FeatureMode = args.mode  # type: ignore
    collection_name = args.collection or f"songs_segments_{mode}"
    excluded_from_search = not args.include_in_search
    source_dir = args.source_dir

    if args.search_filename:
        search_collection = args.search_collection or collection_name
        db = SongVectorDB(collection_name=search_collection, distance_fn="cosine")
        segment_items = fetch_segments_by_filename(db, args.search_filename)
        segment_items = filter_segments_for_search(
            segment_items,
            max_duration_sec=float(args.search_max_seconds),
            skip_initial_sec=float(args.search_skip_seconds),
            skip_end_sec=float(args.search_skip_end_seconds),
        )
        if not segment_items:
            print(f"No segments found for filename: {args.search_filename}")
            return

        print("=" * 60)
        print("Segment similarity search")
        print(f"   Filename: {args.search_filename}")
        print(f"   Segments: {len(segment_items)}")
        print(f"   Mode: {mode}")
        print(f"   Collection: {search_collection}")
        print(f"   TopK: {args.search_topk}")
        print(f"   Max seconds: {args.search_max_seconds}")
        print("=" * 60)

        similar_id_counter: Counter[str] = Counter()
        similar_score_counter: Counter[str] = Counter()
        song_segment_hits: dict[str, set[int]] = {}
        song_density_hits: Counter[str] = Counter()
        rank_weights = None
        total_query_segments = len(segment_items)

        for seg_list_index, (seg_id, embedding, metadata) in enumerate(segment_items):
            seg_index = metadata.get("segment_index")
            start_sec = metadata.get("segment_start_sec")
            end_sec = metadata.get("segment_end_sec")
            print(f"\nSegment {seg_index:04d} | {seg_id} | {start_sec}-{end_sec}s")
            result_items = print_similarity_results(
                db=db,
                segment_id=seg_id,
                query_embedding=embedding,
                top_k=max(1, int(args.search_topk)),
                exclude_source_song_id=(
                    args.search_filename if args.exclude_same_song else None
                ),
            )
            for song_id, rank, distance in result_items:
                base_song_id = song_id.split("::", 1)[0]
                segment_key = (
                    int(seg_index) if isinstance(seg_index, int) else seg_list_index
                )
                song_segment_hits.setdefault(base_song_id, set()).add(segment_key)
                if distance < args.distance_max:
                    song_density_hits.update([base_song_id])
                similar_id_counter.update([song_id])
                weight = 1 if rank_weights is None else rank_weights.get(rank, 0)
                distance_score = normalize_distance_score(distance, args.distance_max)
                similar_score_counter[song_id] += weight * distance_score

        if similar_id_counter:
            song_counter: Counter[str] = Counter()
            song_score_counter: Counter[str] = Counter()
            for segment_id, count in similar_id_counter.items():
                song_id = segment_id.split("::", 1)[0]
                song_counter[song_id] += count

            for segment_id, score in similar_score_counter.items():
                song_id = segment_id.split("::", 1)[0]
                song_score_counter[song_id] += score

            print("\n" + "=" * 60)
            print(f"Aggregated similar songs : {args.search_filename}")

            final_score_map: dict[str, float] = {}
            normalized_topk = max(1, int(args.search_topk))
            for song_id in song_counter.keys():
                score = song_score_counter.get(song_id, 0.0)
                coverage_hits = len(song_segment_hits.get(song_id, set()))
                coverage = (
                    coverage_hits / total_query_segments
                    if total_query_segments > 0
                    else 0.0
                )
                density_hits = song_density_hits.get(song_id, 0)
                density_norm = (
                    density_hits / (total_query_segments * normalized_topk)
                    if total_query_segments > 0
                    else 0.0
                )
                final_score_map[song_id] = (
                    score * (0.5 + 0.5 * coverage) * (0.5 + 0.5 * density_norm)
                )

            sorted_songs = sorted(
                song_counter.keys(),
                key=lambda sid: (
                    final_score_map.get(sid, 0),
                    song_score_counter.get(sid, 0),
                    song_counter.get(sid, 0),
                ),
                reverse=True,
            )
            for song_id in sorted_songs:
                count = song_counter.get(song_id, 0)
                score = song_score_counter.get(song_id, 0.0)
                coverage_hits = len(song_segment_hits.get(song_id, set()))
                coverage = (
                    coverage_hits / total_query_segments
                    if total_query_segments > 0
                    else 0.0
                )
                density_hits = song_density_hits.get(song_id, 0)
                density_norm = (
                    density_hits / (total_query_segments * normalized_topk)
                    if total_query_segments > 0
                    else 0.0
                )
                final_score = final_score_map.get(song_id, 0.0)
                print(
                    f"   final={final_score:7.1f} | score={score:7.1f} | count={count:3d} | cov={coverage:0.2f} | den={density_norm:0.2f} | {song_id}"
                )
        return

    total_added = 0
    total_skipped = 0
    total_segments = 0

    if args.dir:
        base_dir = Path(args.dir)
        if not base_dir.exists():
            print(f"ERROR: Directory not found: {base_dir}")
            sys.exit(1)
        audio_files = get_audio_files_recursive(base_dir)
        if not audio_files:
            print("WARNING: No audio files found")
            return
    else:
        audio_files = [Path(args.audio_path)]

    print("=" * 60)
    print("Segment feature test")
    if args.dir:
        print(f"   Directory: {args.dir}")
        print(f"   Files: {len(audio_files)}")
    else:
        print(f"   File: {audio_files[0]}")
    print(f"   Segment seconds: {segment_seconds}")
    print(f"   Mode: {mode}")
    print(f"   Collection: {collection_name}")
    print("=" * 60)

    for audio_path in audio_files:
        added, skipped, segments = process_audio_file(
            audio_path=audio_path,
            segment_seconds=segment_seconds,
            mode=mode,
            collection_name=collection_name,
            excluded_from_search=excluded_from_search,
            source_dir=source_dir,
            duration=args.duration,
        )
        total_added += added
        total_skipped += skipped
        total_segments += segments

    print("=" * 60)
    print("Summary")
    print(f"   Added: {total_added}")
    print(f"   Skipped: {total_skipped}")
    print(f"   Total segments: {total_segments}")
    print("Done")


if __name__ == "__main__":
    main()
