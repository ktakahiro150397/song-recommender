"""
連鎖検索のパフォーマンス分析スクリプト

各処理ステップの実行時間を計測して、ボトルネックを特定する
"""

import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
import statistics

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from core.db_manager import SongVectorDB
from core import song_metadata_db
from config import DB_CONFIGS
from create_playlist_from_chain import chain_search_to_list

# テスト用の曲ID
TEST_SONG = "Domestic De Violence [Na5PCi8YMYo].wav"
N_SONGS = 20  # 検索する曲数

# 計測用グローバル変数
timings = {
    "vector_search": [],
    "mysql_get_songs": [],
    "metadata_lookup": [],
    "filter_check": [],
    "total_iteration": [],
}


# パッチ関数を作成して、処理時間を計測
original_get_songs_as_dict = song_metadata_db.get_songs_as_dict
original_get_songs = song_metadata_db.get_songs


def patched_get_songs_as_dict(song_ids):
    """get_songs_as_dict をパッチして計測"""
    start = time.perf_counter()
    result = original_get_songs_as_dict(song_ids)
    elapsed = time.perf_counter() - start
    timings["mysql_get_songs"].append(elapsed)
    return result


def patched_get_songs(song_ids):
    """get_songs をパッチして計測"""
    start = time.perf_counter()
    result = original_get_songs(song_ids)
    elapsed = time.perf_counter() - start
    timings["mysql_get_songs"].append(elapsed)
    return result


# パッチを適用
song_metadata_db.get_songs_as_dict = patched_get_songs_as_dict
song_metadata_db.get_songs = patched_get_songs


def patched_chain_search(
    start_filename: str,
    dbs: list[SongVectorDB],
    n_songs: int = 30,
    artist_filter: str | None = None,
) -> list[tuple[str, float, dict]]:
    """
    パフォーマンス計測付きの連鎖検索
    """
    from colorama import Fore, Style
    from create_playlist_from_chain import get_distance_color

    visited: set[str] = set()
    results: list[tuple[str, float]] = []
    current_song_id = start_filename

    # 開始曲の存在確認
    exist_song = None
    for db in dbs:
        exist_song = db.get_song(song_id=current_song_id)
        if exist_song is not None:
            break

    if exist_song is None:
        print(f"❌ 開始曲 {current_song_id} がDBに見つかりません。")
        return []

    # 開始曲のメタデータ取得
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

    for i in range(n_songs - 1):
        iteration_start = time.perf_counter()
        best_song = None
        best_distance = float("inf")
        best_metadata = None

        for db in dbs:
            vector_search_start = time.perf_counter()

            current_song = db.get_song(song_id=current_song_id)
            if current_song is None:
                continue

            vector = current_song["embedding"]
            # 検索除外フラグが False (未設定を含む) の曲のみ検索
            # パフォーマンス最適化: 候補数を50に固定（複数DBがあるため十分）
            n_candidates = 50
            search_result = db.search_similar(
                query_embedding=vector,
                n_results=n_candidates,
                where={"excluded_from_search": {"$ne": True}},
            )

            vector_search_elapsed = time.perf_counter() - vector_search_start
            timings["vector_search"].append(vector_search_elapsed)

            # 検索結果
            candidate_ids = search_result["ids"][0]
            candidate_distances = search_result["distances"][0]

            # MySQLからメタデータを一括取得
            mysql_start = time.perf_counter()
            metadata_dict = song_metadata_db.get_songs_as_dict(candidate_ids)
            mysql_elapsed = time.perf_counter() - mysql_start

            for song_id, distance in zip(candidate_ids, candidate_distances):
                lookup_start = time.perf_counter()
                metadata = metadata_dict.get(song_id, {})
                lookup_elapsed = time.perf_counter() - lookup_start
                timings["metadata_lookup"].append(lookup_elapsed)

                filter_start = time.perf_counter()
                if artist_filter:
                    source_dir = metadata.get("source_dir", "")
                    dir_name = source_dir.replace("data/", "").replace("data\\", "")
                    if artist_filter.lower() not in dir_name.lower():
                        continue
                filter_elapsed = time.perf_counter() - filter_start
                timings["filter_check"].append(filter_elapsed)

                if song_id not in visited and distance < best_distance:
                    best_song = song_id
                    best_distance = distance
                    best_metadata = metadata
                    break

        if best_song is None:
            print(f"\n⚠️  これ以上未訪問の類似曲がありません。")
            break

        iteration_elapsed = time.perf_counter() - iteration_start
        timings["total_iteration"].append(iteration_elapsed)

        source_dir = best_metadata.get("source_dir", "unknown")
        color = get_distance_color(best_distance)
        print(
            f"{color}{i+1:5d} | Dist.: {best_distance:.8f} | {source_dir:<15s} | {best_song}{Style.RESET_ALL} (Iter: {iteration_elapsed:.3f}s)"
        )

        visited.add(best_song)
        results.append((best_song, best_distance, best_metadata))
        current_song_id = best_song

    return results


