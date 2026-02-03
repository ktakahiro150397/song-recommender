"""
DBメンテナンス用Streamlitアプリ

使い方:
    streamlit run db_maintenance.py
"""

import streamlit as st
import pandas as pd
from pathlib import Path

from core.db_manager import SongVectorDB
from config import DB_CONFIGS

# ========== 設定 ==========
# 同期するDB（全て同じ内容を保持）
DB_PATHS = {
    "Full": "songs_full",
    "Balance": "songs_balanced",
    "Minimal": "songs_minimal",
}

# ========== ユーティリティ関数 ==========


def load_songs_as_dataframe(db: SongVectorDB, limit: int = 1000) -> pd.DataFrame:
    """DBから曲一覧を取得してDataFrameに変換"""
    result = db.list_all(limit=limit)

    if not result["ids"]:
        return pd.DataFrame()

    data = []
    for i, song_id in enumerate(result["ids"]):
        metadata = result["metadatas"][i] if result["metadatas"] else {}
        data.append(
            {
                "選択": False,  # チェックボックス用
                "ID": song_id,
                "source_dir": metadata.get("source_dir", ""),
                "filename": metadata.get("filename", ""),
            }
        )

    return pd.DataFrame(data)


def delete_songs(song_ids: list[str]) -> tuple[int, list[str]]:
    """複数の曲を全DBから削除"""
    success_count = 0
    errors = []

    for song_id in song_ids:
        try:
            # 全DBから削除（Full/Balance/Minimal）
            for collection_name in DB_PATHS.values():
                db = SongVectorDB(collection_name=collection_name, distance_fn="cosine")
                db.delete_song(song_id)
            success_count += 1
        except Exception as e:
            errors.append(f"{song_id}: {str(e)}")

    return success_count, errors


# ========== メイン画面 ==========


def main():
    st.set_page_config(
        page_title="DB Maintenance",
        page_icon="🗄️",
        layout="wide",
    )

    st.title("🗄️ DB メンテナンス")
    st.caption("Full/Balance/Minimal の3つのDBを同期管理")

    # サイドバー: DB選択
    st.sidebar.header("設定")

    # 利用可能なDBのみフィルタリング
    available_dbs = {
        name: path for name, path in DB_PATHS.items() if Path(path).exists()
    }

    if not available_dbs:
        st.error("利用可能なDBが見つかりません。")
        return

    selected_db_name = st.sidebar.selectbox(
        "表示するDB",
        options=list(available_dbs.keys()),
        index=0,
    )

    collection_name = available_dbs[selected_db_name]

    # DBを初期化
    try:
        db = SongVectorDB(collection_name=collection_name, distance_fn="cosine")
        total_count = db.count()
    except Exception as e:
        st.error(f"DB初期化エラー: {e}")
        return

    # サイドバー: 統計情報
    st.sidebar.header("DB情報")
    st.sidebar.metric("総登録曲数", f"{total_count:,}")
    st.sidebar.caption(f"表示中: {selected_db_name}")
    st.sidebar.caption("※ 削除時は全DBから削除")

    # 表示件数設定
    limit = st.sidebar.number_input(
        "表示件数",
        min_value=10,
        max_value=10000,
        value=total_count,  # 全件表示をデフォルトに
        step=100,
    )

    # 検索フィルター
    st.sidebar.header("検索・フィルター")
    search_query = st.sidebar.text_input(
        "IDで検索（部分一致）",
        placeholder="例: フェスタ",
    )

    source_dir_filter = st.sidebar.text_input(
        "Source Dirで検索",
        placeholder="例: gakumas_mv",
    )

    # データ読み込み
    with st.spinner("データ読み込み中..."):
        df = load_songs_as_dataframe(db, limit=int(limit))

    if df.empty:
        st.warning("データが見つかりません。")
        return

    # フィルタリング
    filtered_df = df.copy()

    if search_query:
        filtered_df = filtered_df[
            filtered_df["ID"].str.contains(search_query, case=False, na=False)
        ]

    if source_dir_filter:
        filtered_df = filtered_df[
            filtered_df["source_dir"].str.contains(
                source_dir_filter, case=False, na=False
            )
        ]

    st.info(
        f"表示中: {len(filtered_df):,} 件 / 全 {len(df):,} 件（DB内: {total_count:,} 件）"
    )

    # データエディター（チェックボックス付き）
    st.subheader("📋 曲一覧")

    # 全選択チェックボックス
    col1, col2 = st.columns([1, 5])
    with col1:
        select_all = st.checkbox("全て選択", key="select_all")

    # 全選択が有効な場合、全ての「選択」列をTrueに設定
    if select_all:
        filtered_df["選択"] = True

    edited_df = st.data_editor(
        filtered_df,
        column_config={
            "選択": st.column_config.CheckboxColumn(
                "選択",
                help="削除する曲を選択",
                default=False,
            ),
            "ID": st.column_config.TextColumn(
                "曲ID",
                width="medium",
            ),
            "source_dir": st.column_config.TextColumn(
                "Source Dir",
                width="small",
            ),
            "filename": st.column_config.TextColumn(
                "ファイル名",
                width="large",
            ),
        },
        hide_index=True,
        width="stretch",
        height=500,
    )

    # 削除処理
    st.subheader("🗑️ 削除")

    selected_songs = edited_df[edited_df["選択"] == True]["ID"].tolist()

    if selected_songs:
        st.warning(
            f"⚠️ {len(selected_songs)} 件選択中（Full/Balance/Minimal 全てから削除されます）"
        )

        col1, col2 = st.columns([1, 4])

        with col1:
            if st.button(
                "🗑️ 選択した曲を削除",
                type="primary",
            ):
                with st.spinner("3つのDBから削除中..."):
                    success_count, errors = delete_songs(selected_songs)

                if errors:
                    st.error(f"削除完了: {success_count} 件 / エラー: {len(errors)} 件")
                    with st.expander("エラー詳細"):
                        for err in errors:
                            st.text(err)
                else:
                    st.success(f"✅ {success_count} 件を削除しました")

                st.rerun()

        with col2:
            with st.expander("選択中の曲を確認"):
                for song in selected_songs:
                    st.text(f"• {song}")
    else:
        st.info("削除する曲をチェックで選択してください")

    # リフレッシュボタン
    if st.sidebar.button("🔄 再読み込み"):
        st.rerun()


if __name__ == "__main__":
    main()
