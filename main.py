"""
連鎖検索スクリプト

使い方:
    uv run main.py "検索キーワード"
    uv run main.py "検索キーワード" --count 30
    uv run main.py --list "キーワード"  # 部分一致で曲を検索
"""

import argparse
from core.db_manager import SongVectorDB
import os
from colorama import Fore, Style, init
from config import DB_CONFIGS

# Windows用初期化
init()

# ========== DB初期化 ==========
db_minimal = SongVectorDB(collection_name="songs_minimal", distance_fn="cosine")
db_balance = SongVectorDB(collection_name="songs_balanced", distance_fn="cosine")
db_full = SongVectorDB(collection_name="songs_full", distance_fn="cosine")


def find_song_by_keyword(db: SongVectorDB, keyword: str, limit: int = 10) -> list[str]:
    """
    キーワードで部分一致検索して曲を探す

    Args:
        db: ベクトルDB
        keyword: 検索キーワード（部分一致）
        limit: 最大件数

    Returns:
        マッチした曲IDのリスト
    """
    all_songs = db.list_all(limit=10000)
    matches = []

    keyword_lower = keyword.lower()
    for song_id in all_songs["ids"]:
        if keyword_lower in song_id.lower():
            matches.append(song_id)
            if len(matches) >= limit:
                break

    return matches


