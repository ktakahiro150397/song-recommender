"""
連鎖検索結果からYouTube Musicプレイリストを作成するスクリプト

使い方:
    uv run create_playlist_from_chain.py "検索キーワード"
    uv run create_playlist_from_chain.py "検索キーワード" --count 30
    uv run create_playlist_from_chain.py "検索キーワード" --name "プレイリスト名"
"""

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from colorama import Fore, Style, init

from core.db_manager import SongVectorDB
from core.ytmusic_manager import YTMusicManager
from core import song_metadata_db

# Windows用初期化
init()

# ========== デフォルト設定 ==========
DEFAULT_PLAYLIST_NAME = "曲調リコメンドプレイリスト"
DEFAULT_N_SONGS = 30

# 使用するDB
from config import DB_PATHS

# YouTube Music設定
BROWSER_FILE = "browser.json"
PRIVACY = "PRIVATE"  # PRIVATE, PUBLIC, UNLISTED

# ========== ユーティリティ関数 ==========


def find_song_by_keyword(db: SongVectorDB, keyword: str, limit: int = 10) -> list[str]:
    """
    キーワードで部分一致検索して曲を探す
    """
    # MySQLでキーワード検索（セッション内で辞書化済み）
    results = song_metadata_db.search_by_keyword(keyword, limit=limit)
    return [song_id for song_id, _ in results]


def select_song_interactive(db: SongVectorDB, keyword: str) -> str | None:
    """
    キーワードで曲を検索し、複数ヒットした場合は選択させる
    """
    matches = find_song_by_keyword(db, keyword, limit=20)

    if not matches:
        print(f"❌ '{keyword}' に一致する曲が見つかりません。")
        return None

    if len(matches) == 1:
        print(f"✅ 1件ヒット: {matches[0]}")
        return matches[0]

    # 複数ヒット時は選択
    print(f"\n🔍 '{keyword}' で {len(matches)} 件ヒット:")
    for i, song_id in enumerate(matches, 1):
        print(f"  {i:2d}. {song_id}")

    print()
    try:
        choice = input("番号を入力 (Enterで1番目を選択, qでキャンセル): ").strip()
        if choice.lower() == "q":
            return None
        if choice == "":
            return matches[0]
        idx = int(choice) - 1
        if 0 <= idx < len(matches):
            return matches[idx]
        print("❌ 無効な番号です。")
        return None
    except (ValueError, KeyboardInterrupt):
        return None


def extract_video_id_from_filename(filename: str) -> str | None:
    """
    ファイル名からYouTube動画IDを抽出する
    例: "フェスタ・イルミネーション [0Oj57StVGKk].wav" → "0Oj57StVGKk"

    Note: YouTubeの動画IDは11文字の英数字とハイフン、アンダースコアで構成される
    """
    match = re.search(r"\[([a-zA-Z0-9_-]{11})\]", filename)
    return match.group(1) if match else None


def filename_to_query(filename: str, source_dir: str | None = None) -> str:
    """
    ファイル名から検索クエリを抽出
    例: "フェスタ・イルミネーション [0Oj57StVGKk].wav" → "フェスタ・イルミネーション"
    source_dirが指定されていれば、フォルダ名を検索クエリに追加
    例: source_dir="data/gakumas_mv" → "フェスタ・イルミネーション gakumas_mv"
    """
    # [videoId] と拡張子を除去
    match = re.match(r"(.+?)\s*\[.*\]\.(wav|mp3)", filename)
    if match:
        query = match.group(1).strip()
    else:
        # マッチしない場合は拡張子だけ除去
        query = re.sub(r"\.(wav|mp3)$", "", filename).strip()

    # source_dirからフォルダ名を抽出して追加
    if source_dir:
        # "data/xxx" or "xxx" からフォルダ名を取得
        folder_name = source_dir.split("/")[-1]
        if folder_name and folder_name != "data":
            query = f"{query} {folder_name}"

    return query


