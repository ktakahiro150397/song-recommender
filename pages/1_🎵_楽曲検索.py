"""
楽曲検索ページ

キーワードで楽曲を検索して類似曲を表示
"""

import streamlit as st
import pandas as pd
from pathlib import Path
import re
import random

from core.db_manager import SongVectorDB
from core import song_metadata_db
from core import playlist_db
from core.ui_styles import style_distance_column, style_distance_value
from create_playlist_from_chain import (
    chain_search_to_list,
    filename_to_query,
    extract_video_id_from_filename,
    BROWSER_FILE,
)
from core.ytmusic_manager import YTMusicManager

# ========== 設定 ==========
from config import DB_CONFIGS

DB_PATHS = {
    "Full": "songs_full",
    "Balance": "songs_balanced",
    "Minimal": "songs_minimal",
}

# ========== ユーティリティ関数 ==========


def find_song_by_keyword_with_metadata(
    db: SongVectorDB, keyword: str = "", limit: int = 100
) -> list[tuple[str, dict]]:
    """キーワードで部分一致検索（メタデータ付き）

    Args:
        db: データベースインスタンス
        keyword: 検索キーワード（空文字列の場合は全件取得）
        limit: 最大表示件数

    Returns:
        (song_id, metadata)のタプルのリスト
    """
    if keyword:
        # MySQLでキーワード検索（セッション内で辞書化済み）
        matches = song_metadata_db.search_by_keyword(
            keyword, limit=limit, exclude_from_search=True
        )
    else:
        # 全曲取得（セッション内で辞書化済み）
        matches = song_metadata_db.list_all(limit=limit, exclude_from_search=True)

    return matches


def get_recently_added_songs(
    db: SongVectorDB, limit: int = 50
) -> list[tuple[str, dict]]:
    """最近追加された楽曲を取得（registered_atでソート）

    Args:
        db: データベースインスタンス
        limit: 最大取得件数

    Returns:
        (song_id, metadata)のタプルのリスト（新しい順）
    """
    # MySQLから最近追加された曲を取得（ORDER BY registered_at DESC）
    from sqlalchemy import select
    from core.models import Song
    from core.database import get_session

    with get_session() as session:
        stmt = (
            select(Song)
            .where(Song.excluded_from_search == False)
            .order_by(Song.registered_at.desc())
            .limit(limit)
        )
        songs = list(session.execute(stmt).scalars().all())

    return [
        (
            song.song_id,
            {
                "filename": song.filename,
                "song_title": song.song_title,
                "artist_name": song.artist_name,
                "bpm": song.bpm,
                "youtube_id": song.youtube_id,
                "file_extension": song.file_extension,
                "file_size_mb": song.file_size_mb,
                "registered_at": song.registered_at.isoformat(),
                "excluded_from_search": song.excluded_from_search,
            },
        )
        for song in songs
    ]


@st.cache_data(show_spinner=False)
def get_source_dir_names() -> list[str]:
    return song_metadata_db.list_source_dir_names(exclude_from_search=True)


def get_random_songs(db: SongVectorDB, limit: int = 50) -> list[tuple[str, dict]]:
    """ランダムに楽曲を取得

    Args:
        db: データベースインスタンス
        limit: 取得件数（デフォルト: 50）

    Returns:
        (song_id, metadata)のタプルのリスト（ランダム順）
    """
    # MySQLからランダムに曲を取得（ORDER BY RAND()）
    from sqlalchemy import select, func
    from core.models import Song
    from core.database import get_session

    with get_session() as session:
        stmt = (
            select(Song)
            .where(Song.excluded_from_search == False)
            .order_by(func.rand())
            .limit(limit)
        )
        songs = list(session.execute(stmt).scalars().all())

        # セッション内で属性にアクセスしてディクショナリを構築
        result = [
            (
                song.song_id,
                {
                    "filename": song.filename,
                    "song_title": song.song_title,
                    "artist_name": song.artist_name,
                    "bpm": song.bpm,
                    "youtube_id": song.youtube_id,
                    "file_extension": song.file_extension,
                    "file_size_mb": song.file_size_mb,
                    "registered_at": song.registered_at.isoformat(),
                    "excluded_from_search": song.excluded_from_search,
                },
            )
            for song in songs
        ]

    return result


