"""
Register segment embeddings extracted by MERT into ChromaDB.

Usage:
    uv run scripts/register_segments_mert.py <audio_path>
    uv run scripts/register_segments_mert.py --dir <audio_dir>

Example:
    uv run scripts/register_segments_mert.py --dir "F:\\music" --segment-seconds 5
"""

import argparse
import re
import sys
from pathlib import Path

import torch
import torch.nn.functional as F

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.db_manager import SongVectorDB

try:
    import torchaudio
except Exception as exc:  # pragma: no cover
    raise RuntimeError(
        "torchaudio is required. Install torch/torchaudio with CUDA support."
    ) from exc

try:
    from transformers import AutoFeatureExtractor, AutoModel
except Exception as exc:  # pragma: no cover
    raise RuntimeError(
        "transformers is required. Install with: uv add transformers"
    ) from exc


def build_segment_id(filename: str, index: int) -> str:
    return f"{filename}::seg_{index:04d}"


def model_id_to_collection_suffix(model_id: str) -> str:
    cleaned = model_id.strip().lower()
    cleaned = cleaned.replace("/", "_")
    cleaned = re.sub(r"[^a-z0-9_]+", "_", cleaned)
    return cleaned.strip("_")


def get_audio_files_recursive(base_dir: Path) -> list[Path]:
    audio_files: list[Path] = []
    for path in base_dir.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".wav", ".mp3", ".flac", ".m4a"}:
            audio_files.append(path)
    return audio_files


def load_audio_mono(path: Path, target_sr: int) -> torch.Tensor:
    try:
        waveform, sr = torchaudio.load(str(path))
        if waveform.ndim == 2 and waveform.shape[0] > 1:
            waveform = waveform.mean(dim=0, keepdim=True)
        if sr != target_sr:
            waveform = torchaudio.functional.resample(waveform, sr, target_sr)
        return waveform.squeeze(0)
    except Exception:
        import librosa

        y, _ = librosa.load(str(path), sr=target_sr, mono=True)
        return torch.from_numpy(y)


def split_segments(
    waveform: torch.Tensor, segment_seconds: float, sr: int
) -> list[torch.Tensor]:
    segment_samples = int(round(segment_seconds * sr))
    if segment_samples <= 0:
        raise ValueError("segment_seconds is too small for the sampling rate")

    segments: list[torch.Tensor] = []
    for start in range(0, waveform.numel(), segment_samples):
        end = min(start + segment_samples, waveform.numel())
        segment = waveform[start:end]
        if segment.numel() == 0:
            continue
        segments.append(segment)
    return segments


def mean_pool(
    hidden: torch.Tensor, attention_mask: torch.Tensor | None
) -> torch.Tensor:
    if attention_mask is None:
        return hidden.mean(dim=1)
    mask = attention_mask.unsqueeze(-1).to(hidden.dtype)
    summed = (hidden * mask).sum(dim=1)
    denom = mask.sum(dim=1).clamp(min=1)
    return summed / denom


