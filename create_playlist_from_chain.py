"""
連鎖検索結果からYouTube Musicプレイリストを作成するスクリプト

使い方:
    uv run create_playlist_from_chain.py
"""

import re
from datetime import datetime
from colorama import Fore, Style, init

from core.db_manager import SongVectorDB
from core.ytmusic_manager import YTMusicManager

# Windows用初期化
init()

# ========== 定数設定 ==========
# プレイリスト名
PLAYLIST_NAME = "曲調リコメンドプレイリスト"

# 開始曲のファイル名
START_SONG = "【シャニソン】黛 冬優子「SOS」MV 【アイドルマスター】 [zny-LI3hUPM].wav"

# プレイリストに追加する曲数
N_SONGS = 30

# 使用するDB
DB_PATHS = [
    "data/chroma_db_cos_full",
    "data/chroma_db_cos_balance",
    "data/chroma_db_cos_minimal",
]

# YouTube Music設定
BROWSER_FILE = "browser.json"
PRIVACY = "PRIVATE"  # PRIVATE, PUBLIC, UNLISTED

# ========== ユーティリティ関数 ==========


def filename_to_query(filename: str) -> str:
    """
    ファイル名から検索クエリを抽出
    例: "フェスタ・イルミネーション [0Oj57StVGKk].wav" → "フェスタ・イルミネーション"
    """
    # [videoId] と拡張子を除去
    match = re.match(r"(.+?)\s*\[.*\]\.(wav|mp3)", filename)
    if match:
        return match.group(1).strip()
    # マッチしない場合は拡張子だけ除去
    return re.sub(r"\.(wav|mp3)$", "", filename).strip()


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


def chain_search_to_list(
    start_filename: str,
    dbs: list[SongVectorDB],
    n_songs: int = 30,
) -> list[tuple[str, float]]:
    """
    1曲から始めて類似曲を連鎖的に辿り、結果をリストで返す

    Args:
        start_filename: 開始曲のファイル名
        dbs: 使用するベクトルDBのリスト
        n_songs: 取得する曲数

    Returns:
        [(song_id, distance), ...] のリスト（開始曲を含む）
    """
    visited: set[str] = set()
    results: list[tuple[str, float]] = []
    current_song_id = start_filename

    print(f"\n{'='*60}")
    print(f"🔗 連鎖検索開始: {start_filename}")
    print(f"   取得曲数: {n_songs}, DB数: {len(dbs)}")
    print(f"{'='*60}")

    # 開始曲の存在確認
    exist_song = dbs[0].get_song(song_id=current_song_id)
    if exist_song is None:
        print(f"❌ 開始曲 {current_song_id} がDBに見つかりません。")
        return []

    # 開始曲を追加
    start_metadata = exist_song.get("metadata", {})
    source_dir = start_metadata.get("source_dir", "unknown")
    print(
        f"\n{Fore.CYAN}Start | {source_dir:<15s} | {current_song_id}{Style.RESET_ALL}"
    )
    visited.add(current_song_id)
    results.append((current_song_id, 0.0))

    for i in range(n_songs - 1):  # 開始曲を含めてn_songs曲
        best_song = None
        best_distance = float("inf")
        best_metadata = None

        for db in dbs:
            current_song = db.get_song(song_id=current_song_id)
            if current_song is None:
                continue

            vector = current_song["embedding"]
            search_result = db.search_similar(
                query_embedding=vector, n_results=len(visited) + 10
            )

            for song_id, distance, metadata in zip(
                search_result["ids"][0],
                search_result["distances"][0],
                search_result["metadatas"][0],
            ):
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
        results.append((best_song, best_distance))
        current_song_id = best_song

    print(f"\n{'='*60}")
    print(f"✅ 連鎖検索完了: {len(results)}曲を取得")
    print(f"{'='*60}")

    return results


# ========== メイン処理 ==========


def main():
    print("\n" + "=" * 60)
    print("🎵 連鎖検索 → YouTube Music プレイリスト作成")
    print("=" * 60)
    print(f"   プレイリスト名: {PLAYLIST_NAME}")
    print(f"   開始曲: {START_SONG}")
    print(f"   曲数: {N_SONGS}")

    # 1. DBを初期化
    print("\n📂 DBを読み込み中...")
    dbs = [SongVectorDB(db_path=path, distance_fn="cosine") for path in DB_PATHS]
    print(f"   {len(dbs)}個のDBを読み込みました")

    # 2. 連鎖検索を実行
    chain_results = chain_search_to_list(
        start_filename=START_SONG,
        dbs=dbs,
        n_songs=N_SONGS,
    )

    if not chain_results:
        print("❌ 連鎖検索結果が空のため、終了します。")
        return

    # 3. ファイル名から検索クエリを生成
    print("\n🔍 検索クエリを生成中...")
    song_queries = []
    for song_id, distance in chain_results:
        query = filename_to_query(song_id)
        song_queries.append(query)
        print(f"   {song_id}")
        print(f"      → {query}")

    # 4. YouTube Musicマネージャーを初期化
    print("\n🔗 YouTube Musicに接続中...")
    ytm = YTMusicManager(browser_file=BROWSER_FILE)

    # 5. Description を作成
    today = datetime.now().strftime("%Y-%m-%d")
    start_query = filename_to_query(START_SONG)
    description = f"処理日: {today}\n開始曲: {start_query}"

    # 6. プレイリストを作成
    print("\n🎵 プレイリストを作成中...")
    result = ytm.create_or_replace_playlist(
        playlist_name=PLAYLIST_NAME,
        song_queries=song_queries,
        description=description,
        privacy=PRIVACY,
        verbose=True,
    )

    # 7. 結果サマリー
    print("\n" + "=" * 60)
    print("📊 結果サマリー")
    print("=" * 60)
    print(f"   プレイリスト名: {PLAYLIST_NAME}")
    print(f"   Playlist ID: {result['playlist_id']}")
    print(f"   登録成功: {len(result['found_songs'])} / {len(song_queries)} 曲")
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


if __name__ == "__main__":
    main()
