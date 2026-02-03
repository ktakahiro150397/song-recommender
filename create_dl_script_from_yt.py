import argparse
import traceback
from pathlib import Path

from attr import dataclass
from core.ytmusic_manager import YTMusicManager
from core.channel_db import ChannelDB
from ytmusicapi import YTMusic

ytm = YTMusic()


@dataclass
class ChannelSongData:
    channel_id: str
    video_id: str
    title: str
    artists: list[str]
    album: str


def _parse_track(channel_id: str, song: dict) -> ChannelSongData | None:
    """トラック情報をパースしてChannelSongDataを返す"""
    # タイトルがNoneの場合はスキップ
    if song.get("title") is None:
        print(f'Skipping track with no title: {song.get("videoId", "Unknown")}')
        return None

    # Inst / Off Vocal を除く
    title = song["title"].lower()
    if (
        "inst" in title
        or "off vocal" in title
        or "game size" in title
        or "anime size" in title
    ):
        print(f'Skipping instrumental/off vocal track: {song["title"]}')
        return None

    # アーティスト情報を取得（Noneの場合は空リスト）
    artists_data = song.get("artists") or []
    if isinstance(artists_data, list):
        artists = [
            item.get("name", "Unknown Artist")
            for item in artists_data
            if item and isinstance(item, dict)
        ]
    else:
        artists = ["Unknown Artist"]

    # アーティストが空の場合はデフォルト値を設定
    if not artists:
        artists = ["Unknown Artist"]

    # アルバム情報を取得
    album_data = song.get("album")
    if album_data and isinstance(album_data, dict):
        album = album_data.get("name", "Unknown Album")
    else:
        album = "Unknown Album"

    return ChannelSongData(
        channel_id=channel_id,
        video_id=song["videoId"],
        title=song["title"],
        artists=artists,
        album=album,
    )


def get_aritst_songs(channel_id: str) -> list[ChannelSongData]:
    """指定されたYouTubeチャンネルの曲一覧を取得する"""
    artist = ytm.get_artist(channel_id)
    ret_songs: list[ChannelSongData] = []

    # まずsongsセクションから取得を試みる
    if "songs" in artist and artist["songs"] is not None:
        browseId = artist["songs"].get("browseId")
        if browseId is not None:
            print(f"  📀 songsセクションから曲を取得中...")
            songs = ytm.get_playlist(playlistId=browseId, limit=None)
            for song in songs["tracks"]:
                parsed = _parse_track(channel_id, song)
                if parsed:
                    ret_songs.append(parsed)

    # songsから取得できなかった場合、singlesから取得
    if not ret_songs:
        if "singles" in artist and artist["singles"] is not None:
            singles_results = artist["singles"].get("results", [])
            if singles_results:
                print(
                    f"  📀 singlesセクションから曲を取得中... ({len(singles_results)}件のシングル/アルバム)"
                )
                for single in singles_results:
                    album_browse_id = single.get("browseId")
                    if album_browse_id:
                        try:
                            album_data = ytm.get_album(album_browse_id)
                            album_name = album_data.get("title", "Unknown Album")
                            for track in album_data.get("tracks", []):
                                # アルバム情報を追加
                                track["album"] = {"name": album_name}
                                parsed = _parse_track(channel_id, track)
                                if parsed:
                                    ret_songs.append(parsed)
                        except Exception as e:
                            print(f"    ⚠ アルバム取得エラー ({album_browse_id}): {e}")

    # それでも取得できなかった場合
    if not ret_songs:
        print(f"  ⚠ このアーティストから曲を取得できませんでした")

    return ret_songs


def get_most_common_artist(song_data: list[ChannelSongData]) -> str:
    """曲リストから最も頻出するアーティスト名を取得する"""
    from collections import Counter

    # 全曲の全アーティストをカウント
    artist_counter: Counter[str] = Counter()
    for song in song_data:
        for artist in song.artists:
            artist_counter[artist] += 1

    # 最頻出のアーティストを返す（なければ最初の曲の最初のアーティスト）
    if artist_counter:
        return artist_counter.most_common(1)[0][0]
    return song_data[0].artists[0]


