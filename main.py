# ベクトルDB初期化
from core.db_manager import SongVectorDB
from core.feature_extractor import FeatureExtractor
import os

db_minimal = SongVectorDB(db_path="data/chroma_db_cos_minimal", distance_fn="cosine")
db_balance = SongVectorDB(db_path="data/chroma_db_cos_balance", distance_fn="cosine")
db_full = SongVectorDB(db_path="data/chroma_db_cos_full", distance_fn="cosine")
extractor_minimal = FeatureExtractor(duration=90, mode="minimal")
extractor_balance = FeatureExtractor(duration=90, mode="balanced")
extractor_full = FeatureExtractor(duration=90, mode="full")

sound_dir = "data/sample_sound"


def add_songs(db: SongVectorDB, extractor: FeatureExtractor, filename: str):
    # print(f"Checking {filename}...")

    exist_song = db.get_song(song_id=filename)
    if exist_song is not None:
        # print(f"Skipping {filename}, already in DB.")
        return

    if filename.endswith(".wav") or filename.endswith(".mp3"):
        file_path = os.path.join(sound_dir, filename)
        print(f"Processing {file_path}...")
        embedding = extractor.extract_to_vector(file_path)
        metadata = {"filename": filename}
        db.add_song(song_id=filename, embedding=embedding, metadata=metadata)


def main():
    # ディレクトリ配下の音声ファイルを登録

    for filename in os.listdir(sound_dir):
        add_songs(db_minimal, extractor_minimal, filename)
        add_songs(db_balance, extractor_balance, filename)
        add_songs(db_full, extractor_full, filename)

    print(f"\nTotal songs in DB: {db_full.count()}")


def search_song_from_db(db: SongVectorDB, song_id: str):
    exist_song = db.get_song(song_id=song_id)
    if exist_song is None:
        print(f"Song ID {song_id} not found in DB.")
        return

    vector = exist_song["embedding"]
    search_result = db.search_similar(query_embedding=vector, n_results=5)

    print(f"\n--- 検索結果 for {song_id} ---")
    for idx, (song_id, distance, metadata) in enumerate(
        zip(
            search_result["ids"][0],
            search_result["distances"][0],
            search_result["metadatas"][0],
        )
    ):
        print(f"Rank {(idx + 1):02d} | Dist.: {distance:.8f} | {song_id}")
        # print(f"  Metadata: {metadata}")


def search_song():
    audio_path = "data/sample_sound/【シャニソン】シーズ「Monochromatic」3DMV（4K対応）【アイドルマスター】 [sx6CnJbn33k].wav"
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
