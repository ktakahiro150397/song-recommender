# ベクトルDB初期化
from core.db_manager import SongVectorDB
from core.feature_extractor import FeatureExtractor

db = SongVectorDB(db_path="data/chroma_db_cos", distance_fn="cosine")
extractor = FeatureExtractor(duration=90)


def main():
    sound_dir = "data/sample_sound"

    # ディレクトリ配下の音声ファイルを登録
    import os

    for filename in os.listdir(sound_dir):

        exist_song = db.get_song(song_id=filename)
        if exist_song is not None:
            print(f"Skipping {filename}, already in DB.")
            continue

        if filename.endswith(".wav") or filename.endswith(".mp3"):
            file_path = os.path.join(sound_dir, filename)
            print(f"Processing {file_path}...")
            embedding = extractor.extract_to_vector(file_path)
            metadata = {"filename": filename}
            db.add_song(song_id=filename, embedding=embedding, metadata=metadata)

    print(f"\nTotal songs in DB: {db.count()}")


def search_song():
    audio_path = "data/sample_sound/【シャニソン】アルストロメリア「明日もBeautiful Day」MV 【アイドルマスター】 [qR3yRbrlaCk].wav"

    # 存在する場合は取得
    exist_song = db.get_song(song_id=audio_path)
    if exist_song is None:
        vector = extractor.extract_to_vector(audio_path=audio_path)
    else:
        vector = exist_song["embedding"]

    search_result = db.search_similar(query_embedding=vector, n_results=10)

    print("\n--- 検索結果 ---")
    for idx, (song_id, distance, metadata) in enumerate(
        zip(
            search_result["ids"][0],
            search_result["distances"][0],
            search_result["metadatas"][0],
        )
    ):
        print(f"Rank {idx + 1}:")
        print(f"  Song ID: {song_id}")
        print(f"  Distance: {distance}")
        print(f"  Metadata: {metadata}")


if __name__ == "__main__":
    main()
    search_song()
