r"""
既存の楽曲にBPMを追加するマイグレーションスクリプト

既存のデータベース内の楽曲で、BPMが未設定（NULL）のものについて、
元の音声ファイルから特徴量を抽出してBPMを更新します。

使い方:
    uv run migrate_bpm.py [--base-path <path>] [--limit <number>] [--dry-run]

オプション:
    --base-path: 音声ファイルのベースパス（デフォルト: F:\song-recommender-data\data）
    --limit: 処理する曲数の上限（デフォルト: 全件）
    --dry-run: 実際には更新せず、処理内容のみ表示
"""

import argparse
import os
import sys
from pathlib import Path
from sqlalchemy import select
from core.database import get_session
from core.models import Song
from core.feature_extractor import FeatureExtractor

# デフォルトのベースパス（register_songs.pyのSOUND_DIRSに合わせる）
DEFAULT_BASE_PATH = r"F:\song-recommender-data\data"


def find_audio_file(base_path: str, source_dir: str, song_id: str) -> str | None:
    """
    音声ファイルのフルパスを構築して存在確認

    Args:
        base_path: ベースディレクトリ（例: "F:/song-recommender-data/data"）
        source_dir: ソースディレクトリ（例: "gakumas_mv"）
        song_id: 楽曲ID（ファイル名、例: "song.mp3"）

    Returns:
        ファイルが存在する場合はフルパス、存在しない場合はNone
    """
    # パスを正規化
    base_path = base_path.replace("\\", "/")
    source_dir = source_dir.replace("\\", "/")
    
    # ファイルパスを構築: base_path/source_dir/song_id
    file_path = os.path.join(base_path, source_dir, song_id)
    
    if os.path.exists(file_path):
        return file_path
    
    # data/を含むパスの場合も試す
    if not source_dir.startswith("data/"):
        file_path_with_data = os.path.join(base_path, "data", source_dir, song_id)
        if os.path.exists(file_path_with_data):
            return file_path_with_data
    
    return None


def extract_bpm_from_file(file_path: str) -> float | None:
    """
    音声ファイルからBPMを抽出

    Args:
        file_path: 音声ファイルのパス

    Returns:
        BPM値、抽出できない場合はNone
    """
    try:
        # 特徴量抽出器を初期化（BPMのみ必要なので短時間で処理）
        extractor = FeatureExtractor(duration=30)  # 30秒で十分
        features = extractor.extract(file_path)
        return features.tempo
    except Exception as e:
        print(f"   ⚠️  BPM抽出エラー: {e}")
        return None


def migrate_bpm(base_path: str, limit: int | None = None, dry_run: bool = False):
    """
    BPMが未設定の楽曲を更新

    Args:
        base_path: 音声ファイルのベースパス
        limit: 処理する曲数の上限（Noneの場合は全件）
        dry_run: Trueの場合は実際には更新しない
    """
    print("=" * 60)
    print("🎵 BPMマイグレーションスクリプト")
    print("=" * 60)
    print(f"ベースパス: {base_path}")
    print(f"モード: {'DRY RUN (更新しない)' if dry_run else '本番実行'}")
    print("=" * 60)

    # BPMがNULLの楽曲を取得
    with get_session() as session:
        stmt = select(Song).where(Song.bpm.is_(None))
        if limit:
            stmt = stmt.limit(limit)
        
        songs = list(session.execute(stmt).scalars().all())
        total_songs = len(songs)

    if total_songs == 0:
        print("\n✅ BPMが未設定の楽曲はありません")
        return

    print(f"\n📊 BPMが未設定の楽曲: {total_songs}件")
    print()

    # 統計情報
    updated_count = 0
    file_not_found_count = 0
    extraction_failed_count = 0

    # 各楽曲を処理
    for idx, song in enumerate(songs, 1):
        print(f"[{idx}/{total_songs}] {song.song_id}")
        print(f"   source_dir: {song.source_dir}")
        
        # ファイルパスを構築
        file_path = find_audio_file(base_path, song.source_dir, song.song_id)
        
        if file_path is None:
            print(f"   ❌ ファイルが見つかりません")
            file_not_found_count += 1
            continue
        
        print(f"   📁 ファイル: {file_path}")
        
        # BPMを抽出
        bpm = extract_bpm_from_file(file_path)
        
        if bpm is None:
            print(f"   ❌ BPM抽出失敗")
            extraction_failed_count += 1
            continue
        
        print(f"   ✅ BPM: {bpm:.1f}")
        
        # データベースを更新
        if not dry_run:
            with get_session() as session:
                # セッション内で楽曲を再取得して更新
                song_to_update = session.get(Song, song.song_id)
                if song_to_update:
                    song_to_update.bpm = bpm
                    session.commit()
                    updated_count += 1
        else:
            updated_count += 1  # dry-runでもカウント
        
        print()

    # 結果サマリー
    print("=" * 60)
    print("📊 結果サマリー")
    print("=" * 60)
    print(f"処理対象: {total_songs}件")
    print(f"更新成功: {updated_count}件")
    print(f"ファイル未検出: {file_not_found_count}件")
    print(f"BPM抽出失敗: {extraction_failed_count}件")
    
    if dry_run:
        print("\n⚠️  DRY RUNモードのため、実際にはデータベースは更新されていません")
        print("   本番実行する場合は --dry-run オプションを外してください")
    else:
        print("\n✅ マイグレーション完了")


def main():
    """メイン処理"""
    parser = argparse.ArgumentParser(
        description="既存の楽曲にBPMを追加するマイグレーションスクリプト"
    )
    parser.add_argument(
        "--base-path",
        default=DEFAULT_BASE_PATH,
        help=f"音声ファイルのベースパス（デフォルト: {DEFAULT_BASE_PATH}）",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="処理する曲数の上限（デフォルト: 全件）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="実際には更新せず、処理内容のみ表示",
    )

    args = parser.parse_args()

    try:
        # ベースパスの存在確認
        if not os.path.exists(args.base_path):
            print(f"❌ エラー: ベースパス '{args.base_path}' が存在しません")
            print(f"\n💡 ヒント: --base-path オプションで正しいパスを指定してください")
            return 1

        # マイグレーション実行
        migrate_bpm(args.base_path, args.limit, args.dry_run)
        return 0

    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
