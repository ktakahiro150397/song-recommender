"""
楽曲検索ページ

キーワードで楽曲を検索して類似曲を表示
"""

import streamlit as st
import pandas as pd
from pathlib import Path
import re

from core.db_manager import SongVectorDB
from create_playlist_from_chain import (
    chain_search_to_list,
    filename_to_query,
    BROWSER_FILE,
)
from core.ytmusic_manager import YTMusicManager

# ========== ユーティリティ関数 ==========


def style_distance_value(val):
    """距離の値に色付けスタイルを返す（個別の値用）"""
    if val == "-":
        return "background-color: #f0f0f0; color: #666; font-weight: bold"
    try:
        distance = float(val)
        ratio = min(distance / 0.01, 1.0)
        if ratio < 0.5:
            r = int(255 * (ratio * 2))
            g = 255
        else:
            r = 255
            g = int(255 * (1 - (ratio - 0.5) * 2))
        b = 0
        # 背景色を薄く設定
        bg_r = int(r * 0.2 + 255 * 0.8)
        bg_g = int(g * 0.2 + 255 * 0.8)
        bg_b = int(b * 0.2 + 255 * 0.8)
        return f"background-color: #{bg_r:02x}{bg_g:02x}{bg_b:02x}; color: #{r:02x}{g:02x}{b:02x}; font-weight: bold"
    except:
        return ""


