# ベクトルDB初期化
from core.db_manager import SongVectorDB
from core.feature_extractor import FeatureExtractor
import os
from colorama import Fore, Style, init

# Windows用初期化
init()

db_minimal = SongVectorDB(db_path="data/chroma_db_cos_minimal", distance_fn="cosine")
db_balance = SongVectorDB(db_path="data/chroma_db_cos_balance", distance_fn="cosine")
db_full = SongVectorDB(db_path="data/chroma_db_cos_full", distance_fn="cosine")
extractor_minimal = FeatureExtractor(duration=90, mode="minimal")
extractor_balance = FeatureExtractor(duration=90, mode="balanced")
extractor_full = FeatureExtractor(duration=90, mode="full")

sound_dirs = [
    "data/scsp_mv",
    "data/gakumas_mv",
    "data/utada",
    "data/million",
]


def add_songs(
    db: SongVectorDB, extractor: FeatureExtractor, sound_dir: str, filename: str
):
    # print(f"Checking {filename}...")

    exist_song = db.get_song(song_id=filename)
    if exist_song is not None:
        # print(f"Skipping {filename}, already in DB.")
        return

    if filename.endswith(".wav") or filename.endswith(".mp3"):
        file_path = os.path.join(sound_dir, filename)
        print(f"Processing {file_path}...")
        embedding = extractor.extract_to_vector(file_path)
        metadata = {"filename": filename, "source_dir": sound_dir}
        db.add_song(song_id=filename, embedding=embedding, metadata=metadata)


def main():
    # ディレクトリ配下の音声ファイルを登録

    for sound_dir in sound_dirs:
        if not os.path.exists(sound_dir):
            print(f"Skipping {sound_dir}, directory not found.")
            continue

        print(f"\n--- Processing directory: {sound_dir} ---")
        for filename in os.listdir(sound_dir):
            add_songs(db_minimal, extractor_minimal, sound_dir, filename)
            add_songs(db_balance, extractor_balance, sound_dir, filename)
            add_songs(db_full, extractor_full, sound_dir, filename)

    print(f"\nTotal songs in DB: {db_full.count()}")


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


if __name__ == "__main__":
    main()
    # search_song()

    # 連鎖検索の例（複数DBから最も近いものを選択）
    start_file = (
        "【シャニソン】黛 冬優子「SOS」MV 【アイドルマスター】 [zny-LI3hUPM].wav"
    )
    chain_search(
        start_filename=start_file,
        dbs=[db_full, db_balance, db_minimal],
        n_songs=30,
    )
