"""
音声ファイルをベクトルDBに登録するスクリプト

使い方:
    uv run register_songs.py                  # バッチ処理（デフォルト）
    uv run register_songs.py --youtube-queue  # YouTubeキューから処理

バッチ処理により、複数曲を一括でDBに登録することでネットワークリクエスト回数を削減し、
リモートChromaDBへの登録速度を大幅に改善します。
"""

import argparse
import os
import re
import signal
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.db_manager import SongVectorDB
from core.feature_extractor import FeatureExtractor
from core.song_queue_db import SongQueueDB
from core import song_metadata_db
from config import DB_CONFIGS

# グローバル変数：中断フラグ
_interrupted = False
_processing_count = 0
_total_files = 0

# ========== 定数設定 ==========

# 登録対象のディレクトリ
SOUND_DIRS = [
    # "data/scsp_mv",
    # "data/gakumas_mv",
    r"F:\song-recommender-data\data\ALSTROEMERIA",
    # "F:/million",
]

# 音声抽出設定
DURATION = 90  # 秒

# バッチ処理設定
BATCH_SIZE = 500  # 一度に登録する曲数（ChromaDBへの操作回数を削減）

# セグメント登録設定
SEGMENT_SECONDS = 5.0
SEGMENT_BATCH_SIZE = 16
SEGMENT_MODELS = [
    {
        "collection": "songs_segments_mert",
        "model": "m-a-p/MERT-v1-95M",
    },
    {
        "collection": "songs_segments_ast",
        "model": "MIT/ast-finetuned-audioset-10-10-0.4593",
    },
]


def clear_segment_search_cache() -> None:
    from core.database import get_session
    from sqlalchemy import text

    with get_session() as session:
        session.execute(
            text("DELETE FROM song_recommender.segment_search_cache WHERE id <> 0;")
        )
        session.commit()


# ========== シグナルハンドラ ==========


def signal_handler(sig, frame):
    """Ctrl+C (SIGINT) を捕捉して安全に終了する"""
    global _interrupted
    if not _interrupted:
        _interrupted = True
        print("\n\n⚠️  中断リクエストを受信しました...")
        print(
            f"   現在処理中のファイルが完了したら終了します ({_processing_count}/{_total_files})"
        )
        print("   もう一度 Ctrl+C を押すと強制終了します\n")
    else:
        print("\n🛑 強制終了します...")
        sys.exit(1)


# ========== ヘルパー関数 ==========


def extract_youtube_id(filename: str) -> str | None:
    """
    ファイル名からYouTube動画IDを抽出する
    例: "曲名 [abcd1234XYZ].mp3" → "abcd1234XYZ"
    """
    match = re.search(r"\[([a-zA-Z0-9_-]{11})\]", filename)
    return match.group(1) if match else None


def extract_song_title(filename: str) -> str:
    """
    ファイル名から曲名を抽出する

    優先順位:
    1. 「」（カギ括弧）で囲われている → 最初の「」の中身
    2. 【】（すみカッコ）がある場合 → 【】で囲われていない部分を抽出
    3. 上記に該当しない → [videoId]と拡張子、()を除去した文字列

    例:
        '初星学園 「Star-mine」Official Music Video [xxx].wav' → 'Star-mine'
        '【学園アイドルマスター MV】光景【学マス】 [xxx].wav' → '光景'
        '【シャニソン】白瀬 咲耶「千夜アリア」3DMV [xxx].wav' → '千夜アリア'
        'traveling [abc123XYZ].wav' → 'traveling'
    """
    # 1. 「」（カギ括弧）を優先チェック
    kakko_match = re.search(r"「(.+?)」", filename)
    if kakko_match:
        return kakko_match.group(1).strip()

    # 2. 【】（すみカッコ）がある場合、その外側の文字列を抽出
    if "【" in filename and "】" in filename:
        # [videoId] と拡張子を先に除去
        temp = re.sub(r"\s*\[[a-zA-Z0-9_-]{11}\]\.(wav|mp3)$", "", filename)
        # 【...】を除去
        temp = re.sub(r"【[^】]*】", "", temp)
        # ()（丸括弧）と（）（全角丸括弧）を除去
        temp = re.sub(r"[\(（][^\)）]*[\)）]", "", temp)
        # 余分な空白を整理
        temp = re.sub(r"\s+", " ", temp).strip()
        if temp:
            return temp

    # 3. 従来のロジック: [videoId] と拡張子を除去
    # [videoId].ext パターンを除去
    temp = re.sub(r"\s*\[[a-zA-Z0-9_-]{11}\]\.(wav|mp3)$", "", filename)
    # [videoId] のみ（拡張子なし）のパターンも除去
    temp = re.sub(r"\s*\[[a-zA-Z0-9_-]{11}\]$", "", temp)
    # 拡張子のみの場合も除去
    temp = re.sub(r"\.(wav|mp3)$", "", temp)
    # ()（丸括弧）と（）（全角丸括弧）を除去
    temp = re.sub(r"[\(（][^\)）]*[\)）]", "", temp)
    # 余分な空白を整理
    temp = re.sub(r"\s+", " ", temp).strip()

    return temp if temp else filename


def normalize_data_path(path: str) -> str | None:
    """
    パスを正規化し、data/配下の相対パスを返す（data/は除く）
    data/配下でない場合はNoneを返す

    例:
        "data/utada" → "utada"
        "F:/xxx/data/million" → "million"
        "F:/xxx/data/gakumas_mv/sub" → "gakumas_mv/sub"
        "F:/million" → None（data/配下ではない）
    """
    # パス区切りを統一（/ に）
    normalized = path.replace("\\", "/")

    # "data/" を含むかチェック
    data_idx = normalized.find("data/")
    if data_idx == -1:
        # data/xxx 形式ではない（例: "F:/million"）
        return None

    # data/ 以降を抽出し、data/ 自体は除く
    relative_path = normalized[data_idx + 5 :]  # "data/" の5文字分をスキップ
    return relative_path if relative_path else None


