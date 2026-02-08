"""
song_queueテーブルにartist_name、thumbnail_url、source_dirカラムを追加するマイグレーションスクリプト
"""

from sqlalchemy import text
from core.database import get_session


def migrate_song_queue():
    """song_queueテーブルに新しいカラムを追加"""
    print("=" * 60)
    print("🔧 song_queueテーブルのマイグレーション開始")
    print("=" * 60)

    with get_session() as session:
        # 既存のカラムを確認
        print("\n📊 現在のテーブル構造を確認中...")
        result = session.execute(text("SHOW COLUMNS FROM song_queue"))
        existing_columns = {row[0] for row in result}
        print(f"既存のカラム: {', '.join(existing_columns)}")

        # 追加するカラムのリスト
        columns_to_add = [
            ("artist_name", "VARCHAR(200) NULL COMMENT 'アーティスト名'"),
            ("thumbnail_url", "TEXT NULL COMMENT 'サムネイルURL'"),
            (
                "source_dir",
                "VARCHAR(100) NOT NULL DEFAULT 'youtube' COMMENT 'ソースディレクトリ'",
            ),
        ]

        # カラムを追加
        for column_name, column_def in columns_to_add:
            if column_name not in existing_columns:
                print(f"\n✨ カラム '{column_name}' を追加中...")
                try:
                    session.execute(
                        text(
                            f"ALTER TABLE song_queue ADD COLUMN {column_name} {column_def}"
                        )
                    )
                    session.commit()
                    print(f"✅ カラム '{column_name}' を追加しました")
                except Exception as e:
                    print(f"❌ カラム '{column_name}' の追加に失敗: {str(e)}")
                    session.rollback()
                    raise
            else:
                print(f"⏭️  カラム '{column_name}' は既に存在します")

        # マイグレーション後のテーブル構造を確認
        print("\n📊 マイグレーション後のテーブル構造:")
        result = session.execute(text("SHOW COLUMNS FROM song_queue"))
        for row in result:
            print(f"  - {row[0]}: {row[1]} {row[2]} {row[3]}")

    print("\n" + "=" * 60)
    print("✅ マイグレーション完了！")
    print("=" * 60)


if __name__ == "__main__":
    try:
        migrate_song_queue()
    except Exception as e:
        print(f"\n❌ マイグレーションエラー: {str(e)}")
        exit(1)