def select_song_interactive(db: SongVectorDB, keyword: str) -> str | None:
    """
    キーワードで曲を検索し、複数ヒットした場合は選択させる

    Args:
        db: ベクトルDB
        keyword: 検索キーワード

    Returns:
        選択された曲ID（キャンセル時はNone）
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


def get_distance_color(distance: float) -> str:
    """
    距離に応じてANSI 24bit色を返す（緑→黄→赤の滑らかなグラデーション）
    距離 0〜0.01 の範囲で正規化、0.01以上は赤
    """
    # 0〜0.01の範囲で正規化（0.01以上は1.0にクリップ）
    ratio = min(distance / 0.01, 1.0)

    # 緑(0,255,0) → 黄(255,255,0) → 赤(255,0,0) のグラデーション
    if ratio < 0.5:
        # 緑 → 黄: 赤を0→255に増やす
        r = int(255 * (ratio * 2))
        g = 255
    else:
        # 黄 → 赤: 緑を255→0に減らす
        r = 255
        g = int(255 * (1 - (ratio - 0.5) * 2))

    b = 0
    # ANSI 24bit color (True Color)
    return f"\033[38;2;{r};{g};{b}m"


def search_song_from_db(db: SongVectorDB, query_song_id: str, n_results: int = 5):
    exist_song = db.get_song(song_id=query_song_id)
    if exist_song is None:
        print(f"Song ID {query_song_id} not found in DB.")
        return

    vector = exist_song["embedding"]
    # 自分自身を除外するため、1つ多く取得
    search_result = db.search_similar(query_embedding=vector, n_results=n_results + 1)

    # 自分自身を除外した結果を準備
    results = []
    for song_id, distance, metadata in zip(
        search_result["ids"][0],
        search_result["distances"][0],
        search_result["metadatas"][0],
    ):
        if song_id != query_song_id:
            results.append((song_id, distance, metadata))

    results = results[:n_results]

    if not results:
        print(f"\n--- 検索結果 for {query_song_id} ---")
        print("類似曲が見つかりませんでした。")
        return

    print(f"\n--- 検索結果 for {query_song_id} ---")
    for rank, (song_id, distance, metadata) in enumerate(results, start=1):
        source_dir = metadata.get("source_dir", "unknown")
        color = get_distance_color(distance)
        print(
            f"{color}Rank {rank:02d} | Dist.: {distance:.8f} | {source_dir:<15s} |  {song_id}{Style.RESET_ALL}"
        )
        # print(f"  Metadata: {metadata}")


def search_song():
    audio_path = r"data/scsp/【シャニソン】大崎 甜花「また明日」MV 【アイドルマスター】 [QYpNus7FJPg].wav"
    file_name = os.path.basename(audio_path)

    print("\n=== フルモードでの検索テスト ===")
    search_song_from_db(db_full, file_name)

    print("\n=== バランスドモードでの検索テスト ===")
    search_song_from_db(db_balance, file_name)

    print("\n=== ミニマルモードでの検索テスト ===")
    search_song_from_db(db_minimal, file_name)


def chain_search(
    start_filename: str,
    dbs: list[SongVectorDB],
    n_songs: int = 10,
):
    """
    1曲から始めて類似曲を連鎖的に辿る（複数DBから最も近いものを選択）

    Args:
        start_filename: 開始曲のファイル名
        dbs: 使用するベクトルDBのリスト
        n_songs: 表示する曲数
    """
    visited: set[str] = set()
    current_song_id = start_filename

    print(f"\n{'='*60}")
    print(f"連鎖検索開始: {start_filename}")
    print(f"表示曲数: {n_songs}, DB数: {len(dbs)}")
    print(f"{'='*60}")

    # 開始曲の存在確認（最初のDBで確認）
    exist_song = dbs[0].get_song(song_id=current_song_id)
    if exist_song is None:
        print(f"開始曲 {current_song_id} がDBに見つかりません。")
        return

    # 開始曲を表示
    start_metadata = exist_song.get("metadata", {})
    source_dir = start_metadata.get("source_dir", "data/scsp_mv")
    if source_dir == "unknown":
        source_dir = "data/scsp_mv"
    print(
        f"\n{Fore.CYAN}Start | {source_dir:<15s} | {current_song_id}{Style.RESET_ALL}"
    )
    visited.add(current_song_id)

    for i in range(n_songs):
        # 各DBから最も近い未訪問の曲を探す
        best_song = None
        best_distance = float("inf")
        best_metadata = None

        for db in dbs:
            # 現在の曲のベクトルを取得
            current_song = db.get_song(song_id=current_song_id)
            if current_song is None:
                continue

            vector = current_song["embedding"]

            # 十分な数の候補を取得（訪問済みを除外するため多めに）
            search_result = db.search_similar(
                query_embedding=vector, n_results=len(visited) + 10
            )

            # このDBで未訪問の最も近い曲を探す
            for song_id, distance, metadata in zip(
                search_result["ids"][0],
                search_result["distances"][0],
                search_result["metadatas"][0],
            ):
                if song_id not in visited and distance < best_distance:
                    best_song = song_id
                    best_distance = distance
                    best_metadata = metadata
                    break  # このDBでの最良は見つかった

        if best_song is None:
            print(f"\nこれ以上未訪問の類似曲がありません。")
            break

        # 次の曲を表示
        source_dir = best_metadata.get("source_dir", "data/scsp_mv")
        if source_dir == "unknown":
            source_dir = "data/scsp_mv"

        color = get_distance_color(best_distance)
        print(
            f"{color}{i+1:5d} | Dist.: {best_distance:.8f} | {source_dir:<15s} | {best_song}{Style.RESET_ALL}"
        )

        # 訪問済みに追加し、次のループへ
        visited.add(best_song)
        current_song_id = best_song

    print(f"\n{'='*60}")
    print(f"連鎖検索完了: {len(visited)}曲を辿りました")
    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(
        description="連鎖検索スクリプト - 類似曲を連鎖的に辿る"
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
        default=60,
        help="表示する曲数（デフォルト: 60）",
    )
    parser.add_argument(
        "--list",
        "-l",
        type=str,
        metavar="KEYWORD",
        help="キーワードで曲を検索して一覧表示",
    )

    args = parser.parse_args()

    # --list モード: 曲を検索して一覧表示（メタデータ付き）
    if args.list:
        matches = find_song_by_keyword(db_full, args.list, limit=50)
        if not matches:
            print(f"❌ '{args.list}' に一致する曲が見つかりません。")
            return
        print(f"\n🔍 '{args.list}' で {len(matches)} 件ヒット:\n")
        for i, song_id in enumerate(matches, 1):
            song = db_full.get_song(song_id=song_id, include_embedding=False)
            metadata = song.get("metadata", {}) if song else {}
            print(f"  {i:2d}. {song_id}")
            if metadata:
                for key, value in metadata.items():
                    print(f"      {key}: {value}")
            print()
        return

    # キーワードが指定されていない場合はヘルプ表示
    if not args.keyword:
        parser.print_help()
        print("\n" + "=" * 50)
        print("📝 使用例")
        print("=" * 50)
        print('  uv run main.py "フェスタ"           # 部分一致で開始曲を検索')
        print('  uv run main.py "SOS" --count 30    # 30曲まで表示')
        print('  uv run main.py --list "アイマス"    # 曲を検索して一覧表示')
        return

    # 開始曲を検索
    start_song = select_song_interactive(db_full, args.keyword)
    if not start_song:
        return

    # 連鎖検索を実行
    chain_search(
        start_filename=start_song,
        dbs=[db_full, db_balance, db_minimal],
        n_songs=args.count,
    )


if __name__ == "__main__":
    main()