def get_audio_files_recursive(base_dir: str) -> list[tuple[str, str, str]]:
    """
    指定ディレクトリ配下の音声ファイルを再帰的に取得する

    Args:
        base_dir: ベースディレクトリ（例: "F:/song-recommender-data/data"）

    Returns:
        (実際のファイルパス, ファイル名, 正規化されたディレクトリ) のリスト
    """
    results = []

    for root, dirs, files in os.walk(base_dir):
        # 音声ファイルをフィルタ
        audio_files = [f for f in files if f.endswith((".wav", ".mp3"))]

        if not audio_files:
            continue

        # このディレクトリの正規化パス
        normalized_dir = normalize_data_path(root)
        if normalized_dir is None:
            continue

        for filename in audio_files:
            file_path = os.path.join(root, filename)
            results.append((file_path, filename, normalized_dir))

    return results


def get_file_size_mb(file_path: str) -> float:
    """ファイルサイズをMB単位で取得"""
    try:
        size_bytes = os.path.getsize(file_path)
        return round(size_bytes / (1024 * 1024), 2)
    except OSError:
        return 0.0


@dataclass
class SegmentModel:
    collection: str
    model_id: str
    db: SongVectorDB
    feature_extractor: object
    model: object
    target_sr: int
    device: object


def _load_segment_packages():
    try:
        import torch
        import torch.nn.functional as F
        import torchaudio
        from transformers import AutoFeatureExtractor, AutoModel
    except Exception as exc:
        raise RuntimeError(
            "Segment registration requires torch, torchaudio, and transformers. "
            "Install CUDA-enabled torch/torchaudio and transformers."
        ) from exc

    return torch, F, torchaudio, AutoFeatureExtractor, AutoModel


def _load_audio_mono(path: Path, target_sr: int) -> "torch.Tensor":
    torch, _, torchaudio, _, _ = _load_segment_packages()
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


def _split_segments(
    waveform: "torch.Tensor",
    segment_seconds: float,
    sr: int,
    min_samples: int = 1,
) -> list["torch.Tensor"]:
    segment_samples = int(round(segment_seconds * sr))
    if segment_samples <= 0:
        raise ValueError("segment_seconds is too small for the sampling rate")
    if min_samples < 1:
        min_samples = 1

    segments: list["torch.Tensor"] = []
    for start in range(0, waveform.numel(), segment_samples):
        end = min(start + segment_samples, waveform.numel())
        segment = waveform[start:end]
        if segment.numel() < min_samples:
            continue
        segments.append(segment)
    return segments


def _mean_pool(
    hidden: "torch.Tensor", attention_mask: Optional["torch.Tensor"]
) -> "torch.Tensor":
    if attention_mask is None:
        return hidden.mean(dim=1)
    mask = attention_mask.unsqueeze(-1).to(hidden.dtype)
    summed = (hidden * mask).sum(dim=1)
    denom = mask.sum(dim=1).clamp(min=1)
    return summed / denom


def _infer_segment_embeddings(
    model: object,
    feature_extractor: object,
    segments: list["torch.Tensor"],
    sr: int,
    device: "torch.device",
    batch_size: int,
) -> list[list[float]]:
    torch, F, _, _, _ = _load_segment_packages()
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
        pooled = _mean_pool(hidden, attention_mask)
        pooled = F.normalize(pooled, p=2, dim=1)
        embeddings.extend(pooled.cpu().tolist())

    return embeddings


def _build_segment_id(filename: str, index: int) -> str:
    return f"{filename}::seg_{index:04d}"


def _get_chroma_max_batch_size(db: SongVectorDB, default: int = 5000) -> int:
    try:
        max_size = db.client.get_max_batch_size()
        if isinstance(max_size, int) and max_size > 0:
            return max_size
    except Exception:
        pass
    try:
        max_size = db.collection._client.get_max_batch_size()  # type: ignore[attr-defined]
        if isinstance(max_size, int) and max_size > 0:
            return max_size
    except Exception:
        pass
    return default


def _get_chroma_safe_batch_size(
    db: SongVectorDB, margin: float = 0.9, default: int = 5000
) -> int:
    max_size = _get_chroma_max_batch_size(db, default=default)
    safe_size = int(max_size * margin)
    return max(safe_size, 1)


def _add_segment_embeddings_to_db(
    db: SongVectorDB,
    segment_items: list[tuple[str, list[float], dict]],
    source_dir: str | None,
) -> int:
    if not segment_items:
        return 0

    ids = [item[0] for item in segment_items]
    embeddings = [item[1] for item in segment_items]
    metadatas = []
    for _, _, metadata in segment_items:
        base_metadata = {"excluded_from_search": False}
        if source_dir is not None:
            base_metadata["source_dir"] = source_dir
        base_metadata.update(metadata)
        metadatas.append(base_metadata)

    db.collection.add(ids=ids, embeddings=embeddings, metadatas=metadatas)  # type: ignore
    return len(ids)


def init_segment_models(device_preference: str = "auto") -> list[SegmentModel]:
    torch, _, _, AutoFeatureExtractor, AutoModel = _load_segment_packages()

    if device_preference == "cuda" or (
        device_preference == "auto" and torch.cuda.is_available()
    ):
        device = torch.device("cuda")
    else:
        device = torch.device("cpu")

    segment_models: list[SegmentModel] = []
    for config in SEGMENT_MODELS:
        feature_extractor = AutoFeatureExtractor.from_pretrained(
            config["model"], trust_remote_code=True
        )
        model = AutoModel.from_pretrained(config["model"], trust_remote_code=True).to(
            device
        )
        target_sr = int(getattr(feature_extractor, "sampling_rate", 16000))
        db = SongVectorDB(collection_name=config["collection"], distance_fn="cosine")
        segment_models.append(
            SegmentModel(
                collection=config["collection"],
                model_id=config["model"],
                db=db,
                feature_extractor=feature_extractor,
                model=model,
                target_sr=target_sr,
                device=device,
            )
        )

    return segment_models


