import argparse
from core.ytmusic_manager import YTMusicManager
from ytmusicapi import YTMusic

ytm = YTMusic()

def get_channel_metadata(channel_id: str) -> dict:
    """指定されたYouTubeチャンネルのメタデータを取得する"""
    
    return ytm.get_artist(channel_id)

    return {
        "title": "Sample Channel",
        "description": "This is a sample YouTube channel.",
        "subscriber_count": 12345,
    }

def get_channel_song_ids(channel_url: str) -> list[str]:
    """指定されたYouTubeチャンネルから曲IDのリストを取得するダミー関数"""
    # 実際の実装では、YouTube Data APIなどを使用してチャンネルの動画情報を取得し、
    # そこから曲IDを抽出します。
    return ["song_id_1", "song_id_2", "song_id_3"]

def create_download_script(song_ids: list[str], output_file: str) -> None:
    """曲IDのリストからダウンロードスクリプトを作成するダミー関数"""
    with open(output_file, "w") as f:
        f.write("#!/bin/bash\n")
        for song_id in song_ids:
            f.write(f"yt-dlp https://www.youtube.com/watch?v={song_id}\n")
    print(f"ダウンロードスクリプトが作成されました: {output_file}")

def main():
    parser = argparse.ArgumentParser(description="YouTube ダウンロードスクリプト作成ツール")
    parser.add_argument("--url", type=str, required=True, help="YouTubeチャンネルのURL", metavar="URL")
    parser.add_argument("--output", type=str, required=False, help="出力スクリプトファイルのパス",metavar="OUTPUT_FILE")
    args = parser.parse_args()

    # https://music.youtube.com/channel/UC8p5DuhOMR7fZLgnybVX0sA
    channel_metadata = get_channel_metadata(args.url)
    print(channel_metadata)
    channel_song_ids = get_channel_song_ids(args.url)

    fallback_filename = "fallback.ps1"
    output_file = args.output if args.output else fallback_filename

    create_download_script(channel_song_ids, output_file)

if __name__ == "__main__":
    main()