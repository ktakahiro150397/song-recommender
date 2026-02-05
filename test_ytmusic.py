"""
YouTube Music API テストスクリプト

使い方:
1. secrets.jsonを作成（client_id, client_secretを記載）
2. 初回認証: uv run test_ytmusic.py --setup
3. 接続テスト: uv run test_ytmusic.py --test
4. プレイリスト作成テスト: uv run test_ytmusic.py --create "プレイリスト名"
5. プレイリスト一覧: uv run test_ytmusic.py --list
"""

import argparse
import os
from core.ytmusic_manager import YTMusicManager, setup_oauth

BROWSER_FILE = "browser.json"


def check_secrets_file() -> bool:
    """シークレットファイルの存在確認"""
    if not os.path.exists(BROWSER_FILE):
        print(f"❌ シークレットファイルが見つかりません: {BROWSER_FILE}")
        print("   以下の形式で作成してください:")
        print(
            '   {"client_id": "YOUR_CLIENT_ID", "client_secret": "YOUR_CLIENT_SECRET"}'
        )
        return False
    return True


def test_connection():
    """接続テスト"""
    print("=" * 50)
    print("🔗 YouTube Music 接続テスト")
    print("=" * 50)

    if not check_secrets_file():
        return False

    # if not os.path.exists(OAUTH_FILE):
    #     print(f"❌ 認証ファイルが見つかりません: {OAUTH_FILE}")
    #     print("   先に --setup で認証を行ってください")
    #     return False

    try:
        # まず認証なしで基本的な接続テスト
        print("   認証なし検索APIテスト中...")
        from ytmusicapi import YTMusic as YTMusicRaw

        yt_no_auth = YTMusicRaw()
        search_result = yt_no_auth.search("test", filter="songs", limit=1)
        print(f"   ✅ 認証なし検索API: OK")

        # 認証ありでテスト
        print("   認証ありでインスタンス作成中...")
        ytm = YTMusicManager(
            browser_file=BROWSER_FILE,
        )

        # 認証が必要なライブラリAPIでテスト
        print("   ライブラリAPIテスト中...")
        playlists = ytm.get_library_playlists()
        print(f"✅ 接続成功！")
        print(f"   プレイリスト数: {len(playlists)}")
        return True
    except Exception as e:
        print(f"❌ 接続失敗: {e}")
        print("\n💡 トラブルシューティング:")
        print("   1. oauth.json を削除して --setup で再認証")
        print("   2. secrets.json の client_id/client_secret を確認")
        print("   3. Google Cloud Console で OAuth 同意画面が設定済みか確認")
        import traceback

        traceback.print_exc()
        return False


def list_playlists():
    """プレイリスト一覧を表示"""
    print("=" * 50)
    print("📋 プレイリスト一覧")
    print("=" * 50)

    ytm = YTMusicManager(
        browser_file=BROWSER_FILE,
    )
    playlists = ytm.get_library_playlists()

    for i, p in enumerate(playlists, 1):
        count = p.get("count", "?")
        print(f"{i:3}. {p['title']} ({count} songs)")
        print(f"     ID: {p['playlistId']}")


def test_search():
    """検索テスト"""
    print("=" * 50)
    print("🔍 検索テスト")
    print("=" * 50)

    ytm = YTMusicManager(
        browser_file=BROWSER_FILE,
    )

    test_queries = [
        "宇多田ヒカル First Love",
        "YOASOBI 夜に駆ける",
        "Official髭男dism Pretender",
    ]

    for query in test_queries:
        print(f"\nQuery: {query}")
        result = ytm.search_video_id(query)
        if result:
            print(f"  ✅ {result['title']} - {result['artist']}")
            print(f"     videoId: {result['videoId']}")
        else:
            print(f"  ❌ Not found")


def test_create_playlist(playlist_name: str):
    """プレイリスト作成テスト"""
    print("=" * 50)
    print(f"🎵 プレイリスト作成テスト: {playlist_name}")
    print("=" * 50)

    ytm = YTMusicManager(
        browser_file=BROWSER_FILE,
    )

    # テスト用の曲リスト（検索クエリとして使用）
    test_songs = [
        "宇多田ヒカル First Love",
        "YOASOBI 夜に駆ける",
        "Official髭男dism Pretender",
        "King Gnu 白日",
        "米津玄師 Lemon",
    ]

    # song_data形式に変換 (query, is_video_id=False)
    song_data = [(song, False) for song in test_songs]

    result = ytm.create_or_replace_playlist(
        playlist_name=playlist_name,
        song_data=song_data,
        description="Song Recommender テストプレイリスト",
        privacy="PRIVATE",
        verbose=True,
    )

    print("\n" + "=" * 50)
    print("📊 結果サマリー")
    print("=" * 50)
    print(f"Playlist ID: {result['playlist_id']}")
    print(f"Found: {len(result['found_songs'])} songs")
    print(f"Not found: {len(result['not_found'])} queries")

    if result["not_found"]:
        print("\n見つからなかった曲:")
        for q in result["not_found"]:
            print(f"  - {q}")


def test_delete_playlist(playlist_id: str):
    """プレイリスト削除テスト"""
    print("=" * 50)
    print(f"🗑️ プレイリスト削除テスト: {playlist_id}")
    print("=" * 50)

    ytm = YTMusicManager(
        browser_file=BROWSER_FILE,
    )

    ytm.delete_playlist(playlist_id)
    print(f"✅ プレイリストを削除しました: {playlist_id}")


def main():
    parser = argparse.ArgumentParser(description="YouTube Music API テストスクリプト")
    parser.add_argument("--test", action="store_true", help="接続テストを実行")
    parser.add_argument("--list", action="store_true", help="プレイリスト一覧を表示")
    parser.add_argument("--search", action="store_true", help="検索テストを実行")
    parser.add_argument(
        "--create",
        type=str,
        metavar="NAME",
        help="テストプレイリストを作成",
    )
    parser.add_argument(
        "--delete",
        type=str,
        metavar="PLAYLIST_ID",
        help="指定したプレイリストを削除",
    )

    args = parser.parse_args()

    if args.test:
        test_connection()
        return

    if args.list:
        if not test_connection():
            return
        list_playlists()
        return

    if args.search:
        if not test_connection():
            return
        test_search()
        return

    if args.create:
        if not test_connection():
            return
        test_create_playlist(args.create)
        return

    if args.delete:
        if not test_connection():
            return
        test_delete_playlist(args.delete)
        return

    # 引数なしの場合はヘルプを表示
    parser.print_help()
    print("\n" + "=" * 50)
    print("📝 クイックスタート")
    print("=" * 50)
    print("1. 初回認証:        uv run test_ytmusic.py --setup")
    print("2. 接続テスト:      uv run test_ytmusic.py --test")
    print("3. 検索テスト:      uv run test_ytmusic.py --search")
    print("4. プレイリスト一覧: uv run test_ytmusic.py --list")
    print('5. 作成テスト:      uv run test_ytmusic.py --create "テスト"')


if __name__ == "__main__":
    main()
