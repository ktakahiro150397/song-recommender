"""
連鎖検索ページ

指定した楽曲から似た曲を連鎖的に検索してプレイリストを作成
"""

import streamlit as st
import pandas as pd
from pathlib import Path
import re

# 既存のスクリプトから必要な関数をインポート
from create_playlist_from_chain import (
    find_song_by_keyword,
    chain_search_to_list,
    filename_to_query,
    DB_PATHS,
    BROWSER_FILE,
    PRIVACY,
)
from core.db_manager import SongVectorDB
from core.ytmusic_manager import YTMusicManager


# ========== ユーティリティ関数 ==========

def get_distance_color_html(distance: float) -> str:
    """距離に応じてHTML色を返す（緑→黄→赤）"""
    if distance == 0:
        return "color: #808080"  # グレー（起点曲）
    
    ratio = min(distance / 0.01, 1.0)
    if ratio < 0.5:
        r = int(255 * (ratio * 2))
        g = 255
    else:
        r = 255
        g = int(255 * (1 - (ratio - 0.5) * 2))
    b = 0
    return f"color: #{r:02x}{g:02x}{b:02x}; font-weight: bold"


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


# ========== メイン画面 ==========

st.set_page_config(
    page_title="連鎖検索",
    page_icon="🔍",
    layout="wide",
)

st.title("🔍 連鎖検索")
st.caption("楽曲から似た曲を連鎖的に検索してプレイリストを作成")

# サイドバー設定
st.sidebar.header("検索設定")

# DB選択
available_dbs = {
    name: path
    for name, path in zip(
        ["Full", "Balance", "Minimal"],
        DB_PATHS
    )
    if Path(path).exists()
}

if not available_dbs:
    st.error("利用可能なDBが見つかりません。")
    st.stop()

search_db_name = st.sidebar.selectbox(
    "検索DB",
    options=list(available_dbs.keys()),
    index=0,
)
search_db_path = available_dbs[search_db_name]
search_db = SongVectorDB(db_path=search_db_path, distance_fn="cosine")

# 検索パラメータ
n_songs = st.sidebar.number_input(
    "検索曲数",
    min_value=5,
    max_value=100,
    value=30,
    step=5,
)

# メインコンテンツ
keyword = st.text_input(
    "🔍 楽曲を検索（アーティスト名または曲名）",
    placeholder="例: Yoasobi",
)

if keyword:
    # キーワード検索
    matches = find_song_by_keyword(search_db, keyword, limit=50)

    if matches:
        st.success(f"✅ {len(matches)}件見つかりました")

        # 1件のみの場合は自動選択、複数ある場合は選択肢を表示
        if len(matches) == 1:
            selected_song = matches[0]
            st.info(f"📍 起点楽曲: {selected_song}")
            auto_search = True
        else:
            selected_song = st.selectbox(
                "起点となる楽曲を選択",
                options=matches,
                format_func=lambda x: x,
            )
            auto_search = False

        if auto_search or st.button("🔍 連鎖検索を実行", type="primary"):
            with st.spinner("連鎖検索中..."):
                # DBsを初期化
                dbs = [
                    SongVectorDB(db_path=path, distance_fn="cosine") 
                    for path in DB_PATHS
                ]
                
                # 既存の関数を使用
                chain_results = chain_search_to_list(
                    start_filename=selected_song,
                    dbs=dbs,
                    n_songs=n_songs,
                )

            # 結果表示
            st.success(f"✅ {len(chain_results)}曲を検索しました")

            # データフレームとして表示（距離とメタデータも含む）
            df_data = []
            for idx, (song_id, distance, metadata) in enumerate(chain_results, 1):
                df_data.append({
                    "No.": idx,
                    "ファイル名": song_id,
                    "距離": f"{distance:.6f}" if distance > 0 else "-",
                    "source_dir": metadata.get("source_dir", "") if metadata else "",
                    "filename": metadata.get("filename", "") if metadata else "",
                })

            df = pd.DataFrame(df_data)
            
            # 距離列に色付けを適用して表示
            styled_df = style_distance_column(df)
            st.dataframe(styled_df, use_container_width=True, hide_index=True)

            # 起点曲名称（videoIdと拡張子を除去）
            start_song_name = re.sub(r"\s*\[.*?\]\.(wav|mp3)$", "", selected_song)

            # プレイリスト作成セクション
            st.divider()
            st.subheader("📝 プレイリスト作成")
            
            playlist_name = st.text_input(
                "プレイリスト名",
                value=f"曲調レコメンドプレイリスト / {start_song_name}",
            )

            if st.button("🎵 YouTube Musicプレイリスト作成"):
                if not Path(BROWSER_FILE).exists():
                    st.error(f"❌ {BROWSER_FILE} が見つかりません")
                else:
                    with st.spinner("プレイリスト作成中..."):
                        try:
                            ytmusic = YTMusicManager(browser_file=BROWSER_FILE)

                            # 検索＋プレイリスト作成
                            success_count = 0
                            video_ids = []

                            progress_bar = st.progress(0)
                            status_text = st.empty()

                            for idx, (song_id, _, metadata) in enumerate(chain_results):
                                # ファイル名とmetadataから検索クエリを生成
                                source_dir = metadata.get("source_dir", "") if metadata else ""
                                query = filename_to_query(song_id, source_dir)

                                status_text.text(f"検索中: {query}")

                                results = ytmusic.search_songs(query, limit=1)
                                if results:
                                    video_ids.append(results[0]["videoId"])
                                    success_count += 1

                                progress_bar.progress((idx + 1) / len(chain_results))

                            progress_bar.empty()
                            status_text.empty()

                            if video_ids:
                                playlist_id = ytmusic.create_playlist(
                                    playlist_name,
                                    f"連鎖検索結果 ({len(video_ids)}曲)",
                                    privacy=PRIVACY,
                                    video_ids=video_ids,
                                )

                                st.success(
                                    f"✅ プレイリスト作成完了！ ({success_count}/{len(chain_results)}曲)"
                                )
                                st.info(f"🔗 Playlist ID: {playlist_id}")
                            else:
                                st.error("❌ 曲が見つかりませんでした")

                        except Exception as e:
                            st.error(f"❌ エラー: {str(e)}")
    else:
        st.warning("該当する楽曲が見つかりませんでした")