def register_segments_for_file(
    file_path: str,
    filename: str,
    normalized_dir: str,
    segment_models: list[SegmentModel],
    segment_seconds: float = SEGMENT_SECONDS,
    processed_collections: set[str] | None = None,
    waveform_cache: dict[int, tuple[object, int]] | None = None,
) -> dict[str, list[tuple[str, list[float], dict]]] | None:
    """
    1曲分のセグメントを準備する（バッチ処理用）

    Args:
        waveform_cache: {target_sr: (waveform, sr)} のキャッシュ辞書（任意）

    Returns:
        {collection_name: [(segment_id, embedding, metadata), ...]} の辞書
        または処理不要の場合はNone
    """
    if not segment_models:
        return None

    # バッチで処理済みチェック（効率化）
    if processed_collections is None:
        processed_collections = set(
            song_metadata_db.get_processed_collections(filename)
        )

    # 全モデルで処理済みなら早期リターン
    all_processed = all(
        seg_model.collection in processed_collections for seg_model in segment_models
    )
    if all_processed:
        return None  # 何も出力せず静かにスキップ

    # 少なくとも1つのモデルで未処理がある場合のみファイルチェック
    audio_path = Path(file_path)
    if not audio_path.exists():
        print(f"   ⚠️  セグメント登録スキップ: {file_path} が見つかりません")
        return None

    result: dict[str, list[tuple[str, list[float], dict]]] = {}

    for segment_model in segment_models:
        # MySQLで処理済みチェック
        if segment_model.collection in processed_collections:
            continue

        # キャッシュから波形データを取得、なければロード
        if waveform_cache is not None and segment_model.target_sr in waveform_cache:
            waveform = waveform_cache[segment_model.target_sr][0]
        else:
            waveform = _load_audio_mono(audio_path, segment_model.target_sr)
            # キャッシュに保存（次のモデルで再利用）
            if waveform_cache is not None:
                waveform_cache[segment_model.target_sr] = (
                    waveform,
                    segment_model.target_sr,
                )

        min_samples = 1
        win_length = getattr(segment_model.feature_extractor, "win_length", None)
        n_fft = getattr(segment_model.feature_extractor, "n_fft", None)
        if isinstance(win_length, int) and win_length > 1:
            min_samples = win_length
        elif isinstance(n_fft, int) and n_fft > 1:
            min_samples = n_fft

        segments = _split_segments(
            waveform,
            segment_seconds,
            segment_model.target_sr,
            min_samples=min_samples,
        )
        if not segments:
            print(f"   ⚠️  セグメントが生成できません: {filename}")
            continue

        embeddings = _infer_segment_embeddings(
            model=segment_model.model,
            feature_extractor=segment_model.feature_extractor,
            segments=segments,
            sr=segment_model.target_sr,
            device=segment_model.device,
            batch_size=SEGMENT_BATCH_SIZE,
        )

        total_duration = len(waveform) / segment_model.target_sr
        segment_items: list[tuple[str, list[float], dict]] = []
        for index, embedding in enumerate(embeddings):
            start_sec = index * segment_seconds
            end_sec = min(start_sec + segment_seconds, total_duration)
            metadata = {
                "segment_index": index,
                "segment_start_sec": round(start_sec, 3),
                "segment_end_sec": round(end_sec, 3),
                "segment_seconds": round(segment_seconds, 3),
                "source_song_id": filename,
                "source_path": str(audio_path),
                "model": segment_model.model_id,
            }
            segment_items.append(
                (_build_segment_id(filename, index), embedding, metadata)
            )

        result[segment_model.collection] = segment_items

    return result if result else None


def download_youtube_audio(video_id: str, output_dir: str) -> tuple[bool, str, str]:
    """
    yt-dlpを使用してYouTube動画から音声をダウンロード

    Args:
        video_id: YouTube動画ID
        output_dir: 出力ディレクトリ

    Returns:
        (成功フラグ, メッセージ, ダウンロードしたファイルパス)
    """
    try:
        # yt-dlpコマンドを構築
        output_template = os.path.join(output_dir, f"%(title)s [{video_id}].%(ext)s")
        cmd = [
            "yt-dlp",
            "-x",  # 音声のみ抽出
            "--audio-format",
            "wav",  # WAV形式で保存
            "--audio-quality",
            "0",  # 最高品質
            "-o",
            output_template,
            f"https://www.youtube.com/watch?v={video_id}",
        ]

        # ダウンロード実行
        result = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", timeout=300
        )

        if result.returncode != 0:
            return False, f"ダウンロードエラー: {result.stderr}", ""

        # ダウンロードされたファイルを探す（ブラケット付きのvideo_idを含むファイル）
        downloaded_files = [
            f
            for f in Path(output_dir).glob("*")
            if f.is_file() and f"[{video_id}]" in f.name
        ]

        if not downloaded_files:
            return False, "ダウンロードしたファイルが見つかりません", ""

        file_path = str(downloaded_files[0])
        return True, "ダウンロード成功", file_path

    except subprocess.TimeoutExpired:
        return (
            False,
            "ダウンロードがタイムアウトしました（5分以内に完了しませんでした）",
            "",
        )
    except FileNotFoundError:
        return (
            False,
            "yt-dlpが見つかりません。インストールされているか確認してください",
            "",
        )
    except Exception as e:
        return False, f"予期しないエラー: {str(e)}", ""