def print_timing_summary():
    """計測結果を表示"""
    print("\n" + "=" * 80)
    print("📊 パフォーマンス分析結果")
    print("=" * 80)

    for key, values in timings.items():
        if not values:
            continue

        count = len(values)
        total = sum(values)
        avg = statistics.mean(values)
        min_val = min(values)
        max_val = max(values)
        stdev = statistics.stdev(values) if len(values) > 1 else 0

        print(f"\n{key}:")
        print(f"  実行回数: {count}")
        print(f"  合計時間: {total:.3f}s")
        print(f"  平均時間: {avg:.4f}s")
        print(f"  最小時間: {min_val:.4f}s")
        print(f"  最大時間: {max_val:.4f}s")
        print(f"  標準偏差: {stdev:.4f}s")

        # イテレーションごとの時間配分を表示
        if key == "total_iteration":
            print(f"\n  イテレーションごとの時間:")
            for idx, val in enumerate(values[:10], 1):  # 最初の10イテレーション
                print(f"    イテレーション {idx}: {val:.3f}s")


def main():
    print("\n" + "=" * 80)
    print("🔗 連鎖検索パフォーマンス分析")
    print("=" * 80)
    print(f"テスト対象: {TEST_SONG}")
    print(f"取得曲数: {N_SONGS}")

    # DBを初期化（既存コードと同じ方式）
    print("\n📂 DBを読み込み中...")
    dbs = [
        SongVectorDB(collection_name=cfg["collection"], distance_fn="cosine")
        for cfg in DB_CONFIGS
    ]
    print(f"   {len(dbs)}個のDBを読み込みました")

    # 連鎖検索を実行
    start_time = time.perf_counter()
    results = patched_chain_search(
        start_filename=TEST_SONG,
        dbs=dbs,
        n_songs=N_SONGS,
    )
    total_time = time.perf_counter() - start_time

    print(f"\n✅ 連鎖検索完了: {len(results)}曲を取得")
    print(f"⏱️  総実行時間: {total_time:.3f}s")

    # 計測結果を表示
    print_timing_summary()

    print("\n" + "=" * 80)
    print("💡 ボトルネック分析")
    print("=" * 80)

    # 各処理の合計時間を計算
    vector_total = sum(timings["vector_search"])
    mysql_total = sum(timings["mysql_get_songs"])
    lookup_total = sum(timings["metadata_lookup"])
    filter_total = sum(timings["filter_check"])
    iteration_total = sum(timings["total_iteration"])

    print(f"ベクトル検索: {vector_total:.3f}s ({vector_total/total_time*100:.1f}%)")
    print(f"MySQL取得: {mysql_total:.3f}s ({mysql_total/total_time*100:.1f}%)")
    print(f"メタデータ検索: {lookup_total:.3f}s ({lookup_total/total_time*100:.1f}%)")
    print(f"フィルタ処理: {filter_total:.3f}s ({filter_total/total_time*100:.1f}%)")
    print(
        f"その他: {total_time - iteration_total:.3f}s ({(total_time - iteration_total)/total_time*100:.1f}%)"
    )


if __name__ == "__main__":
    main()
