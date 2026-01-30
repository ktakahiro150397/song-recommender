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
    ratio = min(distance / 0.02, 1.0)

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


if __name__ == "__main__":
    main()
    search_song()

    # サマーサマーオーシャンパーリィバケーション > クライマックスアイランド > カウントダウンラブ
    # > 泥濘鳴鳴 > 快盗Vを見逃すな > Monochromatic > 愛なView > アイ NEED YOU（FOR WONDERFUL STORY）
    # >　Ambitious Eve > SOS > Summer Night Paradise > また明日
    # 悪くない
