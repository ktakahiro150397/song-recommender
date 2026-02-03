"""
楽曲検索ページ

キーワードで楽曲を検索して類似曲を表示
"""

import streamlit as st
import pandas as pd
from pathlib import Path
import re

from core.db_manager import SongVectorDB

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

    # 距離列にのみスタイルを適用
    styled = df.style.applymap(color_distance, subset=["距離"])
    return styled


# ========== 設定 ==========
DB_PATHS = {
    "Full": "data/chroma_db_cos_full",
    "Balance": "data/chroma_db_cos_balance",
    "Minimal": "data/chroma_db_cos_minimal",
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

        # キーワードが空の場合は全件マッチ、それ以外はIDまたはsource_dirで検索
        if (
            not keyword
            or keyword_lower in song_id.lower()
            or keyword_lower in source_dir
        ):
            matches.append((song_id, metadata))
            if len(matches) >= limit:
                break

    return matches


# ========== メイン画面 ==========

st.set_page_config(
    page_title="個別曲検索",
    page_icon="🎵",
    layout="wide",
)

st.title("🎵 個別曲検索")
st.caption("キーワードで楽曲を検索して類似曲を表示")

# サイドバー設定
st.sidebar.header("検索設定")

# DB選択
available_dbs = {name: path for name, path in DB_PATHS.items() if Path(path).exists()}

if not available_dbs:
    st.error("利用可能なDBが見つかりません。")
    st.stop()

selected_db_name = st.sidebar.selectbox(
    "検索DB",
    options=list(available_dbs.keys()),
    index=0,
)
db_path = available_dbs[selected_db_name]
db = SongVectorDB(db_path=db_path, distance_fn="cosine")

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

col1, col2 = st.columns([3, 1])
with col1:
    keyword = st.text_input(
        "検索キーワード（IDまたはsource_dir、空欄で全件）",
        placeholder="例: Yoasobi または gakumas_mv",
        label_visibility="collapsed",
    )
with col2:
    search_button = st.button("🔍 検索", type="primary", use_container_width=True)

# 検索実行
if search_button or "last_keyword" in st.session_state:
    # キーワードが空でも検索可能にする
    current_keyword = keyword if keyword else ""

    if (
        "last_keyword" not in st.session_state
        or st.session_state.last_keyword != current_keyword
    ):
        st.session_state.last_keyword = current_keyword
        st.session_state.matches = find_song_by_keyword_with_metadata(
            db, current_keyword, limit=10000
        )

    matches = st.session_state.matches

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
                from config import DB_PATHS

                # 3つのDBをそれぞれ初期化
                db_full = SongVectorDB(db_path=DB_PATHS[0], distance_fn="cosine")
                db_balance = SongVectorDB(db_path=DB_PATHS[1], distance_fn="cosine")
                db_minimal = SongVectorDB(db_path=DB_PATHS[2], distance_fn="cosine")

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
                    if song_data and "embedding" in song_data:
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
                        styled_result_df = result_df.style.applymap(
                            lambda val: style_distance_value(val), subset=["距離"]
                        )
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
