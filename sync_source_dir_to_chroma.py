"""
MySQLからChromaDBへsource_dirを同期するスクリプト

用途:
    従来のバグで source_dir メタデータが記録されていない曲が存在する場合、
    MySQLに存在する source_dir をChromaDBに反映させます。

使い方:
    uv run sync_source_dir_to_chroma.py
    uv run sync_source_dir_to_chroma.py --dry-run    # 確認のみ（実際には変更しない）
    uv run sync_source_dir_to_chroma.py --collection songs_full  # 特定のコレクションのみ
"""

import argparse
import sys
from core.db_manager import SongVectorDB
from core import song_metadata_db
from config import DB_CONFIGS


def sync_source_dir_for_collection(
    collection_name: str, dry_run: bool = False
) -> tuple[int, int, list[str]]:
    """
    1つのコレクションについて source_dir を同期

    Args:
        collection_name: 同期対象のコレクション名
        dry_run: Trueの場合、確認のみで実際には変更しない

    Returns:
        (同期した曲数, スキップ数, エラーリスト)
    """
    print(f"\n{'='*60}")
    print(f"📊 {collection_name} を同期中...")
    print("=" * 60)

    # DB接続
    try:
        db = SongVectorDB(collection_name=collection_name, distance_fn="cosine")
        print(f"✅ {collection_name} に接続しました")
    except Exception as e:
        print(f"❌ {collection_name} への接続に失敗: {str(e)}")
        return 0, 0, [f"Connection error: {str(e)}"]

    # MySQLから全曲を取得（キーワード検索で全件取得）
    print("\n📝 MySQLから全曲を取得中...")
    song_list = song_metadata_db.search_by_keyword(
        "", limit=1000000, exclude_from_search=False
    )
    all_songs = [{"song_id": song_id, **metadata} for song_id, metadata in song_list]
    print(f"✅ {len(all_songs)} 曲を取得しました")

    synced_count = 0
    skipped_count = 0
    errors = []

    # 各曲をチェック
    for idx, song in enumerate(all_songs, 1):
        song_id = song["song_id"]
        mysql_source_dir = song.get("source_dir", "")

        # source_dirが空の場合はスキップ
        if not mysql_source_dir:
            skipped_count += 1
            continue

        # ChromaDBから取得
        try:
            result = db.get_songs([song_id], include_embedding=False)

            if not result.get("ids"):
                # ChromaDB に存在しない（MySQL のみ）-> スキップ
                skipped_count += 1
                continue

            # メタデータを確認
            metadata = (
                result.get("metadatas", [{}])[0] if result.get("metadatas") else {}
            )
            chroma_source_dir = metadata.get("source_dir", "")

            # source_dir が既に存在する場合はスキップ
            if chroma_source_dir:
                skipped_count += 1
                continue

            # source_dir が存在しない -> 更新が必要
            print(f"\n[{idx}] {song_id}")
            print(f"   MySQL: source_dir = '{mysql_source_dir}'")
            print(f"   ChromaDB: source_dir なし")

            if not dry_run:
                # ChromaDB の update メソッドを使用（metadata のみ更新、embedding は保持）
                # 既存レコードは削除せず、メタデータのみ更新
                excluded_from_search = metadata.get("excluded_from_search", False)

                print(f"   ⏳ 更新中...")

                db.collection.update(
                    ids=[song_id],
                    metadatas=[
                        {
                            "excluded_from_search": excluded_from_search,
                            "source_dir": mysql_source_dir,
                        }
                    ],
                )

                print(f"   ✅ 更新完了")
                synced_count += 1
            else:
                print(f"   [DRY RUN] 更新対象")
                synced_count += 1

        except Exception as e:
            error_msg = f"{song_id}: {str(e)}"
            errors.append(error_msg)
            print(f"   ❌ エラー: {str(e)}")

    return synced_count, skipped_count, errors


def main():
    parser = argparse.ArgumentParser(description="MySQLからChromaDBへsource_dirを同期")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="確認のみで実際には変更しない",
    )
    parser.add_argument(
        "--collection",
        type=str,
        help="特定のコレクションのみ同期（デフォルトは全コレクション）",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("🔄 MySQL → ChromaDB source_dir 同期スクリプト")
    print("=" * 60)

    if args.dry_run:
        print("\n⚠️  ドライラン模式 - 実際には変更しません")

    # 同期対象のコレクション
    if args.collection:
        target_collections = [args.collection]
    else:
        target_collections = [config["collection"] for config in DB_CONFIGS]

    total_synced = 0
    total_skipped = 0
    all_errors = []

    # 各コレクションを同期
    for collection_name in target_collections:
        synced, skipped, errors = sync_source_dir_for_collection(
            collection_name, dry_run=args.dry_run
        )
        total_synced += synced
        total_skipped += skipped
        all_errors.extend(errors)

    # 結果サマリー
    print("\n" + "=" * 60)
    print("📊 結果サマリー")
    print("=" * 60)
    print(f"   同期対象: {total_synced} 曲")
    print(f"   スキップ: {total_skipped} 曲（既に存在 or source_dir なし）")

    if all_errors:
        print(f"\n   ❌ エラー: {len(all_errors)} 件")
        for error in all_errors[:10]:  # 最初の10件のみ表示
            print(f"      - {error}")
        if len(all_errors) > 10:
            print(f"      ... 他 {len(all_errors) - 10} 件")

    if args.dry_run:
        print("\n✅ ドライラン完了")
    else:
        print("\n✅ 同期完了！")


if __name__ == "__main__":
    main()
