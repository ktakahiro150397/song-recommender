"""
SQLite から MySQL へのデータ移行スクリプト

既存のSQLiteデータベースから新しいMySQLデータベースにデータを移行します。
実行前に MySQL が起動していることを確認してください。
"""

import sqlite3
from pathlib import Path
from datetime import datetime
from core.database import get_session, init_database
from core.models import SongQueue, YouTubeChannel


def migrate_song_queue():
    """song_queue テーブルのデータを移行"""
    sqlite_path = Path("./data/song_queue.db")

    if not sqlite_path.exists():
        print(f"⚠️  {sqlite_path} が見つかりません。スキップします。")
        return

    print(f"\n📁 {sqlite_path} からデータを移行中...")

    # SQLite から読み取り
    with sqlite3.connect(sqlite_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT video_id, url, title, status, registered_at, processed_at FROM song_queue"
        )
        rows = cursor.fetchall()

    if not rows:
        print("   データが見つかりませんでした。")
        return

    # MySQL に書き込み
    migrated = 0
    skipped = 0

    with get_session() as session:
        for row in rows:
            try:
                # datetimeに変換
                registered_at = (
                    datetime.fromisoformat(row["registered_at"])
                    if row["registered_at"]
                    else datetime.now()
                )
                processed_at = (
                    datetime.fromisoformat(row["processed_at"])
                    if row["processed_at"]
                    else None
                )

                # 重複チェック
                existing = (
                    session.query(SongQueue).filter_by(video_id=row["video_id"]).first()
                )
                if existing:
                    skipped += 1
                    continue

                # 新規追加
                song = SongQueue(
                    video_id=row["video_id"],
                    url=row["url"],
                    title=row["title"],
                    status=row["status"],
                    registered_at=registered_at,
                    processed_at=processed_at,
                )
                session.add(song)
                migrated += 1

            except Exception as e:
                print(f"   ⚠️  エラー: {row['video_id']} - {e}")
                continue

        session.commit()

    print(f"   ✅ 移行完了: {migrated}件, スキップ: {skipped}件")


def migrate_youtube_channels():
    """youtube_channels テーブルのデータを移行"""
    sqlite_path = Path("./data/youtube_channels.db")

    if not sqlite_path.exists():
        print(f"⚠️  {sqlite_path} が見つかりません。スキップします。")
        return

    print(f"\n📁 {sqlite_path} からデータを移行中...")

    # SQLite から読み取り
    with sqlite3.connect(sqlite_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            """
            SELECT url, channel_id, channel_name, thumbnail_url, registered_at, output_count 
            FROM youtube_channels
            """
        )
        rows = cursor.fetchall()

    if not rows:
        print("   データが見つかりませんでした。")
        return

    # MySQL に書き込み
    migrated = 0
    skipped = 0

    with get_session() as session:
        for row in rows:
            try:
                # datetimeに変換
                registered_at = (
                    datetime.fromisoformat(row["registered_at"])
                    if row["registered_at"]
                    else datetime.now()
                )

                # 重複チェック
                existing = (
                    session.query(YouTubeChannel).filter_by(url=row["url"]).first()
                )
                if existing:
                    skipped += 1
                    continue

                # 新規追加
                channel = YouTubeChannel(
                    url=row["url"],
                    channel_id=row["channel_id"],
                    channel_name=row["channel_name"],
                    thumbnail_url=row["thumbnail_url"],
                    registered_at=registered_at,
                    output_count=row["output_count"] or 0,
                )
                session.add(channel)
                migrated += 1

            except Exception as e:
                print(f"   ⚠️  エラー: {row['channel_id']} - {e}")
                continue

        session.commit()

    print(f"   ✅ 移行完了: {migrated}件, スキップ: {skipped}件")


def main():
    """メイン処理"""
    print("=" * 60)
    print("🚀 SQLite → MySQL データ移行ツール")
    print("=" * 60)

    try:
        # データベース初期化
        print("\n📦 MySQLデータベースを初期化中...")
        init_database()
        print("   ✅ 初期化完了")

        # song_queue 移行
        migrate_song_queue()

        # youtube_channels 移行
        migrate_youtube_channels()

        print("\n" + "=" * 60)
        print("✅ すべてのデータ移行が完了しました！")
        print("=" * 60)
        print("\n💡 次のステップ:")
        print("   1. 古いSQLiteファイルをバックアップ")
        print("   2. アプリケーションを再起動してMySQLで動作確認")
        print("   3. 問題なければSQLiteファイルを削除可能")

    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
        print("\n原因の可能性:")
        print("   - MySQLが起動していない")
        print("   - 環境変数が正しく設定されていない")
        print("   - MySQLへの接続権限がない")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
