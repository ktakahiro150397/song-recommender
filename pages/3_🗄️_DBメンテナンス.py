"""
DBメンテナンスページ

データベースの管理と曲の削除
"""

import streamlit as st
import pandas as pd
from pathlib import Path

from core.db_manager import SongVectorDB
from config import DB_CONFIGS

# ========== 設定 ==========
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
                "検索除外": metadata.get("excluded_from_search", False),
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


def toggle_excluded_flag(song_ids: list[str], exclude: bool) -> tuple[int, list[str]]:
    """複数の曲の検索除外フラグを全DBで更新"""
    success_count = 0
    errors = []

    for song_id in song_ids:
        try:
            # 全DBで更新（Full/Balance/Minimal）
            for collection_name in DB_PATHS.values():
                db = SongVectorDB(collection_name=collection_name, distance_fn="cosine")
                # 既存のメタデータを取得
                song_data = db.get_song(song_id, include_embedding=False)
                if song_data and song_data.get("metadata"):
                    metadata = song_data["metadata"]
                    metadata["excluded_from_search"] = exclude
                    db.update_metadata(song_id, metadata)
            success_count += 1
        except Exception as e:
            errors.append(f"{song_id}: {str(e)}")

    return success_count, errors


def find_potential_duplicates(db: SongVectorDB, limit: int = 10000) -> list[tuple[str, list[str]]]:
    """
    曲名の類似性から重複の可能性がある曲をグループ化
    
    Returns:
        [(基準曲ID, [類似曲IDリスト]), ...] のリスト
    """
    import difflib
    
    all_songs = db.list_all(limit=limit)
    if not all_songs["ids"]:
        return []
    
    song_ids = all_songs["ids"]
    duplicates = []
    processed = set()
    
    for i, song_id in enumerate(song_ids):
        if song_id in processed:
            continue
            
        # このIDと類似している他のIDを探す
        similar_songs = []
        base_name = song_id.lower()
        
        for j, other_id in enumerate(song_ids):
            if i == j or other_id in processed:
                continue
                
            other_name = other_id.lower()
            # 類似度を計算（0.7以上で類似とみなす）
            similarity = difflib.SequenceMatcher(None, base_name, other_name).ratio()
            
            if similarity > 0.7:
                similar_songs.append(other_id)
                processed.add(other_id)
        
        if similar_songs:
            duplicates.append((song_id, similar_songs))
            processed.add(song_id)
    
    return duplicates


# ========== メイン画面 ==========

st.set_page_config(
    page_title="DBメンテナンス",
    page_icon="🗄️",
    layout="wide",
)

st.title("🗄️ DBメンテナンス")
st.caption("Full/Balance/Minimal の3つのDBを同期管理")

# サイドバー: DB選択
st.sidebar.header("設定")

# リモートChromaDBサーバーを使用するため、すべてのDBを利用可能として扱う
available_dbs = DB_PATHS

if not available_dbs:
    st.error("利用可能なDBが見つかりません。")
    st.stop()

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
    st.stop()

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

# 検索除外フィルター
show_excluded = st.sidebar.checkbox(
    "検索除外曲を表示",
    value=True,
    help="検索除外フラグが立っている曲も表示します",
)

# データ読み込み
if search_query or source_dir_filter:
    # フィルタがある場合は全データを取得
    with st.spinner("全データから検索中..."):
        df = load_songs_as_dataframe(db, limit=total_count)
else:
    # フィルタがない場合は表示件数制限
    with st.spinner("データ読み込み中..."):
        df = load_songs_as_dataframe(db, limit=int(limit))

if df.empty:
    st.warning("データが見つかりません。")
    st.stop()

# フィルタリング
filtered_df = df.copy()

if search_query:
    filtered_df = filtered_df[
        filtered_df["ID"].str.contains(search_query, case=False, na=False)
    ]

if source_dir_filter:
    filtered_df = filtered_df[
        filtered_df["source_dir"].str.contains(source_dir_filter, case=False, na=False)
    ]

if not show_excluded:
    filtered_df = filtered_df[filtered_df["検索除外"] == False]

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
        "検索除外": st.column_config.CheckboxColumn(
            "検索除外",
            help="このフラグがONの曲は検索結果から除外されます",
            default=False,
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

# 検索除外フラグの管理
st.subheader("🏷️ 検索除外フラグ管理")

if selected_songs:
    st.info(f"💡 {len(selected_songs)} 件選択中")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("✅ 検索除外にする", type="secondary", use_container_width=True):
            with st.spinner("検索除外フラグを設定中..."):
                success_count, errors = toggle_excluded_flag(selected_songs, True)
            
            if errors:
                st.error(f"更新完了: {success_count} 件 / エラー: {len(errors)} 件")
                with st.expander("エラー詳細"):
                    for err in errors:
                        st.text(err)
            else:
                st.success(f"✅ {success_count} 件を検索除外にしました")
            
            st.rerun()
    
    with col2:
        if st.button("🔓 検索除外を解除", type="secondary", use_container_width=True):
            with st.spinner("検索除外フラグを解除中..."):
                success_count, errors = toggle_excluded_flag(selected_songs, False)
            
            if errors:
                st.error(f"更新完了: {success_count} 件 / エラー: {len(errors)} 件")
                with st.expander("エラー詳細"):
                    for err in errors:
                        st.text(err)
            else:
                st.success(f"✅ {success_count} 件の検索除外を解除しました")
            
            st.rerun()
else:
    st.info("検索除外フラグを変更する曲をチェックで選択してください")

# 重複検出セクション
st.divider()
st.subheader("🔍 重複曲検出")

st.info("💡 曲名の類似性から重複の可能性がある曲をグループ表示します")

if st.button("🔍 重複検出を実行", type="secondary"):
    with st.spinner("重複を検出中..."):
        duplicates = find_potential_duplicates(db, limit=total_count)
    
    if duplicates:
        st.success(f"✅ {len(duplicates)} グループの重複候補を検出しました")
        
        for idx, (base_song, similar_songs) in enumerate(duplicates, 1):
            with st.expander(f"グループ {idx}: {base_song} + {len(similar_songs)} 件"):
                st.write(f"**基準曲:** {base_song}")
                st.write(f"**類似曲 ({len(similar_songs)} 件):**")
                for similar in similar_songs:
                    st.text(f"  • {similar}")
                
                st.caption("💡 重複と思われる曲を上の表で選択して、削除または検索除外してください")
    else:
        st.info("重複候補は見つかりませんでした")

# リフレッシュボタン
if st.sidebar.button("🔄 再読み込み"):
    st.rerun()
