"""
ChromaDB を使ったベクトルDB操作モジュール
"""

import chromadb
import os
from pathlib import Path
from typing import Literal


# 距離関数の型
DistanceFunction = Literal["l2", "cosine", "ip"]


class SongVectorDB:
    """楽曲ベクトルを管理するクラス"""

    def __init__(
        self,
        db_path: str | None = None,
        collection_name: str = "songs",
        distance_fn: DistanceFunction = "cosine",
        use_remote: bool = True,
    ):
        """
        Args:
            db_path: ChromaDBの永続化先パス（use_remote=Falseの場合のみ使用）
            collection_name: コレクション名
            distance_fn: 距離関数 ("l2", "cosine", "ip")
                - l2: ユークリッド距離（位置の近さ）
                - cosine: コサイン距離（向きの近さ、0〜2）
                - ip: 内積（類似度、大きいほど近い）
            use_remote: リモートのChromaDBサーバーを使用するか（デフォルト: True）
        """
        self.use_remote = use_remote

        if use_remote:
            # リモートChromaDBサーバーに接続
            chroma_host = os.getenv("CHROMA_HOST", "localhost")
            chroma_port = int(os.getenv("CHROMA_PORT", "8000"))
            self.client = chromadb.HttpClient(
                host=chroma_host,
                port=chroma_port,
            )
        else:
            # ローカルファイルベースのChromaDB（後方互換性のため残す）
            if db_path is None:
                db_path = "./data/chroma"
            # ディレクトリがなければ作成
            Path(db_path).mkdir(parents=True, exist_ok=True)
            self.client = chromadb.PersistentClient(path=db_path)

        self.distance_fn = distance_fn
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={
                "description": "楽曲の音声特徴量ベクトル",
                "hnsw:space": distance_fn,
            },
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

    def add_songs(
        self,
        song_ids: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict] | None = None,
    ) -> None:
        """
        複数の楽曲を一括でDBに登録する（バルクインサート）

        Args:
            song_ids: 楽曲IDのリスト
            embeddings: 音声特徴量ベクトルのリスト
            metadatas: 付加情報のリスト（オプション）
        """
        if not song_ids:
            return

        self.collection.add(
            ids=song_ids,
            embeddings=embeddings,
            metadatas=metadatas if metadatas else None,
        )

    def get_songs(self, song_ids: list[str], include_embedding: bool = False) -> dict:
        """
        複数のIDで楽曲を一括取得する（バルククエリ）

        Args:
            song_ids: 楽曲IDのリスト
            include_embedding: embeddingを含めるか（デフォルトFalse）

        Returns:
            楽曲情報の辞書（ids, embeddings, metadatas）
        """
        if not song_ids:
            return {"ids": [], "embeddings": [], "metadatas": []}

        include = ["metadatas"]
        if include_embedding:
            include.append("embeddings")

        result = self.collection.get(ids=song_ids, include=include)  # type: ignore
        return result

    def search_similar(
        self,
        query_embedding: list[float],
        n_results: int = 5,
        where: dict | None = None,
    ) -> dict:
        """
        類似楽曲を検索する

        Args:
            query_embedding: 検索クエリのベクトル
            n_results: 取得件数
            where: メタデータフィルタ（例: {"excluded_from_search": {"$ne": True}}）

        Returns:
            検索結果（ids, distances, metadatas）
        """
        results = self.collection.query(
            query_embeddings=[query_embedding], n_results=n_results, where=where
        )
        return results

    def get_song(
        self, song_id: str, include_embedding: bool = True, max_retries: int = 3
    ) -> dict | None:
        """
        IDで楽曲を取得する

        Args:
            song_id: 楽曲ID
            include_embedding: embeddingを含めるか（デフォルトTrue）
            max_retries: エラー時の最大リトライ回数

        Returns:
            楽曲情報（見つからない場合はNone）
        """
        import time

        include = ["metadatas"]
        if include_embedding:
            include.append("embeddings")

        for attempt in range(max_retries):
            try:
                result = self.collection.get(ids=[song_id], include=include)  # type: ignore
                break
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(0.5 * (attempt + 1))  # 指数バックオフ
                    continue
                # 最後のリトライでも失敗した場合はNoneを返す（未登録扱い）
                print(
                    f"Warning: Failed to get song '{song_id}' after {max_retries} retries: {e}"
                )
                return None
        if result["ids"]:
            # embeddingsの存在チェック（配列なのでNoneかどうかで判定）
            embeddings = result.get("embeddings")
            has_embeddings = embeddings is not None and len(embeddings) > 0

            return {
                "id": result["ids"][0],
                "embedding": (
                    result["embeddings"][0]
                    if include_embedding and has_embeddings
                    else None
                ),
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

    def get_by_youtube_id(self, youtube_id: str) -> dict | None:
        """
        YouTube動画IDで楽曲を検索する

        Args:
            youtube_id: YouTube動画ID（11文字）

        Returns:
            楽曲情報（見つからない場合はNone）
        """
        try:
            result = self.collection.get(
                where={"youtube_id": youtube_id}, include=["metadatas"]
            )
            if result["ids"] and len(result["ids"]) > 0:
                return {
                    "id": result["ids"][0],
                    "metadata": result["metadatas"][0] if result["metadatas"] else None,
                }
            return None
        except Exception as e:
            # エラー時はNoneを返す（未登録扱い）
            print(f"Warning: Failed to search by youtube_id '{youtube_id}': {e}")
            return None

    def list_all(self, limit: int = 100, where: dict | None = None) -> dict:
        """
        登録されている楽曲一覧を取得する

        Args:
            limit: 取得件数上限
            where: メタデータフィルタ（例: {"excluded_from_search": {"$ne": True}}）

        Returns:
            楽曲一覧
        """
        return self.collection.get(limit=limit, where=where)

    def update_metadata(self, song_id: str, metadata: dict) -> None:
        """
        楽曲のメタデータを更新する
        
        注意: このメソッドはメタデータを完全に置き換えます（マージではありません）
        既存のメタデータを保持したい場合は、先にget_song()で取得してから
        更新したいフィールドのみ変更してください。

        Args:
            song_id: 楽曲ID
            metadata: 更新するメタデータ（既存のメタデータを完全に置き換えます）
            
        Example:
            # 既存のメタデータを保持しながら更新
            song_data = db.get_song(song_id, include_embedding=False)
            metadata = song_data["metadata"]
            metadata["excluded_from_search"] = True
            db.update_metadata(song_id, metadata)
        """
        self.collection.update(ids=[song_id], metadatas=[metadata])


# ===== 動作確認用 =====
if __name__ == "__main__":
    import random

    print("=== ChromaDB 動作確認 ===\n")

    # ダミーベクトル生成（128次元）
    def make_dummy_vector(seed: int) -> list[float]:
        random.seed(seed)
        return [random.random() for _ in range(128)]

    # テストデータ
    test_songs = [
        ("song_001", "アップテンポな曲A", 100),
        ("song_002", "バラード曲B", 200),
        ("song_003", "アップテンポな曲C", 101),  # song_001に近い
        ("song_004", "ジャズ曲D", 300),
        ("song_005", "バラード曲E", 201),  # song_002に近い
    ]

    # ===== L2距離でテスト =====
    print("=" * 50)
    print("【L2距離（ユークリッド）】")
    print("=" * 50)

    db_l2 = SongVectorDB(
        db_path="./data/chroma_test_l2",
        collection_name="songs_l2",
        distance_fn="l2",
    )

    for song_id, title, seed in test_songs:
        db_l2.add_song(
            song_id=song_id,
            embedding=make_dummy_vector(seed),
            metadata={"title": title},
        )

    query_vector = make_dummy_vector(100)
    results = db_l2.search_similar(query_vector, n_results=3)

    print("クエリ: song_001 に近いベクトル")
    print("結果:")
    for i, (id_, dist, meta) in enumerate(
        zip(results["ids"][0], results["distances"][0], results["metadatas"][0])
    ):
        print(f"  {i+1}. {id_} (距離: {dist:.4f}) - {meta['title']}")

    # クリーンアップ
    for song_id, _, _ in test_songs:
        db_l2.delete_song(song_id)

    # ===== コサイン距離でテスト =====
    print("\n" + "=" * 50)
    print("【コサイン距離】")
    print("=" * 50)

    db_cosine = SongVectorDB(
        db_path="./data/chroma_test_cosine",
        collection_name="songs_cosine",
        distance_fn="cosine",
    )

    for song_id, title, seed in test_songs:
        db_cosine.add_song(
            song_id=song_id,
            embedding=make_dummy_vector(seed),
            metadata={"title": title},
        )

    results = db_cosine.search_similar(query_vector, n_results=3)

    print("クエリ: song_001 に近いベクトル")
    print("結果:")
    for i, (id_, dist, meta) in enumerate(
        zip(results["ids"][0], results["distances"][0], results["metadatas"][0])
    ):
        # コサイン距離を類似度に変換（0〜1、1が完全一致）
        similarity = 1 - dist / 2
        print(
            f"  {i+1}. {id_} (距離: {dist:.4f}, 類似度: {similarity:.2%}) - {meta['title']}"
        )

    # クリーンアップ
    for song_id, _, _ in test_songs:
        db_cosine.delete_song(song_id)

    print("\n=== 完了 ===")