def process_youtube_queue(parallel_mode: str = "none") -> None:
    """
    YouTubeキューDBから未処理の曲をダウンロード・登録する

    Args:
        parallel_mode: 並列処理モード（none/thread/process）
    """
    print("=" * 60)
    print("🎵 YouTubeキューから音声ファイルをダウンロード・登録")
    print(f"   並列モード: {parallel_mode}")
    print("=" * 60)

    # キューDBを初期化
    print("\n🔌 YouTubeキューDB接続中...")
    try:
        queue_db = SongQueueDB()
        print("✅ YouTubeキューDB接続成功")
    except Exception as e:
        print(f"❌ YouTubeキューDB接続エラー: {str(e)}")
        raise

    print("📝 未処理の曲を取得中...")
    pending_songs = queue_db.get_pending_songs()
    print(f"✅ 取得完了")

    if not pending_songs:
        print("\n未処理の曲はありません")
        return

    print(f"\n未処理の曲: {len(pending_songs)}件\n")

    # ベクトルDBを初期化
    print("📊 ベクトルDBを初期化中...")
    dbs_and_extractors = []
    for config in DB_CONFIGS:
        print(f"   🔌 DB接続開始: {config['collection']} (mode={config['mode']})")
        try:
            db = SongVectorDB(
                collection_name=config["collection"], distance_fn="cosine"
            )
            print(f"   ✅ DB接続成功: {config['collection']}")
            print(f"   🔧 特徴量抽出器を初期化中: mode={config['mode']}")
            extractor = FeatureExtractor(duration=DURATION, mode=config["mode"])
            print(f"   ✅ 特徴量抽出器初期化完了")
            dbs_and_extractors.append((db, extractor, config["mode"]))
            print(f"   📊 現在のDB曲数: {db.count()} 曲\n")
        except Exception as e:
            print(f"   ❌ DB初期化エラー: {config['collection']} - {str(e)}")
            raise

    print("📦 セグメントモデルを初期化中...")
    segment_models = init_segment_models()

    # 一時ディレクトリを作成
    temp_dir = tempfile.mkdtemp(prefix="youtube_audio_")
    print(f"\n   一時ディレクトリ: {temp_dir}\n")

    success_count = 0
    failed_count = 0

    # シグナルハンドラを設定
    global _interrupted, _processing_count, _total_files
    _interrupted = False
    _total_files = len(pending_songs)
    signal.signal(signal.SIGINT, signal_handler)

    try:
        for idx, song in enumerate(pending_songs, 1):
            # 中断フラグをチェック
            if _interrupted:
                print("\n⚠️  処理を中断しました")
                break

            _processing_count = idx
            video_id = song["video_id"]
            url = song["url"]

            print(f"[{idx}/{len(pending_songs)}] {video_id} - {url}")

            # ✅ YouTubeIDがDBに既に存在しているかをチェック
            existing = song_metadata_db.get_by_youtube_id(video_id)
            youtube_id_exists = existing is not None
            if youtube_id_exists:
                print(f"   ⏭️  YouTubeID ({video_id}) は既に登録済みです")
                print(f"      (既存ID: {existing['song_id']})")

            if youtube_id_exists:
                queue_db.mark_as_processed(video_id)
                success_count += 1
                print()
                continue

            # ダウンロード
            download_success, download_msg, file_path = download_youtube_audio(
                video_id, temp_dir
            )

            if not download_success:
                print(f"   ❌ ダウンロード失敗: {download_msg}")
                queue_db.mark_as_failed(video_id)
                failed_count += 1
                continue

            print(f"   ✅ ダウンロード成功: {os.path.basename(file_path)}")

            # ベクトルDBに登録
            try:
                filename = os.path.basename(file_path)
                # song_queueに保存されたメタデータを使用
                normalized_dir = song.get("source_dir", "youtube")
                artist_name = song.get("artist_name")
                song_title = song.get("title")

                registered = False
                mysql_already_stored = False
                current_bpm = None
                for idx, (db, extractor, mode) in enumerate(dbs_and_extractors):
                    # 各DBに対して、そのDB用の抽出器で特徴量を抽出
                    success, emb, bpm = add_song(
                        db,
                        extractor,
                        file_path,
                        filename,
                        normalized_dir,
                        embedding=None,  # 各DB登録時に新たに抽出
                        artist_name=artist_name if not mysql_already_stored else None,
                        song_title_override=(
                            song_title if not mysql_already_stored else None
                        ),
                        skip_mysql=mysql_already_stored,
                        bpm=current_bpm,
                    )
                    if success:
                        registered = True
                        mysql_already_stored = True
                        if bpm is not None and current_bpm is None:
                            current_bpm = bpm

                # セグメントDB登録
                try:
                    segment_result = register_segments_for_file(
                        file_path=file_path,
                        filename=filename,
                        normalized_dir=normalized_dir,
                        segment_models=segment_models,
                        segment_seconds=SEGMENT_SECONDS,
                    )

                    # YouTubeの場合は1曲ずつ処理するので、結果があればすぐに追加
                    if segment_result:
                        for segment_model in segment_models:
                            collection_name = segment_model.collection
                            segment_items = segment_result.get(collection_name, [])

                            if segment_items:
                                added = _add_segment_embeddings_to_db(
                                    db=segment_model.db,
                                    segment_items=segment_items,
                                    source_dir=normalized_dir,
                                )
                                if added > 0:
                                    song_metadata_db.mark_as_processed(
                                        filename, collection_name
                                    )
                                    print(
                                        f"   ✅ {collection_name}: {added}セグメント登録"
                                    )
                except Exception as e:
                    print(f"   ⚠️  セグメント登録エラー: {str(e)}")

                if registered:
                    print(f"   ✅ DB登録成功 (3DBに登録)")
                    queue_db.mark_as_processed(video_id)
                    success_count += 1
                else:
                    print(f"   ⚠️  既に登録済み")
                    queue_db.mark_as_processed(video_id)
                    success_count += 1

            except Exception as e:
                print(f"   ❌ DB登録失敗: {str(e)}")
                queue_db.mark_as_failed(video_id)
                failed_count += 1

            # ダウンロードしたファイルを削除
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                print(f"   ⚠️  ファイル削除エラー: {str(e)}")

            print()

    finally:
        # シグナルハンドラをリセット
        signal.signal(signal.SIGINT, signal.SIG_DFL)

        # 一時ディレクトリを削除
        try:
            import shutil

            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception as e:
            print(f"⚠️  一時ディレクトリ削除エラー: {str(e)}")

    print("\n🧹 セグメント検索キャッシュをクリア中...")
    try:
        clear_segment_search_cache()
        print("✅ セグメント検索キャッシュをクリアしました")
    except Exception as e:
        print(f"⚠️  キャッシュクリア失敗: {str(e)}")

    # 結果サマリー
    print("=" * 60)
    print("📊 結果サマリー")
    print("=" * 60)
    print(f"   成功: {success_count} 曲")
    print(f"   失敗: {failed_count} 曲")
    if _interrupted:
        print(f"   中断: {len(pending_songs) - _processing_count} 曲（未処理）")

    for db, _, mode in dbs_and_extractors:
        print(f"   DB ({mode}): {db.count()} 曲")
    for segment_model in segment_models:
        print(f"   DB ({segment_model.collection}): {segment_model.db.count()} 曲")

    if _interrupted:
        print("\n⚠️  処理が中断されました")
    else:
        print("\n✅ 完了！")


