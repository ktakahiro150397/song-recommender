"""
連鎖検索デバッグスクリプト
"""

from core.db_manager import SongVectorDB
from pathlib import Path

# DB初期化
db = SongVectorDB("data/chroma_db_cos_minimal")

# テスト用の曲ID
song_id = "Street Fighter 6 Alex's Theme - Go! Alex! Hope is Born! by JAM Project [nu4pDfXRsMA].wav"

print(f"検索対象: {song_id}")
print("=" * 80)

# 曲の存在確認
song = db.get_song(song_id)
if not song:
    print("❌ 曲が見つかりません")
else:
    print(f"✅ 曲が見つかりました")
    print(f"   Metadata: {song.get('metadata')}")

    # 類似検索
    results = db.search_similar(song["embedding"], n_results=10)
    print(f"\n類似曲検索結果: {len(results['ids'][0])}曲")
    print("-" * 80)

    for idx, (sid, dist, meta) in enumerate(
        zip(results["ids"][0], results["distances"][0], results["metadatas"][0]), 1
    ):
        source_dir = meta.get("source_dir") if meta else None
        print(f"{idx:2d}. {sid[:60]}")
        print(f"    Distance: {dist:.8f}")
        print(f"    Source: {source_dir}")
        print(f"    Metadata: {meta}")
        print()