def infer_embeddings(
    model: torch.nn.Module,
    feature_extractor,
    segments: list[torch.Tensor],
    sr: int,
    device: torch.device,
    batch_size: int,
) -> list[list[float]]:
    embeddings: list[list[float]] = []
    model.eval()

    for i in range(0, len(segments), batch_size):
        batch = segments[i : i + batch_size]
        batch_np = [seg.cpu().numpy() for seg in batch]
        inputs = feature_extractor(
            batch_np, sampling_rate=sr, return_tensors="pt", padding=True
        )
        inputs = {k: v.to(device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = model(**inputs)

        hidden = outputs.last_hidden_state
        attention_mask = inputs.get("attention_mask")
        if attention_mask is not None and attention_mask.shape[1] != hidden.shape[1]:
            attention_mask = None
        pooled = mean_pool(hidden, attention_mask)
        pooled = F.normalize(pooled, p=2, dim=1)
        embeddings.extend(pooled.cpu().tolist())

    return embeddings


def add_embeddings_to_db(
    db: SongVectorDB,
    segment_items: list[tuple[str, list[float], dict]],
    excluded_from_search: bool,
    source_dir: str | None,
) -> int:
    if not segment_items:
        return 0

    ids = [item[0] for item in segment_items]
    embeddings = [item[1] for item in segment_items]
    metadatas = []
    for _, _, metadata in segment_items:
        base_metadata = {"excluded_from_search": excluded_from_search}
        if source_dir is not None:
            base_metadata["source_dir"] = source_dir
        base_metadata.update(metadata)
        metadatas.append(base_metadata)

    db.collection.add(ids=ids, embeddings=embeddings, metadatas=metadatas)  # type: ignore
    return len(ids)


def process_audio_file(
    audio_path: Path,
    segment_seconds: float,
    collection_name: str,
    excluded_from_search: bool,
    source_dir: str | None,
    model_name: str,
    batch_size: int,
    device: torch.device,
    feature_extractor,
    model: torch.nn.Module,
    target_sr: int,
) -> tuple[int, int]:
    if not audio_path.exists():
        print(f"ERROR: File not found: {audio_path}")
        return 0, 0

    print(f"\n[debug] Processing file: {audio_path}")
    db = SongVectorDB(collection_name=collection_name, distance_fn="cosine")

    waveform = load_audio_mono(audio_path, target_sr)
    segments = split_segments(waveform, segment_seconds, target_sr)
    if not segments:
        print("WARNING: No segments generated")
        return 0, 0

    total_duration = len(waveform) / target_sr
    print(
        f"[debug] Segments: {len(segments)} | duration={total_duration:.3f}s | sr={target_sr}"
    )

    embeddings = infer_embeddings(
        model=model,
        feature_extractor=feature_extractor,
        segments=segments,
        sr=target_sr,
        device=device,
        batch_size=batch_size,
    )

    filename = audio_path.name
    file_source_dir = source_dir or str(audio_path.parent)
    segment_items: list[tuple[str, list[float], dict]] = []
    skipped = 0

    for index, embedding in enumerate(embeddings):
        segment_id = build_segment_id(filename, index)
        if db.get_song(song_id=segment_id, include_embedding=False) is not None:
            skipped += 1
            continue

        start_sec = index * segment_seconds
        end_sec = min(start_sec + segment_seconds, len(waveform) / target_sr)
        print(
            f"[debug] Segment {index:04d} | {filename} | {start_sec:.3f}-{end_sec:.3f}s"
        )
        metadata = {
            "segment_index": index,
            "segment_start_sec": round(start_sec, 3),
            "segment_end_sec": round(end_sec, 3),
            "segment_seconds": round(segment_seconds, 3),
            "source_song_id": filename,
            "source_path": str(audio_path),
            "model": model_name,
        }
        segment_items.append((segment_id, embedding, metadata))

    added = add_embeddings_to_db(
        db=db,
        segment_items=segment_items,
        excluded_from_search=excluded_from_search,
        source_dir=file_source_dir,
    )

    print(f"[debug] Added: {added} | Skipped: {skipped}")

    return added, skipped


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract MERT embeddings on GPU and register segments in ChromaDB"
    )
    parser.add_argument("audio_path", type=str, nargs="?", help="Path to an audio file")
    parser.add_argument(
        "--dir", type=str, default=None, help="Directory to scan recursively"
    )
    parser.add_argument(
        "--segment-seconds",
        type=float,
        default=5.0,
        help="Segment duration in seconds (default: 5)",
    )
    parser.add_argument(
        "--collection",
        type=str,
        default=None,
        help="Target collection name (default: songs_segments_mert)",
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
        "--model",
        type=str,
        default="m-a-p/MERT-v1-95M",
        help="Hugging Face model id (default: m-a-p/MERT-v1-95M)",
    )
    parser.add_argument(
        "--batch-size", type=int, default=16, help="Batch size for inference"
    )
    parser.add_argument(
        "--device",
        type=str,
        default="auto",
        help="Device: auto, cuda, or cpu (default: auto)",
    )

    args = parser.parse_args()

    if not args.audio_path and not args.dir:
        print("ERROR: Provide an audio_path or --dir")
        sys.exit(1)

    segment_seconds = float(args.segment_seconds)
    if segment_seconds <= 0:
        print("ERROR: --segment-seconds must be positive")
        sys.exit(1)

    if args.device == "cuda" or (args.device == "auto" and torch.cuda.is_available()):
        device = torch.device("cuda")
    else:
        device = torch.device("cpu")

    model_suffix = model_id_to_collection_suffix(args.model)
    collection_name = args.collection or f"songs_segments_mert_{model_suffix}"
    excluded_from_search = not args.include_in_search
    source_dir = args.source_dir

    feature_extractor = AutoFeatureExtractor.from_pretrained(
        args.model, trust_remote_code=True
    )
    model = AutoModel.from_pretrained(args.model, trust_remote_code=True).to(device)
    target_sr = int(getattr(feature_extractor, "sampling_rate", 16000))

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
    print("MERT segment registration")
    if args.dir:
        print(f"   Directory: {args.dir}")
        print(f"   Files: {len(audio_files)}")
    else:
        print(f"   File: {audio_files[0]}")
    print(f"   Segment seconds: {segment_seconds}")
    print(f"   Collection: {collection_name}")
    print(f"   Model: {args.model}")
    print(f"   Device: {device}")
    print("=" * 60)

    total_added = 0
    total_skipped = 0

    for audio_path in audio_files:
        added, skipped = process_audio_file(
            audio_path=Path(audio_path),
            segment_seconds=segment_seconds,
            collection_name=collection_name,
            excluded_from_search=excluded_from_search,
            source_dir=source_dir,
            model_name=args.model,
            batch_size=max(1, int(args.batch_size)),
            device=device,
            feature_extractor=feature_extractor,
            model=model,
            target_sr=target_sr,
        )
        total_added += added
        total_skipped += skipped

    print("\nDone")
    print(f"   Added: {total_added}")
    print(f"   Skipped: {total_skipped}")


if __name__ == "__main__":
    main()