# ========== メイン画面 ==========

st.set_page_config(
    page_title="楽曲検索",
    page_icon="🎵",
    layout="wide",
)

st.title("🎵 楽曲検索")
st.caption("キーワードで楽曲を検索して類似曲を表示、プレイリスト作成も可能")

# セッション状態の初期化
if "chain_results" not in st.session_state:
    st.session_state.chain_results = None
if "chain_selected_song" not in st.session_state:
    st.session_state.chain_selected_song = None
if "playlist_creating" not in st.session_state:
    st.session_state.playlist_creating = False
if "selected_songs" not in st.session_state:
    st.session_state.selected_songs = []
if "selected_song_id" not in st.session_state:
    st.session_state.selected_song_id = None
if "matches" not in st.session_state:
    st.session_state.matches = None
if "last_keyword" not in st.session_state:
    st.session_state.last_keyword = None

# サイドバー設定
st.sidebar.header("検索設定")

# DB選択（リモートChromaDBサーバーを使用するため、ファイル存在チェックは不要）
available_dbs = DB_PATHS  # すべてのDBを利用可能として扱う

if not available_dbs:
    st.error("利用可能なDBが見つかりません。")
    st.stop()

selected_db_name = st.sidebar.selectbox(
    "検索DB",
    options=list(available_dbs.keys()),
    index=0,
)
collection_name = available_dbs[selected_db_name]
db = SongVectorDB(collection_name=collection_name, distance_fn="cosine")

# 検索結果の最大表示数
max_results = st.sidebar.number_input(
    "最大検索結果数",
    min_value=10,
    max_value=200,
    value=50,
    step=10,
)


# メインコンテンツ
st.subheader("🔍 楽曲検索")

col1, col2, col3 = st.columns([3, 1, 1])
with col1:
    keyword = st.text_input(
        "検索キーワード（曲名、ID、source_dir、空欄で全件）",
        placeholder="例: ray または Yoasobi または gakumas_mv または youtube",
        label_visibility="collapsed",
    )
with col2:
    search_button = st.button("🔍 検索", type="primary", use_container_width=True)
with col3:
    recommend_button = st.button(
        "✨ おすすめ曲", type="secondary", use_container_width=True
    )

# 初回表示時にデフォルトでおすすめ曲を表示
if st.session_state.matches is None and st.session_state.last_keyword is None:
    with st.spinner("おすすめ曲を取得中..."):
        st.session_state.matches = get_random_songs(db, limit=max_results)
        st.session_state.last_keyword = "__recommend__"

