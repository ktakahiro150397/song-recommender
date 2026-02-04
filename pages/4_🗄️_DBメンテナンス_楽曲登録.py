"""
DBメンテナンス - 楽曲登録ページ

アップロードした楽曲をベクトルDBに登録
"""

import streamlit as st
from pathlib import Path
import os
import re
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys

# 親ディレクトリをパスに追加（core/ と config.py をインポート可能にする）
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.db_manager import SongVectorDB
from core.feature_extractor import FeatureExtractor
from config import UPLOAD_DATA_DIR, DB_CONFIGS, AUDIO_DURATION

# ========== ページ設定 ==========
st.set_page_config(
    page_title="DBメンテナンス - 楽曲登録",
    page_icon="🗄️",
    layout="wide",
)

# ========== タイトル ==========
st.title("🗄️ DBメンテナンス - 楽曲登録")
st.write("アップロードした楽曲をベクトルDBに登録します。")

st.divider()


# ========== ヘルパー関数 ==========


def extract_youtube_id(filename: str) -> str | None:
    """
    ファイル名からYouTube動画IDを抽出する
    例: "曲名 [abcd1234XYZ].mp3" → "abcd1234XYZ"
    """
    match = re.search(r"\[([a-zA-Z0-9_-]{11})\]", filename)
    return match.group(1) if match else None


def extract_song_title(filename: str) -> str:
    """
    ファイル名から曲名を抽出する

    優先順位:
    1. 「」（カギ括弧）で囲われている → 最初の「」の中身
    2. 【】（すみカッコ）がある場合 → 【】で囲われていない部分を抽出
    3. 上記に該当しない → [videoId]と拡張子、()を除去した文字列
    """
    # 1. 「」（カギ括弧）を優先チェック
    kakko_match = re.search(r"「(.+?)」", filename)
    if kakko_match:
        return kakko_match.group(1).strip()

    # 2. 【】（すみカッコ）がある場合、その外側の文字列を抽出
    if "【" in filename and "】" in filename:
        # [videoId] と拡張子を先に除去
        temp = re.sub(r"\s*\[[a-zA-Z0-9_-]{11}\]\.(wav|mp3)$", "", filename)
        # 【...】を除去
        temp = re.sub(r"【[^】]*】", "", temp)
        # ()（丸括弧）と（）（全角丸括弧）を除去
        temp = re.sub(r"[\(（][^\)）]*[\)）]", "", temp)
        # 余分な空白を整理
        temp = re.sub(r"\s+", " ", temp).strip()
        if temp:
            return temp

    # 3. 従来のロジック: [videoId] と拡張子を除去
    temp = re.sub(r"\s*\[[a-zA-Z0-9_-]{11}\]\.(wav|mp3)$", "", filename)
    temp = re.sub(r"\s*\[[a-zA-Z0-9_-]{11}\]$", "", temp)
    temp = re.sub(r"\.(wav|mp3)$", "", temp)
    temp = re.sub(r"[\(（][^\)）]*[\)）]", "", temp)
    temp = re.sub(r"\s+", " ", temp).strip()

    return temp if temp else filename


def get_file_size_mb(file_path: str) -> float:
    """ファイルサイズをMB単位で取得"""
    try:
        size_bytes = os.path.getsize(file_path)
        return round(size_bytes / (1024 * 1024), 2)
    except OSError:
        return 0.0


def get_audio_files_recursive(base_dir: Path) -> list[tuple[str, str, str]]:
    """
    指定ディレクトリ配下の音声ファイルを再帰的に取得する

    Args:
        base_dir: ベースディレクトリ

    Returns:
        (実際のファイルパス, ファイル名, 正規化されたディレクトリ) のリスト
    """
    results = []

    for root, dirs, files in os.walk(base_dir):
        # 音声ファイルをフィルタ
        audio_files = [f for f in files if f.endswith((".wav", ".mp3"))]

        if not audio_files:
            continue

        # このディレクトリの相対パス（UPLOAD_DATA_DIRからの相対パス）
        try:
            relative_dir = Path(root).relative_to(base_dir)
            normalized_dir = str(relative_dir).replace("\\", "/")
        except ValueError:
            continue

        for filename in audio_files:
            file_path = os.path.join(root, filename)
            results.append((file_path, filename, normalized_dir))

    return results


def add_song(
    db: SongVectorDB,
    extractor: FeatureExtractor,
    file_path: str,
    filename: str,
    normalized_dir: str,
) -> bool:
    """
    1曲をDBに登録する

    Returns:
        登録したらTrue、スキップしたらFalse
    """
    # 既に登録済みならスキップ
    if db.get_song(song_id=filename) is not None:
        return False

    # 特徴量抽出
    embedding = extractor.extract_to_vector(file_path)

    # メタデータ構築
    youtube_id = extract_youtube_id(filename)
    song_title = extract_song_title(filename)
    _, ext = os.path.splitext(filename)

    metadata = {
        "filename": filename,
        "song_title": song_title,
        "source_dir": normalized_dir,
        "youtube_id": youtube_id,
        "file_extension": ext.lower(),
        "file_size_mb": get_file_size_mb(file_path),
        "registered_at": datetime.now().isoformat(),
    }

    db.add_song(song_id=filename, embedding=embedding, metadata=metadata)
    return True


