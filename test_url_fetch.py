"""
YouTube URL情報取得テストスクリプト

使い方:
    uv run python test_url_fetch.py "https://www.youtube.com/watch?v=..."
"""

import argparse
import sys
from ytmusicapi import YTMusic
from core.youtube_url_detector import YouTubeURLDetector
from core.song_queue_db import SongQueueDB


def test_url(url: str):
    """URLから情報を取得してテスト"""
    print("=" * 80)
    print("🔍 YouTube URL情報取得テスト")
    print("=" * 80)
    print(f"\nURL: {url}\n")

    # URLタイプを判別
    detector = YouTubeURLDetector()
    url_type, error_msg = detector.detect(url)

    print(f"📋 URLタイプ: {url_type}")
    if url_type == "unknown":
        print(f"❌ エラー: {error_msg}")
        return

    # 動画IDを抽出
    song_db = SongQueueDB()
    video_id = song_db.extract_video_id(url)

    if video_id:
        print(f"🎬 動画ID: {video_id}")
    else:
        print("⚠️  動画IDが見つかりません")

    # プレイリストIDを抽出（プレイリストタイプの場合）
    if url_type == "playlist":
        playlist_id = detector.extract_playlist_id(url)
        print(f"📋 プレイリストID: {playlist_id}")

    print("\n" + "-" * 80)
    print("🎵 YTMusic APIで情報取得中...\n")

    try:
        ytmusic = YTMusic()

        # 動画情報を取得
        if video_id:
            print("📺 動画情報:")
            print("-" * 80)
            try:
                video_info = ytmusic.get_song(video_id)

                if video_info:
                    # 指定された構造で取得
                    title = video_info["videoDetails"]["title"]
                    author = video_info["videoDetails"]["author"]
                    thumbnail_url = video_info["videoDetails"]["thumbnail"][
                        "thumbnails"
                    ][0]["url"]

                    print(f"✅ タイトル: {title}")
                    print(f"✅ アーティスト: {author}")
                    print(f"✅ サムネイル: {thumbnail_url}")

                    # アルバム情報
                    if "album" in video_info and video_info["album"]:
                        print(f"✅ アルバム: {video_info['album'].get('name', 'N/A')}")

                    # 長さ
                    if "duration_seconds" in video_info:
                        duration = video_info["duration_seconds"]
                        minutes = duration // 60
                        seconds = duration % 60
                        print(f"⏱️  長さ: {minutes}:{seconds:02d}")

                    # 生データ（デバッグ用）
                    print("\n📦 取得した全データ（キー一覧）:")
                    for key in video_info.keys():
                        value_preview = str(video_info[key])[:50]
                        print(f"   - {key}: {value_preview}...")
                else:
                    print("❌ 動画情報を取得できませんでした")

            except Exception as e:
                print(f"❌ 動画情報取得エラー: {str(e)}")
                import traceback

                traceback.print_exc()

        # プレイリスト情報を取得
        if url_type == "playlist":
            print("\n📋 プレイリスト情報:")
            print("-" * 80)
            try:
                playlist_id = detector.extract_playlist_id(url)
                if playlist_id:
                    # 自動生成プレイリスト（RDで始まる）は事前にチェック
                    if playlist_id.startswith("RD"):
                        print("❌ 自動生成プレイリスト（Radio、Mix）は対応していません")
                        print(f"   プレイリストID: {playlist_id}")
                    else:
                        playlist_info = ytmusic.get_playlist(playlist_id, limit=5)

                        print(f"✅ タイトル: {playlist_info.get('title', 'N/A')}")
                        print(
                            f"✅ 説明: {playlist_info.get('description', 'N/A')[:100]}..."
                        )

                        if "tracks" in playlist_info and playlist_info["tracks"]:
                            print(
                                f"✅ 曲数: {len(playlist_info['tracks'])}曲（最初の5曲のみ取得）"
                            )
                            print("\n📝 収録曲:")
                            for i, track in enumerate(playlist_info["tracks"][:5], 1):
                                title = track.get("title", "N/A")
                                artists = track.get("artists", [])
                                artist_names = (
                                    ", ".join([a["name"] for a in artists])
                                    if artists
                                    else "N/A"
                                )
                                video_id = track.get("videoId", "N/A")
                                print(f"   {i}. {title} - {artist_names}")
                                print(f"      動画ID: {video_id}")
                        else:
                            print("⚠️  トラック情報がありません")

                        # 生データ（デバッグ用）
                        print("\n📦 取得した全データ（キー一覧）:")
                        for key in playlist_info.keys():
                            if key == "tracks":
                                print(f"   - {key}: {len(playlist_info[key])}件")
                            else:
                                value_preview = str(playlist_info[key])[:50]
                                print(f"   - {key}: {value_preview}...")

            except Exception as e:
                print(f"❌ プレイリスト情報取得エラー: {str(e)}")
                import traceback

                traceback.print_exc()

    except Exception as e:
        print(f"❌ YTMusic初期化エラー: {str(e)}")
        import traceback

        traceback.print_exc()

    print("\n" + "=" * 80)
    print("✅ テスト完了")
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="YouTube URL情報取得テスト")
    parser.add_argument("url", help="テストするYouTube URL")

    args = parser.parse_args()

    test_url(args.url)


if __name__ == "__main__":
    main()
