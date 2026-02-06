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
from datetime import datetime
from pathlib import Path
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
    r"F:\song-recommender-data\data",
    # "F:/million",
]

# 音声抽出設定
DURATION = 90  # 秒

# バッチ処理設定
BATCH_SIZE = 3  # 一度に登録する曲数（リモートDBのレイテンシ削減）


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
                print(
                    f"   [debug] YouTubeスクリプト: {filename} に対して複数DB登録開始"
                )
                for idx, (db, extractor, mode) in enumerate(dbs_and_extractors):
                    # 各DBに対して、そのDB用の抽出器で特徴量を抽出
                    print(
                        f"   [debug] DB登録試行 [{idx+1}/3]: {db.collection.name} (mode={mode})"
                    )
                    success, emb = add_song(
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
                    )
                    if success:
                        print(f"   [debug] DB登録成功: {db.collection.name}")
                        registered = True
                        mysql_already_stored = (
                            True  # 最初のDB登録後、以降はMySQL登録をスキップ
                        )
                    else:
                        print(f"   [debug] DB登録スキップ: {db.collection.name}")

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
) -> tuple[bool, list[float] | None]:
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

    Returns:
        (登録したらTrue、embeddingベクトル) のタプル
    """
    # 対象の拡張子のみ処理
    if not (filename.endswith(".wav") or filename.endswith(".mp3")):
        return False, None

    # このDB用の処理済みチェック（複数DB登録時に同じDBへの重複登録を防ぐ）
    collection_name = db.collection.name
    if song_metadata_db.is_processed(song_id=filename, collection_name=collection_name):
        print(f"   [debug] add_song: {collection_name} は既に処理済み - スキップ")
        return False, None

    # MySQL側の存在チェック（最初のDB登録の時のみ）
    if not skip_mysql:
        print(f"   [debug] add_song: MySQL存在チェック実行 (skip_mysql={skip_mysql})")
        if song_metadata_db.get_song(song_id=filename) is not None:
            print(f"   [debug] add_song: {filename} はMySQL側に既に存在 - スキップ")
            return False, None
    else:
        print(
            f"   [debug] add_song: MySQL存在チェック スキップ (skip_mysql={skip_mysql})"
        )

    # 特徴量抽出（初回のみ）
    if embedding is None:
        print(f"   [debug] add_song: 特徴量抽出開始 ({collection_name})")
        # YouTube IDによる重複チェック（最初のDB登録、MySQL記録時のみ）
        if not skip_mysql:
            youtube_id = extract_youtube_id(filename)
            if youtube_id:
                print(f"   [debug] add_song: YouTubeID重複チェック: {youtube_id}")
                existing = song_metadata_db.get_by_youtube_id(youtube_id)
                if existing:
                    print(
                        f"   [debug] add_song: YouTubeID {youtube_id} は既に存在 - スキップ"
                    )
                    return False, None
        else:
            print(
                f"   [debug] add_song: YouTubeID重複チェック スキップ (skip_mysql={skip_mysql})"
            )

        try:
            embedding = extractor.extract_to_vector(file_path)
            print(f"   [debug] add_song: 特徴量抽出成功 (次元数: {len(embedding)})")
        except Exception as e:
            print(f"   ❌ 特徴量抽出エラー ({filename}): {str(e)}")
            raise

        # MySQLにメタデータを保存（初回のみ）
        if not skip_mysql:
            print(f"   [debug] add_song: MySQL側へのメタデータ登録開始")
            song_title = (
                song_title_override
                if song_title_override
                else extract_song_title(filename)
            )
            _, ext = os.path.splitext(filename)
            youtube_id = extract_youtube_id(filename)

            song_metadata_db.add_song(
                song_id=filename,
                filename=filename,
                song_title=song_title,
                artist_name=artist_name if artist_name is not None else "",
                source_dir=normalized_dir,
                youtube_id=youtube_id if youtube_id is not None else "",
                file_extension=ext.lower(),
                file_size_mb=get_file_size_mb(file_path),
                excluded_from_search=False,
            )
            print(f"   [debug] add_song: MySQL側へのメタデータ登録完了")
        else:
            print(f"   [debug] add_song: MySQL側へのメタデータ登録 スキップ")

    # ChromaDBには最小限のデータのみ保存（IDとベクトルと検索除外フラグ、source_dir）
    print(f"   [debug] add_song: ChromaDB {collection_name} へのベクトル登録中")
    db.add_song(
        song_id=filename,
        embedding=embedding,
        excluded_from_search=False,
        source_dir=normalized_dir,
    )
    print(f"   [debug] add_song: ChromaDB {collection_name} へのベクトル登録完了")

    # 処理済みコレクションとしてマーク
    print(f"   [debug] add_song: processed_collection マーク中 ({collection_name})")
    song_metadata_db.mark_as_processed(
        song_id=filename, collection_name=collection_name
    )
    print(f"   [debug] add_song: processed_collection マーク完了 ({collection_name})")

    return True, embedding


def prepare_song_data(
    extractor: FeatureExtractor,
    file_path: str,
    filename: str,
    normalized_dir: str,
    artist_name: str | None = None,
    song_title_override: str | None = None,
) -> tuple[str, list[float], str, str, str, str, float] | None:
    """
    1曲分のデータを準備する（バッチ処理用）

    Args:
        extractor: 特徴量抽出器
        file_path: 実際のファイルパス
        filename: ファイル名
        normalized_dir: 正規化されたディレクトリパス
        artist_name: アーティスト名（任意）
        song_title_override: 曲名上書き（任意）

    Returns:
        (song_id, embedding, song_title, artist_name, youtube_id, file_extension, file_size_mb) のタプル、
        または処理不要の場合はNone
    """
    # 対象の拡張子のみ処理
    if not (filename.endswith(".wav") or filename.endswith(".mp3")):
        return None

    # 特徴量抽出
    try:
        embedding = extractor.extract_to_vector(file_path)
    except Exception as e:
        print(f"   ❌ 特徴量抽出エラー ({filename}): {str(e)}")
        return None

    # メタデータ構築
    youtube_id = extract_youtube_id(filename)
    song_title = (
        song_title_override if song_title_override else extract_song_title(filename)
    )
    _, ext = os.path.splitext(filename)

    return (
        filename,  # song_id
        embedding,
        song_title,
        artist_name if artist_name is not None else "",
        youtube_id if youtube_id is not None else "",
        ext.lower(),
        get_file_size_mb(file_path),
    )


def add_songs_batch(
    db: SongVectorDB,
    song_data_list: list[tuple[str, list[float], str, str, str, str, float]],
    normalized_dir: str,
    skip_mysql: bool = False,
) -> int:
    """
    複数の曲を一括でDBに登録する（バルクインサート）

    Args:
        db: ベクトルDB
        song_data_list: (song_id, embedding, song_title, artist_name, youtube_id, file_extension, file_size_mb) のリスト
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
    print(f"   バッチサイズ: {BATCH_SIZE} 曲/バッチ")
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
                if len(batch_files) >= BATCH_SIZE or idx == len(audio_files):
                    # バッチ内のファイル名リストを取得
                    batch_filenames = [f[1] for f in batch_files]

                    # 既存チェック（バルククエリ）
                    existing_result = dbs_and_extractors[0][0].get_songs(
                        batch_filenames, include_embedding=False
                    )
                    existing_ids = set(existing_result.get("ids", []))

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
                        print(
                            f"   [debug] ローカルファイル: {len(files_to_process)} 曲に対して複数DB登録開始"
                        )
                        for db, extractor, mode in dbs_and_extractors:
                            # 各DB用の抽出器で特徴量を抽出
                            print(f"   [debug] {mode} DB 用の特徴量抽出・登録開始")
                            batch_data = []
                            current_normalized_dir = ""
                            for file_path, filename, normalized_dir in files_to_process:
                                current_normalized_dir = normalized_dir
                                song_data = prepare_song_data(
                                    extractor, file_path, filename, normalized_dir
                                )
                                if song_data:
                                    batch_data.append(song_data)

                            # MySQL登録は最初のDB登録でのみ
                            skip_mysql = mysql_registered
                            print(
                                f"   [debug] {mode} DB: skip_mysql={skip_mysql}, batch_data_count={len(batch_data)}"
                            )

                            if batch_data and current_normalized_dir:
                                try:
                                    added_count = add_songs_batch(
                                        db,
                                        batch_data,
                                        current_normalized_dir,
                                        skip_mysql=skip_mysql,
                                    )
                                    print(
                                        f"   [debug] {mode} DB: {added_count} 曲登録完了"
                                    )
                                    if not mysql_registered:  # 最初のDBのみカウント
                                        total_added += added_count
                                        mysql_registered = True
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

                    # バッチをクリア
                    batch_files = []

    finally:
        # シグナルハンドラをリセット
        signal.signal(signal.SIGINT, signal.SIG_DFL)

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

    if _interrupted:
        print("\n⚠️  処理が中断されました")
    else:
        print("\n✅ 完了！")


if __name__ == "__main__":
    main()