# ========== メイン関数 ==========


def add_song(
    db: SongVectorDB,
    extractor: FeatureExtractor,
    file_path: str,
    filename: str,
    normalized_dir: str,
    embedding: list[float] | None = None,
    artist_name: str | None = None,
    song_title_override: str | None = None,
    skip_mysql: bool = False,
    bpm: float | None = None,
) -> tuple[bool, list[float] | None, float | None]:
    """
    1曲をDBに登録する

    Args:
        db: ベクトルDB
        extractor: 特徴量抽出器
        file_path: 実際のファイルパス
        filename: ファイル名
        normalized_dir: 正規化されたディレクトリパス（data/を除いた形式）
        embedding: 特徴量ベクトル（複数DB登録時は1度だけ抽出するため、の二度目以降に指定）
        artist_name: アーティスト名（任意）
        song_title_override: 曲名上書き（任意）
        skip_mysql: MySQLへの登録をスキップするか（複数DB登録時、2番目以降のDBではTrue）
        bpm: BPM（テンポ）

    Returns:
        (登録したらTrue、embeddingベクトル、BPM) のタプル
    """
    # 対象の拡張子のみ処理
    if not (filename.endswith(".wav") or filename.endswith(".mp3")):
        return False, None, None

    collection_name = db.collection.name

    # ステップ1: MySQLメタデータの確認と登録（最初のDB登録時のみ）
    metadata_exists = False
    if not skip_mysql:
        existing_song = song_metadata_db.get_song(song_id=filename)
        if existing_song is not None:
            metadata_exists = True
            # 既存のBPMを取得
            if bpm is None and existing_song.get("bpm") is not None:
                bpm = existing_song["bpm"]
        else:
            # YouTube IDによる重複チェック
            youtube_id = extract_youtube_id(filename)
            if youtube_id:
                existing = song_metadata_db.get_by_youtube_id(youtube_id)
                if existing:
                    return False, None, None

            # メタデータがない場合は登録
            # BPMを抽出（まだ抽出されていない場合）
            if bpm is None:
                try:
                    features = extractor.extract(file_path)
                    bpm = features.tempo
                except Exception as e:
                    print(f"   ⚠️  BPM抽出エラー ({filename}): {str(e)}")
                    bpm = None

            song_title = (
                song_title_override
                if song_title_override
                else extract_song_title(filename)
            )
            _, ext = os.path.splitext(filename)

            # artist_nameが指定されていない場合は、normalized_dirを使用
            if artist_name is None:
                artist_name = normalized_dir

            song_metadata_db.add_song(
                song_id=filename,
                filename=filename,
                song_title=song_title,
                artist_name=artist_name,
                source_dir=normalized_dir,
                youtube_id=youtube_id if youtube_id is not None else "",
                file_extension=ext.lower(),
                file_size_mb=get_file_size_mb(file_path),
                bpm=bpm,
                excluded_from_search=False,
            )
            metadata_exists = True
    else:
        metadata_exists = True  # skip_mysqlの場合は既に存在すると仮定

    # ステップ2: ベクトルDBの処理済みチェック
    if song_metadata_db.is_processed(song_id=filename, collection_name=collection_name):
        return False, None, bpm

    # ステップ3: 特徴量抽出（必要な場合）
    if embedding is None:
        try:
            embedding = extractor.extract_to_vector(file_path)
        except Exception as e:
            print(f"   ❌ 特徴量抽出エラー ({filename}): {str(e)}")
            raise

    # ステップ4: ChromaDBへのベクトル登録
    db.add_song(
        song_id=filename,
        embedding=embedding,
        excluded_from_search=False,
        source_dir=normalized_dir,
    )

    # 処理済みコレクションとしてマーク
    song_metadata_db.mark_as_processed(
        song_id=filename, collection_name=collection_name
    )

    return True, embedding, bpm


def prepare_song_data(
    extractor: FeatureExtractor,
    file_path: str,
    filename: str,
    normalized_dir: str,
    artist_name: str | None = None,
    song_title_override: str | None = None,
    waveform: tuple[object, int] | None = None,
) -> tuple[str, list[float], str, str, str, str, float, float | None] | None:
    """
    1曲分のデータを準備する（バッチ処理用）

    Args:
        extractor: 特徴量抽出器
        file_path: 実際のファイルパス
        filename: ファイル名
        normalized_dir: 正規化されたディレクトリパス
        artist_name: アーティスト名（任意）
        song_title_override: 曲名上書き（任意）
        waveform: 既にロード済みの波形データ (y, sr) のタプル（任意）

    Returns:
        (song_id, embedding, song_title, artist_name, youtube_id, file_extension, file_size_mb, bpm) のタプル、
        または処理不要の場合はNone
    """
    # 対象の拡張子のみ処理
    if not (filename.endswith(".wav") or filename.endswith(".mp3")):
        return None

    # 特徴量抽出
    try:
        if waveform is not None:
            # 波形データから直接抽出（ファイル読み込みなし）
            y, sr = waveform
            features = extractor.extract_from_waveform(y, sr)
            embedding = features.to_vector(extractor.mode)
            bpm = features.tempo
        else:
            # ファイルから読み込む
            features = extractor.extract(file_path)
            embedding = features.to_vector(extractor.mode)
            bpm = features.tempo
    except Exception as e:
        print(f"   ❌ 特徴量抽出エラー ({filename}): {str(e)}")
        return None

    # メタデータ構築
    youtube_id = extract_youtube_id(filename)
    song_title = (
        song_title_override if song_title_override else extract_song_title(filename)
    )
    _, ext = os.path.splitext(filename)

    # artist_nameが指定されていない場合は、normalized_dirを使用
    if artist_name is None:
        artist_name = normalized_dir

    return (
        filename,  # song_id
        embedding,
        song_title,
        artist_name,
        youtube_id if youtube_id is not None else "",
        ext.lower(),
        get_file_size_mb(file_path),
        bpm,
    )


