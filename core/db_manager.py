"""
ChromaDB を使ったベクトルDB操作モジュール
"""

import chromadb
import os
from pathlib import Path
from typing import Literal


# 距離関数の型
DistanceFunction = Literal["l2", "cosine", "ip"]

# ランダムサンプリングの閾値（この値以上の曲数で効率的な方法を使用）
LARGE_DB_THRESHOLD = 10000


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
        self,
        song_id: str,
        embedding: list[float],
        excluded_from_search: bool = False,
        source_dir: str | None = None,
    ) -> None:
        """
        楽曲をDBに登録する（ベクトルと最小限のメタデータのみ）

        Args:
            song_id: 楽曲の一意なID
            embedding: 音声特徴量ベクトル
            excluded_from_search: 検索除外フラグ（デフォルト: False）
            source_dir: ソースディレクトリ（オプション）
        """
        metadata = {"excluded_from_search": excluded_from_search}
        if source_dir is not None:
            metadata["source_dir"] = source_dir
        self.collection.add(
            ids=[song_id],
            embeddings=[embedding],
            metadatas=[metadata],
        )

    def add_songs(
        self,
        song_ids: list[str],
        embeddings: list[list[float]],
        excluded_flags: list[bool] | None = None,
        source_dirs: list[str] | None = None,
    ) -> None:
        """
        複数の楽曲を一括でDBに登録する（バルクインサート）

        Args:
            song_ids: 楽曲IDのリスト
            embeddings: 音声特徴量ベクトルのリスト
            excluded_flags: 検索除外フラグのリスト（オプション、デフォルトはすべてFalse）
            source_dirs: ソースディレクトリのリスト（オプション）
        """
        if not song_ids:
            return

        metadatas = []
        for i, song_id in enumerate(song_ids):
            metadata = {
                "excluded_from_search": (excluded_flags or [False] * len(song_ids))[i]
            }
            if source_dirs and i < len(source_dirs) and source_dirs[i] is not None:
                metadata["source_dir"] = source_dirs[i]
            metadatas.append(metadata)

        self.collection.add(
            ids=song_ids,
            embeddings=embeddings,
            metadatas=metadatas,
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

    def list_all(self, limit: int = 100, where: dict | None = None) -> dict:
        """
        登録されている楽曲一覧を取得する

        Args:
            limit: 取得件数上限
            where: メタデータフィルタ（例: {"excluded_from_search": {"$ne": True}}）

        Returns:
            楽曲一覧（IDとexcluded_from_searchフラグのみ）
        """
        return self.collection.get(limit=limit, where=where)

    def update_excluded_from_search(self, song_id: str, excluded: bool) -> None:
        """
        楽曲の検索除外フラグを更新する

        Args:
            song_id: 楽曲ID
            excluded: 検索除外フラグ

        Example:
            db.update_excluded_from_search(song_id, True)  # 検索から除外
            db.update_excluded_from_search(song_id, False)  # 検索対象に含める
        """
        metadata = {"excluded_from_search": excluded}
        self.collection.update(ids=[song_id], metadatas=[metadata])

    def get_random_sample(self, sample_percentage: float = 0.05) -> dict:
        """
        データベースからランダムにサンプリングする

        メモリ効率的な実装：
        - 小規模DB（<10k曲）: 全件読み込み後にランダムサンプリング
        - 大規模DB（>=10k曲）: IDのみ読み込み→ランダム選択→該当曲のみ取得

        これにより100万曲規模のデータベースでもメモリを圧迫しません。

        Args:
            sample_percentage: サンプリング率（デフォルト: 0.05 = 5%）

        Returns:
            ランダムサンプリングされた楽曲一覧（ids, embeddings, metadatas）
        """
        import random

        total_count = self.count()
        if total_count == 0:
            return {"ids": [], "embeddings": [], "metadatas": []}

        # サンプルサイズを計算（最小10曲、最大1000曲、total_countを超えない）
        target_sample = int(total_count * sample_percentage)
        sample_size = max(min(10, total_count), min(target_sample, 1000, total_count))

        # 大規模DBの場合はメモリ効率的な方法を使用
        if total_count >= LARGE_DB_THRESHOLD:
            # Step 1: IDのみを取得（メモリ効率的）
            all_ids_result = self.collection.get(limit=total_count, include=[])

            if not all_ids_result["ids"]:
                return {"ids": [], "embeddings": [], "metadatas": []}

            all_ids = all_ids_result["ids"]

            # Step 2: ランダムにIDを選択（実際の取得件数に合わせて調整）
            actual_sample_size = min(sample_size, len(all_ids))
            sampled_ids = random.sample(all_ids, actual_sample_size)

            # Step 3: 選択されたIDの楽曲のみ取得
            sampled_songs = self.collection.get(
                ids=sampled_ids, include=["embeddings", "metadatas"]
            )

            return {
                "ids": sampled_songs["ids"],
                "embeddings": sampled_songs.get("embeddings", []),
                "metadatas": sampled_songs.get("metadatas", []),
            }
        else:
            # 小規模DBの場合は従来の方法（全件取得→ランダム選択）
            all_songs = self.collection.get(
                limit=total_count, include=["embeddings", "metadatas"]
            )

            if not all_songs["ids"]:
                return {"ids": [], "embeddings": [], "metadatas": []}

            # ランダムにインデックスを選択
            indices = list(range(len(all_songs["ids"])))
            random.shuffle(indices)
            sampled_indices = indices[:sample_size]

            # サンプリングされたデータを抽出
            embeddings_data = all_songs.get("embeddings")
            metadatas_data = all_songs.get("metadatas")

            # embeddings と metadatas について、None でなく、要素を持つかチェック
            has_embeddings = (
                embeddings_data is not None
                and hasattr(embeddings_data, "__len__")
                and len(embeddings_data) > 0
            )
            has_metadatas = (
                metadatas_data is not None
                and hasattr(metadatas_data, "__len__")
                and len(metadatas_data) > 0
            )

            sampled_data = {
                "ids": [all_songs["ids"][i] for i in sampled_indices],
                "embeddings": (
                    [all_songs["embeddings"][i] for i in sampled_indices]
                    if has_embeddings
                    else []
                ),
                "metadatas": (
                    [all_songs["metadatas"][i] for i in sampled_indices]
                    if has_metadatas
                    else []
                ),
            }

            return sampled_data


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