def get_distance_color(distance: float) -> str:
    """距離に応じてANSI 24bit色を返す"""
    ratio = min(distance / 0.01, 1.0)
    if ratio < 0.5:
        r = int(255 * (ratio * 2))
        g = 255
    else:
        r = 255
        g = int(255 * (1 - (ratio - 0.5) * 2))
    b = 0
    return f"\033[38;2;{r};{g};{b}m"


# ========== 連鎖検索 ==========


def _normalize_source_dir_filters(
    source_dir_filter: str | list[str] | None,
) -> list[str]:
    if not source_dir_filter:
        return []
    if isinstance(source_dir_filter, list):
        return [name.strip() for name in source_dir_filter if name.strip()]
    if "," in source_dir_filter:
        return [name.strip() for name in source_dir_filter.split(",") if name.strip()]
    return [source_dir_filter.strip()]


def _build_source_dir_candidates(source_dir_names: list[str]) -> list[str]:
    candidates: set[str] = set()
    for name in source_dir_names:
        if not name:
            continue
        if name.startswith("data/") or name.startswith("data\\"):
            candidates.add(name)
        else:
            candidates.add(name)
            candidates.add(f"data/{name}")
            candidates.add(f"data\\{name}")
    return list(candidates)


def chain_search_to_list(
    start_filename: str,
    dbs: list[SongVectorDB],
    n_songs: int = 30,
    artist_filter: str | list[str] | None = None,
    min_bpm: float | None = None,
    max_bpm: float | None = None,
) -> list[tuple[str, float, dict]]:
    """
    1曲から始めて類似曲を連鎖的に辿り、結果をリストで返す

    Args:
        start_filename: 開始曲のファイル名
        dbs: 使用するベクトルDBのリスト
        n_songs: 取得する曲数
        artist_filter: source_dirでフィルタリング（複数可）
        min_bpm: 最小BPM（指定された場合、この値以上のBPMの曲のみ選択）
        max_bpm: 最大BPM（指定された場合、この値以下のBPMの曲のみ選択）

    Returns:
        [(song_id, distance, metadata), ...] のリスト（開始曲を含む）
    """
    visited: set[str] = set()
    results: list[tuple[str, float]] = []
    current_song_id = start_filename

    # source_dirフィルタが指定されている場合、whereフィルタを構築
    where_filter: dict | None = None
    source_dir_filters = _normalize_source_dir_filters(artist_filter)
    if source_dir_filters:
        matched_dirs = _build_source_dir_candidates(source_dir_filters)
        if not matched_dirs:
            print("❌ 指定した登録元に一致するディレクトリが見つかりません。")
            return []
        # $in で複数のsource_dirをOR検索
        where_filter = {"source_dir": {"$in": matched_dirs}}

    print(f"\n{'='*60}")
    print(f"🔗 連鎖検索開始: {start_filename}")
    print(f"   取得曲数: {n_songs}, DB数: {len(dbs)}")
    if source_dir_filters:
        print(f"   登録元フィルタ: {', '.join(source_dir_filters)}")
        print(f"   対象ディレクトリ: {len(matched_dirs)}個")
    if min_bpm is not None:
        print(f"   最小BPMフィルタ: {min_bpm:.1f} BPM以上")
    if max_bpm is not None:
        print(f"   最大BPMフィルタ: {max_bpm:.1f} BPM以下")
    print(f"{'='*60}")

    # 開始曲の存在確認（全てのDBで確認）
    exist_song = None
    for db in dbs:
        exist_song = db.get_song(song_id=current_song_id)
        if exist_song is not None:
            break

    if exist_song is None:
        print(f"❌ 開始曲 {current_song_id} がDBに見つかりません。")
        return []

    # 開始曲のメタデータをMySQLから取得
    start_song = song_metadata_db.get_song(current_song_id)
    if start_song:
        start_metadata = {
            "filename": start_song.get("filename", ""),
            "song_title": start_song.get("song_title", ""),
            "artist_name": start_song.get("artist_name", ""),
            "source_dir": start_song.get("source_dir", ""),
            "youtube_id": start_song.get("youtube_id", ""),
            "file_extension": start_song.get("file_extension", ""),
            "file_size_mb": start_song.get("file_size_mb", 0.0),
            "bpm": start_song.get("bpm"),
            "registered_at": start_song.get("registered_at", ""),
            "excluded_from_search": start_song.get("excluded_from_search", False),
        }
        source_dir = start_song.get("source_dir", "unknown")
    else:
        start_metadata = {}
        source_dir = "unknown"

    print(
        f"\n{Fore.CYAN}Start | {source_dir:<15s} | {current_song_id}{Style.RESET_ALL}"
    )
    visited.add(current_song_id)
    results.append((current_song_id, 0.0, start_metadata))

    for i in range(n_songs - 1):  # 開始曲を含めてn_songs曲
        best_song = None
        best_distance = float("inf")
        best_metadata = None

        for db in dbs:
            current_song = db.get_song(song_id=current_song_id)
            if current_song is None:
                continue

            vector = current_song["embedding"]
            # 検索除外フラグが False (未設定を含む) の曲のみ検索
            # パフォーマンス最適化: 候補数を50に固定（複数DBがあるため十分）
            n_candidates = 50

            # where_filter が指定されている場合は、artist_filter フラグと組み合わせる
            combined_where = None
            if where_filter:
                combined_where = {
                    "$and": [
                        where_filter,
                        {"excluded_from_search": {"$ne": True}},
                    ]
                }
            else:
                combined_where = {"excluded_from_search": {"$ne": True}}

            search_result = db.search_similar(
                query_embedding=vector,
                n_results=n_candidates,
                where=combined_where,
            )

            # 検索結果のIDリストを取得
            candidate_ids = search_result["ids"][0]
            candidate_distances = search_result["distances"][0]

            # MySQLからメタデータを一括取得
            metadata_dict = song_metadata_db.get_songs_as_dict(candidate_ids)

            for song_id, distance in zip(candidate_ids, candidate_distances):
                metadata = metadata_dict.get(song_id, {})

                # BPMフィルタを適用
                if min_bpm is not None or max_bpm is not None:
                    song_bpm = metadata.get("bpm")
                    if song_bpm is None:
                        continue
                    if min_bpm is not None and song_bpm < min_bpm:
                        continue
                    if max_bpm is not None and song_bpm > max_bpm:
                        continue

                if song_id not in visited and distance < best_distance:
                    best_song = song_id
                    best_distance = distance
                    best_metadata = metadata
                    break

        if best_song is None:
            print(f"\n⚠️  これ以上未訪問の類似曲がありません。")
            break

        source_dir = best_metadata.get("source_dir", "unknown")
        color = get_distance_color(best_distance)
        print(
            f"{color}{i+1:5d} | Dist.: {best_distance:.8f} | {source_dir:<15s} | {best_song}{Style.RESET_ALL}"
        )

        visited.add(best_song)
        results.append((best_song, best_distance, best_metadata))
        current_song_id = best_song

    print(f"\n{'='*60}")
    print(f"✅ 連鎖検索完了: {len(results)}曲を取得")
    print(f"{'='*60}")

    return results