def add_songs_batch(
    db: SongVectorDB,
    song_data_list: list[
        tuple[str, list[float], str, str, str, str, float, float | None]
    ],
    normalized_dir: str,
    skip_mysql: bool = False,
) -> int:
    """
    複数の曲を一括でDBに登録する（バルクインサート）

    Args:
        db: ベクトルDB
        song_data_list: (song_id, embedding, song_title, artist_name, youtube_id, file_extension, file_size_mb, bpm) のリスト
        normalized_dir: 正規化されたディレクトリパス
        skip_mysql: MySQLへの登録をスキップするか（複数DB登録時、最初のDB以外ではTrue）

    Returns:
        登録した曲数
    """
    if not song_data_list:
        return 0

    song_ids = [data[0] for data in song_data_list]
    embeddings = [data[1] for data in song_data_list]
    collection_name = db.collection.name

    # MySQLにメタデータを一括登録（最初のDB登録でのみ）
    if not skip_mysql:
        from core.database import get_session
        from core.models import Song
        from sqlalchemy import delete

        # 既存レコードを先に削除（重複を避けるため）
        with get_session() as session:
            session.execute(delete(Song).where(Song.song_id.in_(song_ids)))
            session.commit()

        # 新しいレコードを挿入
        songs = []
        for data in song_data_list:
            (
                song_id,
                _,
                song_title,
                artist_name,
                youtube_id,
                file_extension,
                file_size_mb,
                bpm,
            ) = data
            songs.append(
                Song(
                    song_id=song_id,
                    filename=song_id,
                    song_title=song_title,
                    artist_name=artist_name,
                    source_dir=normalized_dir,
                    youtube_id=youtube_id,
                    file_extension=file_extension,
                    file_size_mb=file_size_mb,
                    bpm=bpm,
                    registered_at=datetime.now(),
                    excluded_from_search=False,
                )
            )

        with get_session() as session:
            session.bulk_save_objects(songs)

    # ProcessedCollectionは各DB登録時に記録
    from core.database import get_session
    from core.models import ProcessedCollection

    processed_records = [
        ProcessedCollection(
            song_id=song_id,
            collection_name=collection_name,
            processed_at=datetime.now(),
        )
        for song_id in song_ids
    ]

    with get_session() as session:
        session.bulk_save_objects(processed_records)

    # ChromaDBには最小限のデータのみ保存
    excluded_flags = [False] * len(song_ids)
    source_dirs = [normalized_dir] * len(song_ids)
    db.add_songs(song_ids, embeddings, excluded_flags, source_dirs)

    return len(song_data_list)


def process_single_db(args: tuple) -> bool:
    """
    ProcessPoolExecutor用：1つのDBに対して特徴量抽出＆登録を行う
    （プロセス間でオブジェクトを渡せないため、引数から再構築）

    Args:
        args: (db_config, file_path, filename, normalized_dir, duration)
    """
    db_config, file_path, filename, normalized_dir, duration = args

    # プロセス内でDB・Extractorを初期化
    try:
        db = SongVectorDB(collection_name=db_config["collection"], distance_fn="cosine")
        extractor = FeatureExtractor(duration=duration, mode=db_config["mode"])
    except Exception as e:
        print(f"❌ プロセス内DB初期化エラー ({db_config['collection']}): {str(e)}")
        raise

    return add_song(db, extractor, file_path, filename, normalized_dir)