def create_download_script(
    song_data: list[ChannelSongData], output_file: str, delay_ms: int = 100
) -> None:
    """曲IDのリストからダウンロードスクリプトを作成する"""
    artist_name = get_most_common_artist(song_data)
    base_dir = "F:\\song-recommender-data\\data"
    artist_dir = f"{base_dir}\\{artist_name}"

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("# PowerShell スクリプト\n")
        f.write(f"# Generated by create_dl_script_from_yt.py\n\n")
        f.write(f"# Channel ID: {song_data[0].channel_id}\n")
        f.write(f"# Total songs: {len(song_data)}\n\n")

        # アーティスト名フォルダを作成して移動
        f.write(f"# アーティストフォルダを作成して移動\n")
        f.write(f'mkdir -Force "{artist_dir}"\n')
        f.write(f'Set-Location "{artist_dir}"\n\n')

        for i, song_item in enumerate(song_data):
            f.write(f"# {song_item.title} - {', '.join(song_item.artists)}\n")
            f.write(
                f"yt-dlp -x --audio-format wav --no-overwrites https://www.youtube.com/watch?v={song_item.video_id}\n"
            )
            # 最後の曲以外はディレイを追加
            if delay_ms > 0 and i < len(song_data) - 1:
                f.write(f"Start-Sleep -Milliseconds {delay_ms}\n")
            f.write("\n")
    print(f"ダウンロードスクリプトが作成されました: {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="YouTube ダウンロードスクリプト作成ツール"
    )
    parser.add_argument(
        "--url",
        type=str,
        required=False,
        help="YouTubeチャンネルのURLまたはID",
        metavar="URL_OR_ID",
    )
    parser.add_argument(
        "--channel-id",
        type=str,
        required=False,
        help="YouTubeチャンネルID (UCから始まる)",
        metavar="CHANNEL_ID",
    )
    parser.add_argument(
        "--output",
        type=str,
        required=False,
        help="出力先フォルダのパス（指定しない場合はカレントディレクトリ）",
        metavar="OUTPUT_DIR",
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        help="SQLiteから指定したoutput_countのチャンネルを一括で処理する",
    )
    parser.add_argument(
        "--output-count",
        type=int,
        default=0,
        help="--batch時に対象とするoutput_countの値（デフォルト: 0）",
        metavar="COUNT",
    )
    parser.add_argument(
        "--delay",
        type=int,
        default=100,
        help="各ダウンロード間のディレイミリ秒（デフォルト: 100ms）",
        metavar="SECONDS",
    )
    parser.add_argument(
        "--parallel",
        type=int,
        default=3,
        help="run_all.ps1での並列実行数（デフォルト: 3）",
        metavar="NUM",
    )

    args = parser.parse_args()

    channel_db = ChannelDB()

    # 一括処理モード
    if args.batch:
        target_count = args.output_count
        channels = channel_db.get_channels_with_zero_output(target_count)
        if not channels:
            print(f"output_count={target_count}のチャンネルはありません。")
            return

        print(f"\noutput_count={target_count}のチャンネル: {len(channels)}件")
        for idx, ch in enumerate(channels, 1):
            print(
                f"{idx}. {ch.get('channel_name', 'Unknown')} (ID: {ch['channel_id']})"
            )

        print("\n一括処理を開始します...\n")

        # 出力先フォルダを作成（実行日時でサブフォルダを作成）
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        base_output_dir = Path(args.output) if args.output else Path(".")
        output_dir = base_output_dir / timestamp
        output_dir.mkdir(parents=True, exist_ok=True)
        print(f"出力先: {output_dir.absolute()}\n")

        success_count = 0
        fail_count = 0
        generated_scripts: list[str] = []  # 生成したスクリプトのパスを追跡

        for ch in channels:
            channel_id = ch["channel_id"]
            channel_name = ch.get("channel_name", "Unknown")

            print(f"処理中: {channel_name} (ID: {channel_id})")

            try:
                channel_metadata = get_aritst_songs(channel_id)

                if channel_metadata is None or len(channel_metadata) == 0:
                    print(f"  ⚠ 曲を取得できませんでした\n")
                    fail_count += 1
                    continue

                # ファイル名を生成（最頻出アーティスト名を使用）
                artist_name = get_most_common_artist(channel_metadata)
                filename = f"scripts_{artist_name}_{channel_metadata[0].channel_id}.ps1"
                output_file = output_dir / filename

                create_download_script(channel_metadata, str(output_file), args.delay)
                generated_scripts.append(filename)  # 生成したファイル名を追跡

                # output_countをインクリメント
                success, message = channel_db.increment_output_count(channel_id)
                if success:
                    print(f"  ✓ {message}\n")
                    success_count += 1
                else:
                    print(f"  ⚠ {message}\n")
                    fail_count += 1

            except Exception as e:
                print(f"  ✗ エラー: {str(e)}")
                traceback.print_exc()
                print()
                fail_count += 1

        print(f"\n一括処理完了: 成功 {success_count}件 / 失敗 {fail_count}件")

        # run_all.ps1を生成（成功したスクリプトがある場合）
        if generated_scripts:
            run_all_path = output_dir / "run_all.ps1"
            with open(run_all_path, "w", encoding="utf-8") as f:
                f.write("# 全スクリプト並列実行\n")
                f.write(f"# Generated by create_dl_script_from_yt.py\n")
                f.write(f"# 並列実行数: {args.parallel}\n\n")

                f.write("$scriptDir = $PSScriptRoot\n")
                f.write("$scripts = @(\n")
                for script in generated_scripts:
                    f.write(f'    "{script}"\n')
                f.write(")\n\n")

                f.write(f"$maxParallel = {args.parallel}\n\n")

                f.write(
                    'Write-Host "=== 並列ダウンロード開始 ===" -ForegroundColor Green\n'
                )
                f.write(
                    'Write-Host "スクリプト数: $($scripts.Count), 並列数: $maxParallel" -ForegroundColor Cyan\n'
                )
                f.write('Write-Host ""\n\n')

                # Start-Jobを使用して並列実行し、定期的に出力を取得
                f.write("$jobs = @()\n")
                f.write("$jobScriptMap = @{}\n\n")

                f.write("foreach ($script in $scripts) {\n")
                f.write(
                    "    # 実行中のジョブが上限に達している場合は待機しながら出力を取得\n"
                )
                f.write(
                    "    while (($jobs | Where-Object { $_.State -eq 'Running' }).Count -ge $maxParallel) {\n"
                )
                f.write("        foreach ($j in $jobs) {\n")
                f.write("            if ($j.HasMoreData) {\n")
                f.write("                $output = Receive-Job -Job $j\n")
                f.write("                if ($output) { Write-Host $output }\n")
                f.write("            }\n")
                f.write("        }\n")
                f.write("        Start-Sleep -Milliseconds 200\n")
                f.write("    }\n")
                f.write("    \n")
                f.write("    $scriptPath = Join-Path $scriptDir $script\n")
                f.write('    Write-Host "[開始] $script" -ForegroundColor Cyan\n')
                f.write("    $job = Start-Job -ScriptBlock {\n")
                f.write("        param($path)\n")
                f.write("        & $path\n")
                f.write("    } -ArgumentList $scriptPath\n")
                f.write("    $jobs += $job\n")
                f.write("    $jobScriptMap[$job.Id] = $script\n")
                f.write("}\n\n")

                f.write("# 全ジョブの完了を待機しながら出力を取得\n")
                f.write(
                    'Write-Host "\n全ジョブの完了を待機中..." -ForegroundColor Yellow\n'
                )
                f.write("while ($jobs | Where-Object { $_.State -eq 'Running' }) {\n")
                f.write("    foreach ($j in $jobs) {\n")
                f.write("        if ($j.HasMoreData) {\n")
                f.write("            $output = Receive-Job -Job $j\n")
                f.write("            if ($output) { Write-Host $output }\n")
                f.write("        }\n")
                f.write("    }\n")
                f.write("    Start-Sleep -Milliseconds 200\n")
                f.write("}\n\n")

                f.write("# 残りの出力を取得\n")
                f.write("foreach ($j in $jobs) {\n")
                f.write("    $output = Receive-Job -Job $j\n")
                f.write("    if ($output) { Write-Host $output }\n")
                f.write("    $scriptName = $jobScriptMap[$j.Id]\n")
                f.write("    if ($j.State -eq 'Completed') {\n")
                f.write(
                    '        Write-Host "[完了] $scriptName" -ForegroundColor Green\n'
                )
                f.write("    } else {\n")
                f.write(
                    '        Write-Host "[エラー] $scriptName : $($j.State)" -ForegroundColor Red\n'
                )
                f.write("    }\n")
                f.write("}\n\n")

                f.write("# ジョブをクリーンアップ\n")
                f.write("$jobs | Remove-Job -Force\n")
                f.write('Write-Host "\n=== 全て完了! ===" -ForegroundColor Green\n')

            print(f"\n並列実行スクリプトを作成しました: {run_all_path}")
            print(f"  実行方法: .\\{run_all_path.name}")

        return

    # 単一チャンネル処理モード
    channel_id_from_db = None

    if args.channel_id:
        # --channel-idが指定された場合はそれを使用
        channel_id = args.channel_id
        # SQLiteからチャンネル情報を取得
        channel_info = channel_db.get_channel_by_id(channel_id)
        if channel_info:
            channel_id_from_db = channel_info["channel_id"]
            print(
                f"SQLiteからチャンネル情報を取得しました: {channel_info.get('channel_name', 'Unknown')}"
            )
        else:
            print(f"警告: チャンネルID '{channel_id}' はSQLiteに登録されていません")
    elif args.url:
        # --urlが指定された場合
        # URLからchannel_idを抽出
        if args.url.startswith("UC"):
            # UCで始まる場合はそのままIDとして扱う
            channel_id = args.url
        elif "channel/" in args.url:
            # URLからchannel_idを抽出
            channel_id = args.url.split("channel/")[-1].rstrip("/")
        else:
            print("エラー: 無効なURLまたはID形式です")
            print(
                "使用例: --url https://music.youtube.com/channel/UCxxxxx または --channel-id UCxxxxx"
            )
            return

        # SQLiteからチャンネル情報を取得
        channel_info = channel_db.get_channel_by_id(channel_id)
        if channel_info:
            channel_id_from_db = channel_info["channel_id"]
            print(
                f"SQLiteからチャンネル情報を取得しました: {channel_info.get('channel_name', 'Unknown')}"
            )
        else:
            print(f"警告: チャンネルID '{channel_id}' はSQLiteに登録されていません")
    else:
        print("エラー: --url または --channel-id のいずれかを指定してください")
        return

    # https://music.youtube.com/channel/UC8p5DuhOMR7fZLgnybVX0sA
    channel_metadata = get_aritst_songs(channel_id)
    # print(channel_metadata)

    if channel_metadata is None or len(channel_metadata) == 0:
        print("指定されたチャンネルから曲を取得できませんでした。")
        return

    # 出力先フォルダを作成
    output_dir = Path(args.output) if args.output else Path(".")
    output_dir.mkdir(parents=True, exist_ok=True)

    # ファイル名を生成（最頻出アーティスト名を使用）
    artist_name = get_most_common_artist(channel_metadata)
    filename = f"scripts_{artist_name}_{channel_metadata[0].channel_id}.ps1"
    output_file = output_dir / filename

    create_download_script(channel_metadata, str(output_file), args.delay)

    # SQLiteにoutput_countをインクリメント
    if channel_id_from_db:
        success, message = channel_db.increment_output_count(channel_id_from_db)
        if success:
            print(message)
        else:
            print(f"警告: {message}")


if __name__ == "__main__":
    main()
