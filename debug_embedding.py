"""
特定の曲のEmbeddingを確認するスクリプト
"""

from core.db_manager import SongVectorDB
from config import DB_CONFIGS

search_term = "ナイトループ"  # 部分検索で見つける

print("=" * 60)
print(f"🔍 '{search_term}' の Embedding 確認")
print("=" * 60)

for config in DB_CONFIGS:
    print(f"\n📊 {config['collection']}")
    print("-" * 60)

    db = SongVectorDB(collection_name=config["collection"], distance_fn="cosine")

    # 部分検索で候補を探す
    result = db.collection.get(limit=100000, include=["metadatas"])

    matching_ids = []
    for i, song_id in enumerate(result.get("ids", [])):
        if search_term in song_id:
            matching_ids.append(song_id)

    if matching_ids:
        print(f"✅ {len(matching_ids)}件見つかりました:")
        for song_id in matching_ids[:5]:  # 最初の5件
            print(f"   - {song_id}")

        # 最初にマッチした曲のEmbeddingを取得
        song_id = matching_ids[0]
        print(f"\n📌 詳細確認: {song_id}")

        result = db.get_songs([song_id], include_embedding=True)

        if result.get("ids"):
            embedding = result["embeddings"][0] if result.get("embeddings") else None
            metadata = result["metadatas"][0] if result.get("metadatas") else {}

            print(f"   Metadata: {metadata}")

            if embedding:
                print(f"   Embedding 次元数: {len(embedding)}")
                print(f"   Embedding 先頭20個: {embedding[:20]}")
                print(f"   Embedding 統計:")
                print(f"      Min: {min(embedding):.6f}")
                print(f"      Max: {max(embedding):.6f}")
                print(f"      Mean: {sum(embedding) / len(embedding):.6f}")
            else:
                print(f"   ❌ Embedding が None です")
    else:
        print(f"❌ '{search_term}' を含む曲が見つかりません")