def main():
    # 引数パーサー
    parser = argparse.ArgumentParser(description="音声ファイルをベクトルDBに登録")
    parser.add_argument(
        "--parallel",
        "-p",
        type=str,
        choices=["none", "thread", "process"],
        default="none",
        help="並列処理モード: none(直列), thread(ThreadPool), process(ProcessPool) - 現在は使用されていません（後方互換性のため残しています）",
    )
    parser.add_argument(
        "--youtube-queue",
        "-y",
        action="store_true",
        help="YouTubeキューDBから未処理の曲をダウンロード・登録する",
    )
    args = parser.parse_args()

    # YouTubeキューモードの場合
    if args.youtube_queue:
        process_youtube_queue(parallel_mode=args.parallel)
        return

    print("=" * 60)
    print("🎵 音声ファイルをベクトルDBに登録")

    chroma_probe = SongVectorDB(
        collection_name=DB_CONFIGS[0]["collection"], distance_fn="cosine"
    )
    chroma_max_batch = _get_chroma_max_batch_size(chroma_probe)
    chroma_safe_batch = _get_chroma_safe_batch_size(chroma_probe)
    if BATCH_SIZE > chroma_safe_batch:
        print(
            f"   ⚠️  バッチサイズ上限を適用: {BATCH_SIZE} → {chroma_safe_batch}"
        )
    batch_size = min(BATCH_SIZE, chroma_safe_batch)

    print(f"   ChromaDB max batch size: {chroma_max_batch}")
    print(f"   バッチサイズ: {batch_size} 曲/バッチ（音声ファイル1回読み込み最適化）")
    print("=" * 60)

    # DB・抽出器を初期化
    print("\n📊 ベクトルDBを初期化中...")
    dbs_and_extractors = []
    for config in DB_CONFIGS:
        print(f"   🔌 DB接続開始: {config['collection']} (mode={config['mode']})")
        try:
            db = SongVectorDB(
                collection_name=config["collection"], distance_fn="cosine"
            )
            print(f"   ✅ DB接続成功: {config['collection']}")
            print(f"   🔧 特徴量抽出器を初期化中: mode={config['mode']}")
            extractor = FeatureExtractor(duration=DURATION, mode=config["mode"])
            print(f"   ✅ 特徴量抽出器初期化完了")
            dbs_and_extractors.append((db, extractor, config["mode"]))
            print(f"   📊 現在のDB曲数: {db.count()} 曲\n")
        except Exception as e:
            print(f"   ❌ DB初期化エラー: {config['collection']} - {str(e)}")
            raise

    print("📦 セグメントモデルを初期化中...")
    segment_models = init_segment_models()

    print()

    total_added = 0
    total_skipped = 0

    # シグナルハンドラを設定
    global _interrupted, _processing_count, _total_files
    _interrupted = False
    signal.signal(signal.SIGINT, signal_handler)

    try:
        for sound_dir in SOUND_DIRS:
            # data/配下でないパスはスキップ
            if normalize_data_path(sound_dir) is None:
                print(f"⚠️  Skipping {sound_dir}, not under data/ directory.")
                continue

            if not os.path.exists(sound_dir):
                print(f"⚠️  Skipping {sound_dir}, directory not found.")
                continue

            print(f"\n--- Processing directory: {sound_dir} (recursive) ---")

            # 再帰的に音声ファイルを取得
            audio_files = get_audio_files_recursive(sound_dir)
            print(f"    Found {len(audio_files)} audio files")

            current_dir = None
            _total_files = len(audio_files)

            # バッチ処理用の一時リスト
            batch_files = []

            for idx, (file_path, filename, normalized_dir) in enumerate(audio_files, 1):
                # 中断フラグをチェック
                if _interrupted:
                    print("\n⚠️  処理を中断しました")
                    break

                _processing_count = idx

                # ディレクトリが変わったら表示
                if normalized_dir != current_dir:
                    current_dir = normalized_dir
                    print(f"\n    📁 {normalized_dir}/")

                batch_files.append((file_path, filename, normalized_dir))

                # バッチサイズに達したか、最後のファイルの場合に処理
                if len(batch_files) >= batch_size or idx == len(audio_files):
                    # バッチ内で重複ファイル名を除外（最初の出現のみ保持）
                    seen_filenames = set()
                    unique_batch_files = []
                    duplicate_count = 0
                    for file_path, filename, normalized_dir in batch_files:
                        if filename not in seen_filenames:
                            seen_filenames.add(filename)
                            unique_batch_files.append(
                                (file_path, filename, normalized_dir)
                            )
                        else:
                            duplicate_count += 1

                    if duplicate_count > 0:
                        print(
                            f"    ℹ️  バッチ内の重複ファイルをスキップ: {duplicate_count} 件"
                        )

                    batch_files = unique_batch_files

                    # バッチ内のファイル名リストを取得
                    batch_filenames = [f[1] for f in batch_files]

                    # 既存チェック（バルククエリ、エラー時はフォールバック）
                    try:
                        existing_result = dbs_and_extractors[0][0].get_songs(
                            batch_filenames, include_embedding=False
                        )
                        existing_ids = set(existing_result.get("ids", []))
                    except Exception as e:
                        # 重複IDエラーやその他のエラーが発生した場合は空としてスキップ
                        print(f"    ⚠️  既存チェックエラー（処理継続）: {str(e)}")
                        existing_ids = set()

                    # 未登録のファイルのみ処理
                    files_to_process = [
                        f for f in batch_files if f[1] not in existing_ids
                    ]

                    skipped_count = len(batch_files) - len(files_to_process)
                    total_skipped += skipped_count

                    if files_to_process:
                        print(
                            f"    バッチ処理中... ({len(files_to_process)} 曲、{skipped_count} 曲スキップ)"
                        )

                        # 全DBに対して、各DB専用のモードで特徴量を抽出・登録
                        mysql_registered = False

                        # バッチ内の全ファイルを一度だけロード（メモリ上で再利用）
                        waveform_cache: dict[str, tuple[object, int]] = (
                            {}
                        )  # {filename: (y, sr)}
                        load_errors = 0
                        for file_path, filename, normalized_dir in files_to_process:
                            if filename not in waveform_cache:
                                try:
                                    import librosa

                                    # 最初のextractorのsrでロード
                                    y, sr = librosa.load(
                                        file_path,
                                        sr=dbs_and_extractors[0][1].sr,
                                        duration=dbs_and_extractors[0][1].duration,
                                    )
                                    waveform_cache[filename] = (y, sr)
                                except Exception as e:
                                    print(
                                        f"   ❌ 音声ロードエラー ({filename}): {str(e)}"
                                    )
                                    load_errors += 1

                        if waveform_cache:
                            success_msg = f"    📂 {len(waveform_cache)} 曲をメモリにロード済み（再利用）"
                            if load_errors > 0:
                                success_msg += f" ({load_errors} 曲ロード失敗)"
                            print(success_msg)

                        for db, extractor, mode in dbs_and_extractors:
                            # 各DB用の抽出器で特徴量を抽出（波形データを再利用）
                            batch_data = []
                            current_normalized_dir = ""
                            for file_path, filename, normalized_dir in files_to_process:
                                current_normalized_dir = normalized_dir
                                waveform = waveform_cache.get(filename)
                                song_data = prepare_song_data(
                                    extractor,
                                    file_path,
                                    filename,
                                    normalized_dir,
                                    waveform=waveform,
                                )
                                if song_data:
                                    batch_data.append(song_data)

                            # MySQL登録は最初のDB登録でのみ
                            skip_mysql = mysql_registered

                            if batch_data and current_normalized_dir:
                                try:
                                    added_count = add_songs_batch(
                                        db,
                                        batch_data,
                                        current_normalized_dir,
                                        skip_mysql=skip_mysql,
                                    )
                                    if not mysql_registered:  # 最初のDBのみカウント
                                        total_added += added_count
                                        mysql_registered = True
                                    if added_count > 0:
                                        if mode != "minimal":
                                            print(
                                                f"    ✅ {mode} DB に {added_count} 曲登録"
                                            )
                                        else:
                                            print(f"    ✅ {added_count} 曲登録")
                                except Exception as e:
                                    print(
                                        f"    ❌ {mode} DB バッチ登録エラー: {str(e)}"
                                    )
                    else:
                        pass
                        # print(f"    すべて登録済み ({skipped_count} 曲スキップ)")

                    # セグメントDB登録（バッチチェックで最適化）
                    # 全てのDBに登録済みかバッチチェック
                    all_collections = [
                        config["collection"] for config in DB_CONFIGS
                    ] + [model["collection"] for model in SEGMENT_MODELS]
                    batch_filenames_check = [f[1] for f in batch_files]

                    try:
                        processed_map = (
                            song_metadata_db.get_processed_collections_batch(
                                batch_filenames_check
                            )
                        )
                    except Exception as e:
                        print(f"    ⚠️  処理済みチェックエラー（処理継続）: {str(e)}")
                        processed_map = {}

                    # バッチ内の全曲分のセグメントを準備
                    segments_to_add: dict[
                        str, list[tuple[str, list[float], dict, str]]
                    ] = {model["collection"]: [] for model in SEGMENT_MODELS}
                    songs_to_mark: dict[str, set[str]] = (
                        {}
                    )  # {filename: {collection1, collection2}}

                    # セグメント用の波形キャッシュを準備（ファイルごとに各target_sr用の波形を保持）
                    segment_waveform_caches: dict[
                        str, dict[int, tuple[object, int]]
                    ] = {}

                    for file_path, filename, normalized_dir in batch_files:
                        # 全てのDBに登録済みかチェック（早期スキップ）
                        processed_collections = processed_map.get(filename, set())
                        if all(col in processed_collections for col in all_collections):
                            # 全DB登録済み - 完全スキップ
                            continue

                        # このファイル用の波形キャッシュを準備（必要になったらロード）
                        if filename not in segment_waveform_caches:
                            segment_waveform_caches[filename] = {}

                        try:
                            segment_result = register_segments_for_file(
                                file_path=file_path,
                                filename=filename,
                                normalized_dir=normalized_dir,
                                segment_models=segment_models,
                                segment_seconds=SEGMENT_SECONDS,
                                processed_collections=processed_collections,
                                waveform_cache=segment_waveform_caches[filename],
                            )

                            if segment_result:
                                for (
                                    collection_name,
                                    segment_items,
                                ) in segment_result.items():
                                    # normalized_dirを各アイテムに追加してバッファに蓄積
                                    for seg_id, emb, meta in segment_items:
                                        segments_to_add[collection_name].append(
                                            (seg_id, emb, meta, normalized_dir)
                                        )

                                    # この曲をこのコレクションで処理済みとしてマーク予定に追加
                                    if filename not in songs_to_mark:
                                        songs_to_mark[filename] = set()
                                    songs_to_mark[filename].add(collection_name)
                        except Exception as e:
                            print(f"    ⚠️  セグメント登録エラー: {str(e)}")

                    # バッチ内の全セグメントを一括でChromaDBに追加
                    for segment_model in segment_models:
                        collection_name = segment_model.collection
                        segment_batch = segments_to_add.get(collection_name, [])

                        if not segment_batch:
                            continue

                        # ChromaDBへの一括追加
                        ids = [item[0] for item in segment_batch]
                        embeddings = [item[1] for item in segment_batch]
                        metadatas = []
                        for _, _, meta, source_dir in segment_batch:
                            full_meta = {
                                "excluded_from_search": False,
                                "source_dir": source_dir,
                            }
                            full_meta.update(meta)
                            metadatas.append(full_meta)

                        max_batch = _get_chroma_safe_batch_size(segment_model.db)
                        try:
                            for start in range(0, len(ids), max_batch):
                                end = start + max_batch
                                segment_model.db.collection.add(
                                    ids=ids[start:end],
                                    embeddings=embeddings[start:end],
                                    metadatas=metadatas[start:end],
                                )
                            print(
                                f"    ✅ {collection_name}: {len(ids)}セグメント一括登録"
                            )
                        except Exception as e:
                            print(f"    ❌ {collection_name} 一括登録エラー: {str(e)}")
                            continue

                    # MySQLに処理済みマークを一括登録
                    for filename, collections in songs_to_mark.items():
                        for collection_name in collections:
                            try:
                                song_metadata_db.mark_as_processed(
                                    filename, collection_name
                                )
                            except Exception as e:
                                print(
                                    f"    ⚠️  処理済みマーク失敗 ({filename}, {collection_name}): {str(e)}"
                                )

                    # バッチをクリア
                    batch_files = []

    finally:
        # シグナルハンドラをリセット
        signal.signal(signal.SIGINT, signal.SIG_DFL)

    print("\n🧹 セグメント検索キャッシュをクリア中...")
    try:
        clear_segment_search_cache()
        print("✅ セグメント検索キャッシュをクリアしました")
    except Exception as e:
        print(f"⚠️  キャッシュクリア失敗: {str(e)}")

    # 結果サマリー
    print("\n" + "=" * 60)
    print("📊 結果サマリー")
    print("=" * 60)
    print(f"   新規登録: {total_added} 曲")
    print(f"   スキップ: {total_skipped} 曲（登録済み）")
    if _interrupted and _total_files > 0:
        print(f"   中断: {_total_files - _processing_count} ファイル（未処理）")

    for db, _, mode in dbs_and_extractors:
        print(f"   DB ({mode}): {db.count()} 曲")
    for segment_model in segment_models:
        print(f"   DB ({segment_model.collection}): {segment_model.db.count()} 曲")

    if _interrupted:
        print("\n⚠️  処理が中断されました")
    else:
        print("\n✅ 完了！")


if __name__ == "__main__":
    main()
