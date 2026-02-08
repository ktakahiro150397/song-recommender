"""Add header_comment and create playlist_comments table."""

from sqlalchemy import text
from core.database import get_session


def migrate_playlist_comments() -> None:
    """DB migration for playlist comments."""
    print("=" * 60)
    print("playlist_comments migration start")
    print("=" * 60)

    with get_session() as session:
        print("\nChecking playlist_headers columns...")
        result = session.execute(text("SHOW COLUMNS FROM playlist_headers"))
        existing_columns = {row[0] for row in result}
        print(f"Existing columns: {', '.join(existing_columns)}")

        if "header_comment" not in existing_columns:
            print("\nAdding header_comment column...")
            try:
                session.execute(
                    text(
                        "ALTER TABLE playlist_headers "
                        "ADD COLUMN header_comment TEXT NULL COMMENT 'Header comment' "
                        "AFTER creator_sub"
                    )
                )
                session.commit()
                print("Added header_comment column")
            except Exception as e:
                print(f"Failed to add header_comment: {str(e)}")
                session.rollback()
                raise
        else:
            print("header_comment column already exists")

        print("\nChecking playlist_comments table...")
        table_result = session.execute(text("SHOW TABLES LIKE 'playlist_comments'"))
        existing_table = table_result.first()

        if not existing_table:
            print("\nCreating playlist_comments table...")
            try:
                playlist_id_column = session.execute(
                    text("SHOW FULL COLUMNS FROM playlist_headers LIKE 'playlist_id'")
                ).first()
                collation = None
                column_type = "VARCHAR(200)"
                if playlist_id_column:
                    mapping = playlist_id_column._mapping
                    column_type = mapping.get("Type", column_type)
                    collation = mapping.get("Collation")

                charset = None
                if collation:
                    charset = collation.split("_")[0]

                playlist_id_sql = column_type
                if collation and charset:
                    playlist_id_sql = (
                        f"{column_type} CHARACTER SET {charset} COLLATE {collation}"
                    )

                table_charset_sql = ""
                if collation and charset:
                    table_charset_sql = f" CHARSET={charset} COLLATE={collation}"

                session.execute(
                    text(
                        "CREATE TABLE playlist_comments ("
                        "id INT AUTO_INCREMENT PRIMARY KEY, "
                        f"playlist_id {playlist_id_sql} NOT NULL, "
                        "user_sub VARCHAR(200) NOT NULL, "
                        "comment TEXT NOT NULL, "
                        "created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, "
                        "INDEX idx_playlist_comment_playlist (playlist_id, created_at), "
                        "INDEX idx_playlist_comment_user (user_sub), "
                        "CONSTRAINT fk_playlist_comments_playlist "
                        "FOREIGN KEY (playlist_id) "
                        "REFERENCES playlist_headers(playlist_id) ON DELETE CASCADE"
                        ")"
                        f"{table_charset_sql}"
                    )
                )
                session.commit()
                print("Created playlist_comments table")
            except Exception as e:
                print(f"Failed to create playlist_comments: {str(e)}")
                session.rollback()
                raise
        else:
            print("playlist_comments table already exists")

    print("\n" + "=" * 60)
    print("Migration complete")
    print("=" * 60)


if __name__ == "__main__":
    try:
        migrate_playlist_comments()
    except Exception as e:
        print(f"\nMigration error: {str(e)}")
        raise
