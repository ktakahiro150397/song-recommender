"""
データベース初期化・マイグレーションスクリプト

新しいテーブル（songs, processed_collections）を作成し、
既存のChromaDBからMySQLへメタデータを移行する。
"""

import sys
from core.database import init_database, get_session
from core.models import Song, ProcessedCollection
from core.db_manager import SongVectorDB
from config import DB_CONFIGS
from datetime import datetime


def create_tables():
    """新しいテーブルを作成する"""
    print("=" * 60)
    print("テーブルを作成中...")
    print("=" * 60)

    try:
        init_database()
        print("✅ テーブルの作成に成功しました")
        print("  - songs")
        print("  - processed_collections")
        return True
    except Exception as e:
        print(f"❌ テーブルの作成に失敗しました: {e}")
        return False


def migrate_metadata_from_chromadb():
    """ChromaDBからMySQLへメタデータを移行する"""
    print("\n" + "=" * 60)
    print("ChromaDBからMySQLへメタデータを移行中...")
    print("=" * 60)

    total_migrated = 0

    for db_config in DB_CONFIGS:
        collection_name = db_config["collection"]
        print(f"\n📦 コレクション: {collection_name}")

        try:
            # ChromaDBに接続
            db = SongVectorDB(
                collection_name=collection_name, distance_fn="cosine", use_remote=True
            )

            # 全曲を取得（最大100万曲）
            print(f"  楽曲データを取得中...")
            result = db.list_all(limit=1000000)

            if not result.get("ids"):
                print(f"  ⏭️  データがありません")
                continue

            song_ids = result["ids"]
            metadatas = result.get("metadatas", [])

            print(f"  {len(song_ids)} 曲見つかりました")

            # MySQLに移行
            migrated = 0
            skipped = 0

            with get_session() as session:
                for i, song_id in enumerate(song_ids):
                    metadata = metadatas[i] if i < len(metadatas) else {}

                    # メタデータがない場合はスキップ（新形式のデータ）
                    if not metadata or len(metadata) <= 1:
                        skipped += 1
                        continue

                    # このコレクションで既に処理されているかチェック
                    existing_processed = (
                        session.query(ProcessedCollection)
                        .filter(
                            ProcessedCollection.song_id == song_id,
                            ProcessedCollection.collection_name == collection_name,
                        )
                        .first()
                    )

                    if existing_processed:
                        skipped += 1
                        continue

                    # songsテーブルに存在しなければ新規作成
                    if not session.get(Song, song_id):
                        song = Song(
                            song_id=song_id,
                            filename=metadata.get("filename", song_id),
                            song_title=metadata.get("song_title", ""),
                            artist_name=metadata.get("artist_name", ""),
                            source_dir=metadata.get("source_dir", ""),
                            youtube_id=metadata.get("youtube_id", ""),
                            file_extension=metadata.get("file_extension", ""),
                            file_size_mb=metadata.get("file_size_mb", 0.0),
                            bpm=metadata.get("bpm"),
                            registered_at=(
                                datetime.fromisoformat(metadata["registered_at"])
                                if metadata.get("registered_at")
                                else datetime.now()
                            ),
                            excluded_from_search=metadata.get(
                                "excluded_from_search", False
                            ),
                        )
                        session.add(song)
                        session.flush()  # 即座にデータベースに反映させる

                    # このコレクション用のProcessedCollectionレコードを作成
                    processed = ProcessedCollection(
                        song_id=song_id,
                        collection_name=collection_name,
                        processed_at=datetime.now(),
                    )
                    session.add(processed)

                    migrated += 1

                    if (migrated + skipped) % 100 == 0:
                        print(
                            f"  進捗: {migrated + skipped}/{len(song_ids)} 曲処理済み"
                        )

            print(f"  ✅ {migrated} 曲をMySQLに移行しました")
            print(f"  ⏭️  {skipped} 曲はスキップしました（既存または新形式）")
            total_migrated += migrated

        except Exception as e:
            print(f"  ❌ エラー: {e}")
            import traceback

            traceback.print_exc()
            continue

    print("\n" + "=" * 60)
    print(f"✅ 合計 {total_migrated} 曲をMySQLに移行しました")
    print("=" * 60)

    return total_migrated > 0


def main():
    """メイン処理"""
    print("\n" + "=" * 60)
    print("データベース初期化・マイグレーション")
    print("=" * 60)

    # ステップ1: テーブル作成
    if not create_tables():
        print("\n❌ 処理を中断します")
        sys.exit(1)

    # ステップ2: メタデータ移行の確認
    print("\n" + "=" * 60)
    response = input("ChromaDBからMySQLへメタデータを移行しますか？ (y/N): ")
    if response.lower() in ["y", "yes"]:
        migrate_metadata_from_chromadb()
    else:
        print("⏭️  メタデータの移行をスキップしました")

    print("\n" + "=" * 60)
    print("✅ すべての処理が完了しました")
    print("=" * 60)


if __name__ == "__main__":
    main()