# ========== メイン処理 ==========

st.subheader("📁 登録対象ディレクトリ")
st.info(f"**登録対象:** `{UPLOAD_DATA_DIR}`")

# アップロードディレクトリの存在確認
if not UPLOAD_DATA_DIR.exists():
    st.error(f"❌ ディレクトリが存在しません: `{UPLOAD_DATA_DIR}`")
    st.stop()

# 音声ファイルを取得
audio_files = get_audio_files_recursive(UPLOAD_DATA_DIR)

if not audio_files:
    st.warning("⚠️ 登録可能な音声ファイルが見つかりません。")
    st.info(
        "先に「📤 楽曲ファイルアップロード」ページでファイルをアップロードしてください。"
    )
    st.stop()

st.success(f"✅ {len(audio_files)} 件の音声ファイルが見つかりました。")

# ファイル一覧を表示
with st.expander("ファイル一覧を表示", expanded=False):
    current_dir = None
    for file_path, filename, normalized_dir in audio_files:
        if normalized_dir != current_dir:
            current_dir = normalized_dir
            st.write(f"**📁 {normalized_dir}/**")
        st.write(f"  - `{filename}`")

st.divider()

# 登録設定
st.subheader("⚙️ 登録設定")

col1, col2 = st.columns(2)
with col1:
    st.write(f"**DB設定数:** {len(DB_CONFIGS)}")
    for config in DB_CONFIGS:
        st.write(f"  - `{config['path']}` (mode: {config['mode']})")

with col2:
    st.write(f"**音声抽出時間:** {AUDIO_DURATION} 秒")

st.divider()

# 登録実行ボタン
st.subheader("🚀 登録実行")

if st.button("🎵 ベクトルDBに登録を開始", type="primary", use_container_width=True):
    # DB・抽出器を初期化
    dbs_and_extractors = []

    with st.spinner("DBを初期化中..."):
        for config in DB_CONFIGS:
            db = SongVectorDB(
                collection_name=config["collection"], distance_fn="cosine"
            )
            extractor = FeatureExtractor(duration=AUDIO_DURATION, mode=config["mode"])
            dbs_and_extractors.append((db, extractor, config["mode"]))

    st.success("✅ DB初期化完了")

    # ログ表示エリア
    log_container = st.container()
    status_text = st.empty()
    progress_bar = st.progress(0)

    total_added = 0
    total_skipped = 0

    # ThreadPoolで並列処理
    with ThreadPoolExecutor(max_workers=len(DB_CONFIGS)) as executor:
        for idx, (file_path, filename, normalized_dir) in enumerate(audio_files):
            # プログレス更新
            progress = (idx + 1) / len(audio_files)
            progress_bar.progress(progress)
            status_text.text(f"処理中... ({idx + 1}/{len(audio_files)}): {filename}")

            # 最初のDBでチェック（登録済みならスキップ）
            if dbs_and_extractors[0][0].get_song(song_id=filename) is not None:
                total_skipped += 1
                with log_container:
                    st.write(
                        f"⏭️ **[{idx + 1}/{len(audio_files)}]** スキップ（登録済み）: `{filename}`"
                    )
                continue

            # 全DBに並列で登録
            def process_for_db(db_ext_mode):
                db, extractor, mode = db_ext_mode
                return add_song(db, extractor, file_path, filename, normalized_dir)

            futures = [
                executor.submit(process_for_db, item) for item in dbs_and_extractors
            ]
            results = [f.result() for f in as_completed(futures)]

            if any(results):
                total_added += 1
                with log_container:
                    st.write(
                        f"✅ **[{idx + 1}/{len(audio_files)}]** 登録完了: `{filename}`"
                    )
                    st.caption(
                        f"   📁 {normalized_dir} | 🎵 {extract_song_title(filename)}"
                    )
            else:
                total_skipped += 1
                with log_container:
                    st.write(
                        f"⏭️ **[{idx + 1}/{len(audio_files)}]** スキップ: `{filename}`"
                    )

    # 完了
    progress_bar.progress(1.0)
    status_text.empty()

    st.divider()

    # 結果サマリー
    st.subheader("📊 登録結果")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("新規登録", f"{total_added} 曲")
    with col2:
        st.metric("スキップ", f"{total_skipped} 曲")
    with col3:
        total_in_db = dbs_and_extractors[0][0].count()
        st.metric("DB総登録数", f"{total_in_db} 曲")

    if total_added > 0:
        st.success(f"🎉 登録が完了しました！ {total_added} 曲を新規登録しました。")
    else:
        st.info("ℹ️ 新規登録する曲はありませんでした（すべて登録済み）。")

st.divider()
st.caption("💡 この画面では upload/data/ 配下の音声ファイルをベクトルDBに登録します。")
