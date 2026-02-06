"""
DBメンテナンスページ

データベースの管理と曲の削除
"""

import streamlit as st
import pandas as pd
from pathlib import Path

from core.db_manager import SongVectorDB
from core import song_metadata_db
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
    # MySQLから曲一覧を取得（セッション内で辞書化済み）
    songs = song_metadata_db.list_all(limit=limit, exclude_from_search=False)

    if not songs:
        return pd.DataFrame()

    data = []
    for song_id, metadata in songs:
        data.append(
            {
                "選択": False,  # チェックボックス用
                "ID": song_id,
                "source_dir": metadata["source_dir"],
                "filename": metadata["filename"],
                "検索除外": metadata["excluded_from_search"],
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

            # MySQLからも削除
            song_metadata_db.delete_song(song_id)
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
                db.update_excluded_from_search(song_id, exclude)

            # MySQLでも更新
            song_metadata_db.update_excluded_from_search(song_id, exclude)
            success_count += 1
        except Exception as e:
            errors.append(f"{song_id}: {str(e)}")

    return success_count, errors


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
    max_value=max(10000, total_count),  # DBの総件数に応じて上限を調整
    value=100,  # デフォルトを100件に設定
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

# セッション状態で曲一覧のチェック状態を管理
if "songs_selection" not in st.session_state:
    st.session_state.songs_selection = {}

if "exclude_flags_session" not in st.session_state:
    st.session_state.exclude_flags_session = {}

# フィルター後の曲IDリストを生成
filtered_song_ids = filtered_df["ID"].tolist()

# セッション状態を初期化（フィルター変更時にリセット）
for song_id in filtered_song_ids:
    if song_id not in st.session_state.songs_selection:
        st.session_state.songs_selection[song_id] = False
    if song_id not in st.session_state.exclude_flags_session:
        st.session_state.exclude_flags_session[song_id] = filtered_df[
            filtered_df["ID"] == song_id
        ]["検索除外"].iloc[0]

# データエディター（チェックボックス付き）
st.subheader("📋 曲一覧")

# 全選択チェックボックス
col1, col2 = st.columns([1, 5])
with col1:
    select_all = st.checkbox("全て選択", key="select_all", value=False)

# 全選択が有効な場合、全ての「選択」列をTrueに設定
if select_all:
    for song_id in filtered_song_ids:
        st.session_state.songs_selection[song_id] = True

# 表示用DataFrameを作成（セッション状態のチェック状態を反映）
display_df = filtered_df.copy()
display_df["選択"] = display_df["ID"].map(
    lambda x: st.session_state.songs_selection.get(x, False)
)
display_df["検索除外"] = display_df["ID"].map(
    lambda x: st.session_state.exclude_flags_session.get(x, False)
)

# ============== フォーム内でチェックボックスを管理（再実行トリガーなし） ==============
with st.form("songs_table_form", border=False):
    cols = st.columns([0.5, 2, 2, 3, 1])
    with cols[0]:
        st.write("**選択**")
    with cols[1]:
        st.write("**曲ID**")
    with cols[2]:
        st.write("**Source Dir**")
    with cols[3]:
        st.write("**ファイル名**")
    with cols[4]:
        st.write("**検索除外**")

    # 曲ごとにチェックボックスを動的に作成
    for idx, row in display_df.iterrows():
        song_id = row["ID"]

        cols = st.columns([0.5, 2, 2, 3, 1])

        with cols[0]:
            # 選択チェックボックス
            st.session_state.songs_selection[song_id] = st.checkbox(
                "選択",
                value=st.session_state.songs_selection.get(song_id, False),
                key=f"select_{idx}_{song_id}",
                label_visibility="collapsed",
            )

        with cols[1]:
            st.text(song_id)

        with cols[2]:
            st.text(row["source_dir"])

        with cols[3]:
            st.text(row["filename"])

        with cols[4]:
            # 検索除外チェックボックス
            st.session_state.exclude_flags_session[song_id] = st.checkbox(
                "除外",
                value=st.session_state.exclude_flags_session.get(song_id, False),
                key=f"exclude_{idx}_{song_id}",
                label_visibility="collapsed",
            )

    # フォーム送信ボタン（実際には何もしない、セッション状態更新のため）
    st.form_submit_button("✅ 選択状態を保存", use_container_width=False)
    st.caption("💡 このボタンを押してから下記の削除・検索除外ボタンを押してください")

# 編集後のデータフレームを構築（後続処理用）
edited_df = display_df.copy()
edited_df["選択"] = edited_df["ID"].map(
    lambda x: st.session_state.songs_selection.get(x, False)
)
edited_df["検索除外"] = edited_df["ID"].map(
    lambda x: st.session_state.exclude_flags_session.get(x, False)
)

# 削除処理
st.subheader("🗑️ 削除")

selected_songs = [
    song_id
    for song_id, selected in st.session_state.songs_selection.items()
    if selected
]

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
                # セッション状態をリセット
                for song_id in selected_songs:
                    if song_id in st.session_state.songs_selection:
                        del st.session_state.songs_selection[song_id]
                    if song_id in st.session_state.exclude_flags_session:
                        del st.session_state.exclude_flags_session[song_id]

            st.rerun()

    with col2:
        with st.expander("選択中の曲を確認"):
            for song in selected_songs:
                st.text(f"• {song}")
else:
    st.info("削除する曲をチェックで選択してください")

# 検索除外フラグの管理
st.subheader("🏷️ 検索除外フラグ管理")

# セッション状態から変更されたフラグを検出
exclude_changes = []
for song_id in filtered_song_ids:
    current_exclude = st.session_state.exclude_flags_session.get(song_id, False)
    original_exclude = filtered_df[filtered_df["ID"] == song_id]["検索除外"].iloc[0]

    if current_exclude != original_exclude:
        exclude_changes.append((song_id, current_exclude))

if exclude_changes:
    st.info(f"💡 {len(exclude_changes)} 件の検索除外状態が変更されました")

    col1, col2 = st.columns(2)

    with col1:
        if st.button(
            "💾 変更を保存",
            type="primary",
            use_container_width=True,
            key="save_exclude_changes",
        ):
            with st.spinner("検索除外フラグを更新中..."):
                success_count = 0
                errors = []

                for song_id, should_exclude in exclude_changes:
                    try:
                        # 全DBで更新（Full/Balance/Minimal）
                        for collection_name in DB_PATHS.values():
                            db_update = SongVectorDB(
                                collection_name=collection_name, distance_fn="cosine"
                            )
                            # 既存のメタデータを取得
                            song_data = db_update.get_song(
                                song_id, include_embedding=False
                            )
                            if song_data and song_data.get("metadata"):
                                metadata = song_data["metadata"]
                                metadata["excluded_from_search"] = should_exclude
                                db_update.update_metadata(song_id, metadata)
                        success_count += 1
                    except Exception as e:
                        errors.append(f"{song_id}: {str(e)}")

                if errors:
                    st.error(f"更新完了: {success_count} 件 / エラー: {len(errors)} 件")
                    with st.expander("エラー詳細"):
                        for err in errors:
                            st.text(err)
                else:
                    st.success(f"✅ {success_count} 件の検索除外状態を更新しました")
                    # セッション状態を更新
                    for song_id, should_exclude in exclude_changes:
                        filtered_df.loc[filtered_df["ID"] == song_id, "検索除外"] = (
                            should_exclude
                        )

                st.rerun()

    with col2:
        if st.button(
            "✖️ 変更をキャンセル", use_container_width=True, key="cancel_exclude_changes"
        ):
            # セッション状態をリセット
            for song_id, original_exclude in [
                (sid, filtered_df[filtered_df["ID"] == sid]["検索除外"].iloc[0])
                for sid in [sc[0] for sc in exclude_changes]
            ]:
                st.session_state.exclude_flags_session[song_id] = original_exclude
            st.rerun()

    with st.expander("変更内容を確認"):
        for song_id, should_exclude in exclude_changes:
            status = "除外に設定" if should_exclude else "除外を解除"
            st.text(f"• {song_id}: {status}")

# 一括処理（選択した曲）
selected_songs = [
    song_id
    for song_id, selected in st.session_state.songs_selection.items()
    if selected
]

if selected_songs:
    st.info(f"💡 削除用に {len(selected_songs)} 件選択中")

    col1, col2 = st.columns(2)

    with col1:
        if st.button(
            "✅ 選択中を検索除外にする", type="secondary", use_container_width=True
        ):
            with st.spinner("検索除外フラグを設定中..."):
                success_count, errors = toggle_excluded_flag(selected_songs, True)

            if errors:
                st.error(f"更新完了: {success_count} 件 / エラー: {len(errors)} 件")
                with st.expander("エラー詳細"):
                    for err in errors:
                        st.text(err)
            else:
                st.success(f"✅ {success_count} 件を検索除外にしました")
                # セッション状態を更新
                for song_id in selected_songs:
                    st.session_state.exclude_flags[song_id] = True

            st.rerun()

    with col2:
        if st.button(
            "🔓 選択中の検索除外を解除", type="secondary", use_container_width=True
        ):
            with st.spinner("検索除外フラグを解除中..."):
                success_count, errors = toggle_excluded_flag(selected_songs, False)

            if errors:
                st.error(f"更新完了: {success_count} 件 / エラー: {len(errors)} 件")
                with st.expander("エラー詳細"):
                    for err in errors:
                        st.text(err)
            else:
                st.success(f"✅ {success_count} 件の検索除外を解除しました")
                # セッション状態を更新
                for song_id in selected_songs:
                    st.session_state.exclude_flags[song_id] = False

            st.rerun()
else:
    st.caption("💡 左の「選択」列をチェックすると一括変更オプションが表示されます")

# リフレッシュボタン
if st.sidebar.button("🔄 再読み込み"):
    st.rerun()
