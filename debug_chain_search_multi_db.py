"""
連鎖検索デバッグスクリプト（複数DB対応）
"""

from core.db_manager import SongVectorDB
from create_playlist_from_chain import chain_search_to_list, DB_PATHS
from pathlib import Path

# テスト用の曲ID
song_id = "Street Fighter 6 Alex's Theme - Go! Alex! Hope is Born! by JAM Project [nu4pDfXRsMA].wav"

print(f"検索対象: {song_id}")
print("=" * 80)

# 全てのDBを初期化
dbs = [
    SongVectorDB(db_path=path, distance_fn="cosine")
    for path in DB_PATHS
    if Path(path).exists()
]

print(f"使用するDB数: {len(dbs)}")
for i, db_path in enumerate(DB_PATHS):
    if Path(db_path).exists():
        print(f"  {i+1}. {db_path}")

print("\n" + "=" * 80)
print("連鎖検索を実行中...")
print("=" * 80)

# 連鎖検索実行
results = chain_search_to_list(
    start_filename=song_id,
    dbs=dbs,
    n_songs=10,
)

print("\n" + "=" * 80)
print(f"結果: {len(results)}曲")
print("=" * 80)

if results:
    for idx, (sid, distance, metadata) in enumerate(results, 1):
        source_dir = metadata.get("source_dir") if metadata else "unknown"
        print(f"{idx:2d}. {sid[:60]}")
        print(f"    Distance: {distance:.8f}")
        print(f"    Source: {source_dir}")
        print()
else:
    print("❌ 連鎖検索結果が空です")