# ========== メイン処理 ==========


def run_playlist_creation(
    start_song: str,
    playlist_name: str,
    n_songs: int,
):
    """プレイリスト作成の実行"""
    print("\n" + "=" * 60)
    print("🎵 連鎖検索 → YouTube Music プレイリスト作成")
    print("=" * 60)
    print(f"   プレイリスト名: {playlist_name}")
    print(f"   開始曲: {start_song}")
    print(f"   曲数: {n_songs}")

    # 1. DBを初期化
    print("\n📂 DBを読み込み中...")
    from config import DB_CONFIGS

    dbs = [
        SongVectorDB(collection_name=cfg["collection"], distance_fn="cosine")
        for cfg in DB_CONFIGS
    ]
    print(f"   {len(dbs)}個のDBを読み込みました")

    # 2. 連鎖検索を実行
    chain_results = chain_search_to_list(
        start_filename=start_song,
        dbs=dbs,
        n_songs=n_songs,
    )

    if not chain_results:
        print("❌ 連鎖検索結果が空のため、終了します。")
        return

    # 3. ファイル名から検索クエリとビデオIDを生成
    print("\n🔍 検索クエリとビデオIDを生成中...")
    song_data = []  # [(video_id_or_query, is_video_id), ...]
    for song_id, distance, metadata in chain_results:
        # まずメタデータからvideo_idを取得
        video_id = metadata.get("youtube_id") if metadata else None

        # メタデータにない場合はファイル名から抽出
        if not video_id:
            video_id = extract_video_id_from_filename(song_id)

        if video_id:
            song_data.append((video_id, True))  # True = video_id
            print(f"   {song_id}")
            print(f"      → ビデオID: {video_id}")
        else:
            # Video IDがない場合はクエリ検索にフォールバック
            source_dir = metadata.get("source_dir") if metadata else None
            query = filename_to_query(song_id, source_dir=source_dir)
            song_data.append((query, False))  # False = search query
            print(f"   {song_id}")
            print(f"      → 検索クエリ: {query}")

    # 4. YouTube Musicマネージャーを初期化
    print("\n🔗 YouTube Musicに接続中...")
    ytm = YTMusicManager(browser_file=BROWSER_FILE)

    # 5. Description を作成
    today = datetime.now().strftime("%Y-%m-%d")
    start_query = filename_to_query(start_song)
    description = f"処理日: {today}\n開始曲: {start_query}"

    # 6. プレイリストを作成
    print("\n🎵 プレイリストを作成中...")
    result = ytm.create_or_replace_playlist(
        playlist_name=playlist_name,
        song_data=song_data,
        description=description,
        privacy=PRIVACY,
        verbose=True,
    )

    # 7. 結果サマリー
    print("\n" + "=" * 60)
    print("📊 結果サマリー")
    print("=" * 60)
    print(f"   プレイリスト名: {playlist_name}")
    print(f"   Playlist ID: {result['playlist_id']}")
    print(f"   登録成功: {len(result['found_songs'])} / {len(song_data)} 曲")
    print(f"   見つからず: {len(result['not_found'])} 曲")

    if result["playlist_id"]:
        print(
            f"\n   🔗 URL: https://music.youtube.com/playlist?list={result['playlist_id']}"
        )

    if result["not_found"]:
        print("\n   ❌ 見つからなかった曲:")
        for q in result["not_found"]:
            print(f"      - {q}")

    print("\n✅ 完了！")


