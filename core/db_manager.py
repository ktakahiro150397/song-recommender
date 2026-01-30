"""
ChromaDB を使ったベクトルDB操作モジュール
"""

import chromadb
from pathlib import Path


class SongVectorDB:
    """楽曲ベクトルを管理するクラス"""

    def __init__(self, db_path: str = "./data/chroma"):
        """
        Args:
            db_path: ChromaDBの永続化先パス
        """
        # ディレクトリがなければ作成
        Path(db_path).mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(path=db_path)
        self.collection = self.client.get_or_create_collection(
            name="songs", metadata={"description": "楽曲の音声特徴量ベクトル"}
        )

    def add_song(
        self, song_id: str, embedding: list[float], metadata: dict | None = None
    ) -> None:
        """
        楽曲をDBに登録する

        Args:
            song_id: 楽曲の一意なID
            embedding: 音声特徴量ベクトル
            metadata: 付加情報（タイトル、パスなど）
        """
        self.collection.add(
            ids=[song_id],
            embeddings=[embedding],
            metadatas=[metadata] if metadata else None,
        )

    def search_similar(self, query_embedding: list[float], n_results: int = 5) -> dict:
        """
        類似楽曲を検索する

        Args:
            query_embedding: 検索クエリのベクトル
            n_results: 取得件数

        Returns:
            検索結果（ids, distances, metadatas）
        """
        results = self.collection.query(
            query_embeddings=[query_embedding], n_results=n_results
        )
        return results

    def get_song(self, song_id: str) -> dict | None:
        """
        IDで楽曲を取得する

        Args:
            song_id: 楽曲ID

        Returns:
            楽曲情報（見つからない場合はNone）
        """
        result = self.collection.get(ids=[song_id])
        if result["ids"]:
            return {
                "id": result["ids"][0],
                "embedding": result["embeddings"][0] if result["embeddings"] else None,
                "metadata": result["metadatas"][0] if result["metadatas"] else None,
            }
        return None

    def delete_song(self, song_id: str) -> None:
        """
        楽曲を削除する

        Args:
            song_id: 楽曲ID
        """
        self.collection.delete(ids=[song_id])

    def count(self) -> int:
        """登録されている楽曲数を返す"""
        return self.collection.count()

    def list_all(self, limit: int = 100) -> dict:
        """
        登録されている楽曲一覧を取得する

        Args:
            limit: 取得件数上限

        Returns:
            楽曲一覧
        """
        return self.collection.get(limit=limit)


# ===== 動作確認用 =====
if __name__ == "__main__":
    import random

    print("=== ChromaDB 動作確認 ===\n")

    # DB初期化
    db = SongVectorDB(db_path="./data/chroma_test")
    print(f"現在の登録数: {db.count()}")

    # ダミーベクトル生成（128次元）
    def make_dummy_vector(seed: int) -> list[float]:
        random.seed(seed)
        return [random.random() for _ in range(128)]

    # テストデータ登録
    test_songs = [
        ("song_001", "アップテンポな曲A", 100),
        ("song_002", "バラード曲B", 200),
        ("song_003", "アップテンポな曲C", 101),  # song_001に近い
        ("song_004", "ジャズ曲D", 300),
        ("song_005", "バラード曲E", 201),  # song_002に近い
    ]

    print("\n--- 楽曲登録 ---")
    for song_id, title, seed in test_songs:
        db.add_song(
            song_id=song_id,
            embedding=make_dummy_vector(seed),
            metadata={"title": title, "seed": seed},
        )
        print(f"  登録: {song_id} ({title})")

    print(f"\n登録後の件数: {db.count()}")

    # 類似検索テスト
    print("\n--- 類似検索テスト ---")
    print("クエリ: song_001 に近いベクトル（seed=100）")

    query_vector = make_dummy_vector(100)
    results = db.search_similar(query_vector, n_results=3)

    print("結果:")
    for i, (id_, dist, meta) in enumerate(
        zip(results["ids"][0], results["distances"][0], results["metadatas"][0])
    ):
        print(f"  {i+1}. {id_} (距離: {dist:.4f}) - {meta['title']}")

    # クリーンアップ（テスト用）
    print("\n--- クリーンアップ ---")
    for song_id, _, _ in test_songs:
        db.delete_song(song_id)
    print(f"削除後の件数: {db.count()}")

    print("\n=== 完了 ===")