def style_distance_column(df: pd.DataFrame) -> pd.DataFrame:
    """距離列に色付けスタイルを適用（背景色付き）"""

    def color_distance(val):
        if val == "-":
            return "background-color: #f0f0f0; color: #666; font-weight: bold"
        try:
            distance = float(val)
            ratio = min(distance / 0.01, 1.0)
            if ratio < 0.5:
                r = int(255 * (ratio * 2))
                g = 255
            else:
                r = 255
                g = int(255 * (1 - (ratio - 0.5) * 2))
            b = 0
            # 背景色を薄く設定（RGB値を0.2の重みで白に近づける）
            bg_r = int(r * 0.2 + 255 * 0.8)
            bg_g = int(g * 0.2 + 255 * 0.8)
            bg_b = int(b * 0.2 + 255 * 0.8)
            return f"background-color: #{bg_r:02x}{bg_g:02x}{bg_b:02x}; color: #{r:02x}{g:02x}{b:02x}; font-weight: bold"
        except:
            return ""

    # 距離列が存在する場合のみスタイルを適用
    if "距離" in df.columns:
        styled = df.style.map(color_distance, subset=["距離"])
        return styled
    else:
        return df.style


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
        limit: 最大取得件数

    Returns:
        (song_id, metadata)のタプルのリスト
    """
    all_songs = db.list_all(limit=10000)
    matches = []

    keyword_lower = keyword.lower() if keyword else ""
    for idx, song_id in enumerate(all_songs["ids"]):
        metadata = all_songs["metadatas"][idx] if all_songs["metadatas"] else {}
        source_dir = metadata.get("source_dir", "").lower()
        song_title = metadata.get("song_title", "").lower()

        # キーワードが空の場合は全件マッチ、それ以外はID、source_dir、song_titleで検索
        if (
            not keyword
            or keyword_lower in song_id.lower()
            or keyword_lower in source_dir
            or keyword_lower in song_title
        ):
            matches.append((song_id, metadata))
            if len(matches) >= limit:
                break

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
    # 全曲取得（limit=10000で十分な数を取得）
    all_songs = db.list_all(limit=10000)
    
    # メタデータと曲IDをペアにしてリスト化
    song_list = []
    for idx, song_id in enumerate(all_songs["ids"]):
        metadata = all_songs["metadatas"][idx] if all_songs["metadatas"] else {}
        song_list.append((song_id, metadata))
    
    # registered_atでソート（新しい順）
    # registered_atが存在しない場合は古い扱いとする
    sorted_songs = sorted(
        song_list,
        key=lambda x: x[1].get("registered_at", "1900-01-01T00:00:00"),
        reverse=True  # 新しい順
    )
    
    return sorted_songs[:limit]


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
    recommend_button = st.button("✨ おすすめ曲", type="secondary", use_container_width=True)

# 検索実行
if search_button or recommend_button or "last_keyword" in st.session_state:
    # おすすめボタンが押された場合は、最近追加された曲を表示
    if recommend_button:
        st.session_state.last_keyword = "__recommend__"
        with st.spinner("おすすめ曲を取得中..."):
            st.session_state.matches = get_recently_added_songs(db, limit=max_results)
    # 検索ボタンが押された、またはキーワードが変更された場合
    elif search_button or (
        "last_keyword" not in st.session_state
        or (st.session_state.last_keyword != keyword and st.session_state.last_keyword != "__recommend__")
    ):
        # キーワードが空でも検索可能にする
        current_keyword = keyword if keyword else ""
        st.session_state.last_keyword = current_keyword
        st.session_state.matches = find_song_by_keyword_with_metadata(
            db, current_keyword, limit=10000
        )

    matches = st.session_state.matches
    
    # 表示タイトルを変更
    if st.session_state.last_keyword == "__recommend__":
        st.info("✨ 最近追加された楽曲を表示しています")

    if matches:
        st.success(f"✅ {len(matches)}件見つかりました")

        # データフレームとして表示
        df_data = []
        for idx, (song_id, metadata) in enumerate(matches, 1):
            df_data.append(
                {
                    "No.": idx,
                    "ファイル名": song_id,
                    "source_dir": metadata.get("source_dir", "") if metadata else "",
                    "registered_at": (
                        metadata.get("registered_at", "") if metadata else ""
                    ),
                }
            )

        df = pd.DataFrame(df_data)

        # データフレーム表示
        st.dataframe(df, use_container_width=True, hide_index=True)

        # 詳細表示用の楽曲選択
        st.divider()
        st.subheader("🎯 類似曲検索（各DBから）")
        st.info("💡 この曲に類似している曲を検索します")

        selected_song = st.selectbox(
            "楽曲を選択して類似曲を検索",
            options=[song_id for song_id, _ in matches],
            format_func=lambda x: x,
        )

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
                        similar = db_instance.search_similar(
                            query_embedding=song_data["embedding"],
                            n_results=n_results + 1,  # 自分自身も含まれるので+1
                        )
                        # 自分自身を除外
                        filtered = []
                        for song_id, distance, metadata in zip(
                            similar["ids"][0],
                            similar["distances"][0],
                            similar["metadatas"][0],
                        ):
                            if song_id != selected_song:
                                filtered.append((song_id, distance, metadata))
                        all_results[db_name] = filtered[:n_results]
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
                                    "source_dir": (
                                        metadata.get("source_dir", "")
                                        if metadata
                                        else ""
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
            st.write("")  # スペース調整

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

                # 既存の関数を使用
                chain_results = chain_search_to_list(
                    start_filename=selected_song,
                    dbs=dbs,
                    n_songs=chain_search_count,
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
                        "距離": f"{distance:.6f}" if distance > 0 else "-",
                        "source_dir": (
                            metadata.get("source_dir", "") if metadata else ""
                        ),
                        "filename": metadata.get("filename", "") if metadata else "",
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

            # プレイリスト作成ボタンのコールバック関数
            def start_playlist_creation():
                st.session_state.playlist_creating = True

            # プレイリスト作成中の場合
            if st.session_state.playlist_creating:
                if not Path(BROWSER_FILE).exists():
                    st.error(f"❌ {BROWSER_FILE} が見つかりません")
                    st.session_state.playlist_creating = False
                else:
                    with st.spinner(
                        "🎵 プレイリスト作成中...YouTube Musicで曲を検索しています"
                    ):
                        try:
                            ytmusic = YTMusicManager(browser_file=BROWSER_FILE)

                            # 検索＋プレイリスト作成
                            success_count = 0
                            video_ids = []

                            progress_bar = st.progress(0)
                            status_text = st.empty()

                            for idx, (song_id, _, metadata) in enumerate(chain_results):
                                # ファイル名とmetadataから検索クエリを生成
                                source_dir = (
                                    metadata.get("source_dir", "") if metadata else ""
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
                                playlist_id = ytmusic.create_playlist(
                                    playlist_name,
                                    f"曲調おすすめプレイリスト検索結果 ({len(video_ids)}曲)",
                                    privacy="PUBLIC",
                                    video_ids=video_ids,
                                )

                                st.success(
                                    f"✅ プレイリスト作成完了！ ({success_count}/{len(chain_results)}曲)"
                                )
                                playlist_url = f"https://music.youtube.com/playlist?list={playlist_id}"
                                st.markdown(
                                    f"🔗 **プレイリストURL:** [{playlist_url}]({playlist_url})"
                                )
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