def main():
    parser = argparse.ArgumentParser(
        description="連鎖検索結果からYouTube Musicプレイリストを作成"
    )
    parser.add_argument(
        "keyword",
        nargs="?",
        help="開始曲の検索キーワード（部分一致）",
    )
    parser.add_argument(
        "--count",
        "-n",
        type=int,
        default=DEFAULT_N_SONGS,
        help=f"プレイリストに追加する曲数（デフォルト: {DEFAULT_N_SONGS}）",
    )
    parser.add_argument(
        "--name",
        type=str,
        default=DEFAULT_PLAYLIST_NAME,
        help=f"プレイリスト名（デフォルト: {DEFAULT_PLAYLIST_NAME}）",
    )

    args = parser.parse_args()

    # キーワードが指定されていない場合はヘルプ表示
    if not args.keyword:
        parser.print_help()
        print("\n" + "=" * 50)
        print("📝 使用例")
        print("=" * 50)
        print('  uv run create_playlist_from_chain.py "フェスタ"')
        print('  uv run create_playlist_from_chain.py "SOS" --count 20')
        print('  uv run create_playlist_from_chain.py "SOS" --name "My Playlist"')
        return

    # DBを初期化（曲検索用）
    db = SongVectorDB(db_path=DB_PATHS[0], distance_fn="cosine")

    # 開始曲を検索
    start_song = select_song_interactive(db, args.keyword)
    if not start_song:
        return

    # プレイリスト作成を実行
    run_playlist_creation(
        start_song=start_song,
        playlist_name=args.name,
        n_songs=args.count,
    )


if __name__ == "__main__":
    main()
