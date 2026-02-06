#!/usr/bin/env python3
"""
プレイリストコメント機能のテストスクリプト
"""

from core import playlist_db


def test_comment_functionality():
    """コメント機能の基本テスト"""
    print("=== プレイリストコメント機能テスト ===\n")

    # テストデータ
    test_playlist_id = "test_playlist_001"
    test_user_sub = "test_user_sub"
    test_comment = "これはテストコメントです。"

    # 1. コメントを追加
    print("1. コメントを追加...")
    result = playlist_db.add_playlist_comment(
        playlist_id=test_playlist_id,
        user_sub=test_user_sub,
        comment=test_comment,
    )
    print(f"   結果: {'成功' if result else '失敗'}")

    # 2. コメント一覧を取得
    print("\n2. コメント一覧を取得...")
    comments = playlist_db.list_playlist_comments(test_playlist_id)
    print(f"   取得件数: {len(comments)}")
    if comments:
        latest_comment = comments[-1]
        print(f"   最新コメントID: {latest_comment['id']}")
        print(f"   コメント内容: {latest_comment['comment']}")
        print(f"   削除フラグ: {latest_comment.get('is_deleted', False)}")

        # 3. コメントを削除（論理削除）
        print("\n3. コメントを削除...")
        delete_result = playlist_db.delete_playlist_comment(
            comment_id=latest_comment['id'],
            user_sub=test_user_sub,
        )
        print(f"   結果: {'成功' if delete_result else '失敗'}")

        # 4. 削除後のコメント一覧を取得
        print("\n4. 削除後のコメント一覧を取得...")
        comments_after = playlist_db.list_playlist_comments(test_playlist_id)
        if comments_after:
            deleted_comment = [c for c in comments_after if c['id'] == latest_comment['id']]
            if deleted_comment:
                print(f"   削除フラグ: {deleted_comment[0].get('is_deleted', False)}")
                print(f"   期待値: True")
                if deleted_comment[0].get('is_deleted', False):
                    print("   ✅ 論理削除が正常に動作しています")
                else:
                    print("   ❌ 論理削除が正しく設定されていません")

    print("\n=== テスト完了 ===")


if __name__ == "__main__":
    try:
        test_comment_functionality()
    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