# 検索実行
if search_button or recommend_button or "last_keyword" in st.session_state:
    # おすすめボタンが押された場合は、ランダムに50曲を表示
    if recommend_button:
        st.session_state.last_keyword = "__recommend__"
        with st.spinner("おすすめ曲を取得中..."):
            st.session_state.matches = get_random_songs(db, limit=max_results)
    # 検索ボタンが押された、またはキーワードが変更された場合
    elif search_button or (
        "last_keyword" not in st.session_state
        or (
            st.session_state.last_keyword != keyword
            and st.session_state.last_keyword != "__recommend__"
        )
    ):
        # キーワードが空でも検索可能にする
        current_keyword = keyword if keyword else ""
        st.session_state.last_keyword = current_keyword
        st.session_state.matches = find_song_by_keyword_with_metadata(
            db, current_keyword, limit=100000
        )

    matches = st.session_state.matches

    # 表示タイトルを変更
    if st.session_state.last_keyword == "__recommend__":
        pass

    if matches:
        st.success(f"✅ {len(matches)}件見つかりました")

        # st.info(
        #     "💡 **使い方:** 下の表で曲の行をクリックして、類似曲検索やプレイリスト作成に使用する曲を選択してください。"
        # )

        # データフレームとして表示
        df_data = []
        for idx, (song_id, metadata) in enumerate(matches, 1):
            df_data.append(
                {
                    "No.": idx,
                    "ファイル名": song_id,
                    "アーティスト": metadata.get("artist_name", "") if metadata else "",
                    "BPM": metadata.get("bpm", "") if metadata else "",
                    "registered_at": (
                        metadata.get("registered_at", "") if metadata else ""
                    ),
                }
            )

        df = pd.DataFrame(df_data)

        # dataframeで行選択可能なテーブルを表示
        event = st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            selection_mode="single-row",
            on_select="rerun",
            key="search_results_table",
        )

        # 選択された曲を更新
        selected_song_id = None
        if event.selection and event.selection.rows:
            selected_idx = event.selection.rows[0]
            if 0 <= selected_idx < len(matches):
                selected_song_id, _ = matches[selected_idx]

        # セッション状態を更新
        st.session_state.selected_song_id = selected_song_id
        st.session_state.selected_songs = [selected_song_id] if selected_song_id else []

        # 選択された曲を目立つように表示
        if selected_song_id:
            st.success(f"✨ **選択中の曲:** {selected_song_id}")
        else:
            st.info("💡 曲が選択されていません")

        # 詳細表示用の楽曲選択
        st.divider()
        st.subheader("🎯 類似曲検索（各DBから）")

        # 選択された曲がある場合はその曲を使用、なければ最初の曲
        if st.session_state.selected_song_id:
            selected_song = st.session_state.selected_song_id
            st.info(f"💡 選択された曲「{selected_song}」に類似している曲を検索します")
        else:
            selected_song = matches[0][0]
            st.warning("💡 曲が選択されていません。検索結果の最初の曲を使用します")

        # 類似曲検索のパラメータ
        n_results = st.number_input(
            "各DBからの検索数",
            min_value=5,
            max_value=50,
            value=10,
            step=5,
        )

        if st.button("🔍 類似曲を検索", type="secondary"):
            with st.spinner("類似曲を検索中..."):
                # 3つのDBをそれぞれ初期化（正しいパスと名前の対応）
                db_full = SongVectorDB(
                    collection_name="songs_full", distance_fn="cosine"
                )
                db_balance = SongVectorDB(
                    collection_name="songs_balanced", distance_fn="cosine"
                )
                db_minimal = SongVectorDB(
                    collection_name="songs_minimal", distance_fn="cosine"
                )

                dbs = [
                    ("Full", db_full),
                    ("Balance", db_balance),
                    ("Minimal", db_minimal),
                ]

                # 各DBから類似曲を検索
                all_results = {}
                for db_name, db_instance in dbs:
                    song_data = db_instance.get_song(
                        selected_song, include_embedding=True
                    )
                    if song_data and song_data.get("embedding") is not None:
                        # 検索除外フラグがTrueの曲を除外
                        # メタデータに excluded_from_search がない場合は False として扱う
                        similar = db_instance.search_similar(
                            query_embedding=song_data["embedding"],
                            n_results=n_results + 10,  # 除外分を考慮して多めに取得
                            where={"excluded_from_search": {"$ne": True}},
                        )
                        # 自分自身を除外してIDと距離を抽出
                        filtered_ids = []
                        filtered_distances = []
                        for song_id, distance in zip(
                            similar["ids"][0],
                            similar["distances"][0],
                        ):
                            if song_id != selected_song:
                                filtered_ids.append(song_id)
                                filtered_distances.append(distance)

                        # 上位n_results件のみ取得
                        filtered_ids = filtered_ids[:n_results]
                        filtered_distances = filtered_distances[:n_results]

                        # MySQLからメタデータを一括取得
                        metadata_dict = song_metadata_db.get_songs_as_dict(filtered_ids)

                        # (song_id, distance, metadata) のタプルリストを作成
                        filtered = [
                            (song_id, distance, metadata_dict.get(song_id, {}))
                            for song_id, distance in zip(
                                filtered_ids, filtered_distances
                            )
                        ]
                        all_results[db_name] = filtered
                    else:
                        all_results[db_name] = []

            # 各DBの結果を表示
            tabs = st.tabs(["📊 Full", "📊 Balance", "📊 Minimal"])

            for idx, (db_name, results) in enumerate(all_results.items()):
                with tabs[idx]:
                    if results:
                        result_data = []
                        for rank, (song_id, distance, metadata) in enumerate(
                            results, 1
                        ):
                            result_data.append(
                                {
                                    "Rank": rank,
                                    "ファイル名": song_id,
                                    "距離": f"{distance:.6f}",
                                    "BPM": (
                                        metadata.get("bpm", "") if metadata else ""
                                    ),
                                    "registered_at": (
                                        metadata.get("registered_at", "")
                                        if metadata
                                        else ""
                                    ),
                                }
                            )

                        result_df = pd.DataFrame(result_data)
                        # 距離列のカラム名を指定
                        if "距離" in result_df.columns:
                            styled_result_df = result_df.style.map(
                                lambda val: style_distance_value(val), subset=["距離"]
                            )
                        else:
                            styled_result_df = result_df.style
                        st.dataframe(
                            styled_result_df, use_container_width=True, hide_index=True
                        )
                    else:
                        st.warning(f"{db_name}: 類似曲が見つかりませんでした")

            # 距離の比較グラフ
            st.divider()
            st.subheader("📈 距離比較グラフ")

            # データを整形
            chart_data = {}
            for db_name, results in all_results.items():
                if results:
                    distances = [dist for _, dist, _ in results]
                    chart_data[db_name] = distances

            # 折れ線グラフで比較
            if chart_data:
                import pandas as pd

                df_chart = pd.DataFrame(chart_data)
                df_chart.index = df_chart.index + 1  # 1-indexed
                df_chart.index.name = "Rank"
                st.line_chart(df_chart, use_container_width=True)

                # 統計情報
                st.divider()
                st.subheader("📊 統計情報")

                col1, col2, col3 = st.columns(3)
                for col, (db_name, results) in zip(
                    [col1, col2, col3], all_results.items()
                ):
                    with col:
                        if results:
                            distances = [dist for _, dist, _ in results]
                            st.metric(
                                f"{db_name} 平均距離",
                                f"{sum(distances)/len(distances):.6f}",
                            )
                            st.caption(f"最小: {min(distances):.6f}")
                            st.caption(f"最大: {max(distances):.6f}")
            else:
                st.warning("類似曲が見つかりませんでした")

        # 連鎖検索セクション
        st.divider()
        st.subheader("🔗 曲調おすすめプレイリスト作成（連鎖検索）")
        st.info("💡 この曲から似た曲を連鎖的に検索してプレイリストを作成")

        # セッション状態の初期化
        if "source_dir_filter_selected" not in st.session_state:
            if "artist_filter_selected" in st.session_state:
                st.session_state.source_dir_filter_selected = (
                    st.session_state.artist_filter_selected
                )
            else:
                st.session_state.source_dir_filter_selected = []

        col1, col2 = st.columns(2)
        with col1:
            chain_search_count = st.number_input(
                "プレイリスト曲数",
                min_value=5,
                max_value=100,
                value=30,
                step=5,
                key="chain_search_count",
            )
        with col2:
            source_dir_names = get_source_dir_names()
            source_dir_filter_selected = st.multiselect(
                "登録元フィルタ（任意）",
                options=source_dir_names,
                help="source_dir（data/除去）から複数選択（検索で絞り込み）",
                key="source_dir_filter_selected",
            )

        # BPMフィルタオプション
        bpm_filter_mode = st.selectbox(
            "BPMフィルタ",
            options=[
                "BPM条件なし",
                "選択した曲以上のBPMのみで作成",
                "選択した曲以下のBPMのみで作成",
            ],
            index=0,
            help="選択した曲のBPMを基準にフィルタします",
            key="bpm_filter_mode",
        )

        if st.button("🔍 連鎖検索を実行", type="primary", key="chain_search_button"):
            with st.spinner("連鎖検索中..."):
                # 全てのDBsを初期化（検索には全てのDBを使用）
                db_full = SongVectorDB(
                    collection_name="songs_full", distance_fn="cosine"
                )
                db_balance = SongVectorDB(
                    collection_name="songs_balanced", distance_fn="cosine"
                )
                db_minimal = SongVectorDB(
                    collection_name="songs_minimal", distance_fn="cosine"
                )

                dbs = [db_full, db_balance, db_minimal]

                # BPMフィルタが有効な場合、選択曲のBPMを取得
                min_bpm = None
                max_bpm = None
                if bpm_filter_mode != "BPM条件なし":
                    selected_song_metadata = song_metadata_db.get_song(selected_song)
                    if selected_song_metadata and selected_song_metadata.get("bpm"):
                        selected_bpm = selected_song_metadata["bpm"]
                        if bpm_filter_mode == "選択した曲以上のBPMのみで作成":
                            min_bpm = selected_bpm
                            st.info(
                                f"🎵 選択した曲のBPM: {min_bpm:.1f} BPM以上でフィルタリング"
                            )
                        elif bpm_filter_mode == "選択した曲以下のBPMのみで作成":
                            max_bpm = selected_bpm
                            st.info(
                                f"🎵 選択した曲のBPM: {max_bpm:.1f} BPM以下でフィルタリング"
                            )
                    else:
                        st.warning(
                            "⚠️ 選択した曲のBPM情報がないため、BPMフィルタは無効です"
                        )

                # 既存の関数を使用
                chain_results = chain_search_to_list(
                    start_filename=selected_song,
                    dbs=dbs,
                    n_songs=chain_search_count,
                    artist_filter=(
                        source_dir_filter_selected
                        if source_dir_filter_selected
                        else None
                    ),
                    min_bpm=min_bpm,
                    max_bpm=max_bpm,
                )

                # セッション状態に保存
                st.session_state.chain_results = chain_results
                st.session_state.chain_selected_song = selected_song

        # 連鎖検索結果があれば表示（セッション状態から取得）
        if (
            st.session_state.chain_results is not None
            and st.session_state.chain_selected_song == selected_song
        ):
            chain_results = st.session_state.chain_results

            # 結果表示
            st.success(f"✅ {len(chain_results)}曲を検索しました")

            # データフレームとして表示（距離とメタデータも含む）
            chain_df_data = []
            for idx, (song_id, distance, metadata) in enumerate(chain_results, 1):
                chain_df_data.append(
                    {
                        "No.": idx,
                        "ファイル名": song_id,
                        "アーティスト": (
                            metadata.get("artist_name", "") if metadata else ""
                        ),
                        "距離": f"{distance:.6f}" if distance > 0 else "-",
                        "BPM": metadata.get("bpm", "") if metadata else "",
                    }
                )

            chain_df = pd.DataFrame(chain_df_data)

            # 距離列に色付けを適用して表示
            styled_chain_df = style_distance_column(chain_df)
            st.dataframe(styled_chain_df, use_container_width=True, hide_index=True)

            # 起点曲名称（videoIdと拡張子を除去）
            start_song_name = re.sub(
                r"\s*\[.*?\]\.(wav|mp3)$", "", st.session_state.chain_selected_song
            )

            # プレイリスト作成セクション
            st.divider()
            st.subheader("📝 YouTube Music プレイリスト作成")

            playlist_name = st.text_input(
                "プレイリスト名",
                value=f"曲調おすすめプレイリスト / {start_song_name}",
                key="playlist_name_input",
            )

            playlist_header_comment = st.text_area(
                "プレイリストコメント",
                placeholder="例: 今回は落ち着いた曲中心で作成",
                key="playlist_header_comment_input",
            )

            # プレイリスト作成ボタンのコールバック関数
            def start_playlist_creation():
                st.session_state.playlist_creating = True

            # プレイリスト作成中の場合
            if st.session_state.playlist_creating:
                # Streamlitのログインから取得したアクセストークンを使用
                access_token = st.user.get("access_token") if st.user else None
                
                if not access_token:
                    st.error("❌ YouTube API の権限が不足しています")
                    st.info(
                        """
                        プレイリスト作成には YouTube API の権限が必要です。
                        一度ログアウトして、再度ログインしてください。
                        
                        管理者の方へ: `.streamlit/secrets.toml` に YouTube API のスコープが設定されているか確認してください。
                        """
                    )
                    st.session_state.playlist_creating = False
                else:
                    with st.spinner(
                        "🎵 プレイリスト作成中...YouTube Musicで曲を検索しています"
                    ):
                        try:
                            ytmusic = YTMusicManager(access_token=access_token)

                            # 検索＋プレイリスト作成
                            success_count = 0
                            video_ids = []

                            progress_bar = st.progress(0)
                            status_text = st.empty()

                            for idx, (song_id, _, metadata) in enumerate(chain_results):
                                # まずメタデータからyoutube_idを取得
                                video_id = (
                                    metadata.get("youtube_id") if metadata else None
                                )

                                # メタデータにない場合はファイル名から抽出
                                if not video_id:
                                    video_id = extract_video_id_from_filename(song_id)

                                if video_id:
                                    # ビデオIDが取得できた場合は直接使用
                                    status_text.text(
                                        f"追加中 ({idx + 1}/{len(chain_results)}): {song_id} → ID: {video_id}"
                                    )
                                    video_ids.append(video_id)
                                    success_count += 1
                                else:
                                    # ビデオIDがない場合は検索クエリで検索
                                    source_dir = (
                                        metadata.get("source_dir", "")
                                        if metadata
                                        else ""
                                    )
                                    query = filename_to_query(song_id, source_dir)

                                    status_text.text(
                                        f"検索中 ({idx + 1}/{len(chain_results)}): {query}"
                                    )

                                    result = ytmusic.search_video_id(query)
                                    if result and result.get("videoId"):
                                        video_ids.append(result["videoId"])
                                        success_count += 1

                                progress_bar.progress((idx + 1) / len(chain_results))

                            progress_bar.empty()
                            status_text.empty()

                            if video_ids:
                                description_lines = [
                                    f"曲調おすすめプレイリスト検索結果 ({len(video_ids)}曲)"
                                ]
                                if (
                                    playlist_header_comment
                                    and playlist_header_comment.strip()
                                ):
                                    description_lines.extend(
                                        [
                                            "",
                                            "プレイリストコメント:",
                                            playlist_header_comment.strip(),
                                        ]
                                    )
                                playlist_description = "\n".join(description_lines)

                                playlist_id = ytmusic.create_playlist(
                                    playlist_name,
                                    playlist_description,
                                    privacy="PUBLIC",
                                    video_ids=video_ids,
                                )

                                if not playlist_id:
                                    st.error("❌ プレイリスト作成に失敗しました")
                                    st.session_state.playlist_creating = False
                                    st.stop()

                                st.success(
                                    f"✅ プレイリスト作成完了！ ({success_count}/{len(chain_results)}曲)"
                                )
                                playlist_url = f"https://music.youtube.com/playlist?list={playlist_id}"
                                st.markdown(
                                    f"🔗 **プレイリストURL:** [{playlist_url}]({playlist_url})"
                                )

                                creator_sub = getattr(st.user, "sub", "")
                                items = [
                                    {
                                        "seq": idx + 1,
                                        "song_id": song_id,
                                        "cosine_distance": float(distance),
                                    }
                                    for idx, (song_id, distance, _) in enumerate(
                                        chain_results
                                    )
                                ]
                                saved = playlist_db.save_playlist_result(
                                    playlist_id=playlist_id,
                                    playlist_name=playlist_name,
                                    playlist_url=playlist_url,
                                    creator_sub=creator_sub,
                                    items=items,
                                    header_comment=playlist_header_comment,
                                )
                                if not saved:
                                    st.warning("⚠️ プレイリストのDB保存に失敗しました")
                            else:
                                st.error("❌ 曲が見つかりませんでした")

                        except Exception as e:
                            st.error(f"❌ エラー: {str(e)}")
                        finally:
                            st.session_state.playlist_creating = False
            else:
                # プレイリスト作成ボタン
                st.button(
                    "🎵 YouTube Musicプレイリスト作成",
                    on_click=start_playlist_creation,
                    type="primary",
                    key="create_playlist_button",
                )

    else:
        st.warning("該当する楽曲が見つかりませんでした")

# 統計情報
st.divider()
st.subheader("📊 DB統計")

col1, col2 = st.columns(2)
with col1:
    total_songs = db.count()
    st.metric("総楽曲数", f"{total_songs:,} 曲")

with col2:
    st.metric("選択中のDB", selected_db_name)
