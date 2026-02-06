"""
ChromaDBの embedding 存在確認スクリプト（全件チェック）
"""

from core.db_manager import SongVectorDB
from config import DB_CONFIGS

print("=" * 60)
print("🔍 ChromaDB embedding 状態確認（全件チェック）")
print("=" * 60)

for config in DB_CONFIGS:
    print(f"\n📊 {config['collection']}")
    print("-" * 60)

    db = SongVectorDB(collection_name=config["collection"], distance_fn="cosine")
    total_count = db.count()
    print(f"   総曲数: {total_count}")

    # 全曲をバッチ処理でチェック
    if total_count > 0:
        batch_size = 1000
        without_embedding = []
        without_source_dir = []

        for batch_start in range(0, total_count, batch_size):
            batch_end = min(batch_start + batch_size, total_count)
            print(f"   チェック中: {batch_end}/{total_count}", end="\r")

            result = db.collection.get(
                limit=batch_size,
                offset=batch_start,
                include=["embeddings", "metadatas"],
            )

            for i, song_id in enumerate(result.get("ids", [])):
                embedding = (
                    result.get("embeddings")[i]
                    if result.get("embeddings") is not None
                    else None
                )
                metadata = (
                    result.get("metadatas")[i]
                    if result.get("metadatas") is not None
                    else {}
                )

                has_embedding = embedding is not None and len(embedding) > 0
                has_source_dir = "source_dir" in metadata

                if not has_embedding:
                    without_embedding.append(song_id)
                if not has_source_dir:
                    without_source_dir.append(song_id)

        print(f"   チェック完了: {total_count}/{total_count}  ")
        print(
            f"\n   ✅ embedding あり: {total_count - len(without_embedding)}/{total_count}"
        )
        print(
            f"   ✅ source_dir あり: {total_count - len(without_source_dir)}/{total_count}"
        )

        if without_embedding:
            print(f"\n   ❌ embedding なし: {len(without_embedding)} 曲")
            print(f"      最初の10件: {without_embedding[:10]}")
            if len(without_embedding) > 10:
                print(f"      ... 他 {len(without_embedding) - 10} 曲")

        if without_source_dir:
            print(f"\n   ❌ source_dir なし: {len(without_source_dir)} 曲")
            print(f"      最初の10件: {without_source_dir[:10]}")
            if len(without_source_dir) > 10:
                print(f"      ... 他 {len(without_source_dir) - 10} 曲")
