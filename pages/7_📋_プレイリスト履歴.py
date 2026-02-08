"""
作成済みプレイリスト履歴ページ
"""

import streamlit as st
import pandas as pd
import html
from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit.components.v1 as components

from core import playlist_db
from core.ui_styles import style_distance_column
from core.user_db import get_emails_by_subs
from core import song_metadata_db
from core.user_db import get_display_names_by_subs


st.set_page_config(
    page_title="プレイリスト履歴",
    page_icon="📋",
    layout="wide",
)

st.title("📋 作成済みプレイリスト履歴")
st.markdown("---")

if "delete_confirm_id" not in st.session_state:
    st.session_state.delete_confirm_id = ""

delete_notice = st.session_state.pop("delete_notice", "")
if delete_notice:
    st.toast(delete_notice)


user_sub = getattr(st.user, "sub", "")
user_email = getattr(st.user, "email", "")

# フィルター
st.markdown("### 🔍 フィルター")
col_filter, col_keyword = st.columns([1, 2])
with col_filter:
    only_mine = st.checkbox("自分のプレイリストのみ", value=True)
with col_keyword:
    keyword = st.text_input(
        "プレイリスト名またはIDで検索",
        placeholder="キーワードを入力...",
        label_visibility="collapsed",
    )

query_timezone = st.query_params.get("tz", "")
if not query_timezone:
    components.html(
        """
                <script>
                const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
                const params = new URLSearchParams(window.location.search);
                if (!params.get('tz')) {
                    params.set('tz', tz);
                    window.location.search = params.toString();
                }
                </script>
                """,
        height=0,
    )

timezone = query_timezone or "Asia/Tokyo"

creator_sub_filter = user_sub if only_mine and user_sub else None
headers = playlist_db.list_playlist_headers(
    creator_sub=creator_sub_filter,
    keyword=keyword if keyword else None,
    limit=500,
)

if only_mine and not user_sub:
    st.warning("ログインユーザーSubが取得できないため、全件表示になります")

if not headers and only_mine:
    st.info("自分のプレイリストが見つからなかったため、全件表示に切り替えます")
    headers = playlist_db.list_playlist_headers(
        creator_sub=None,
        keyword=keyword if keyword else None,
        limit=500,
    )

if not headers:
    st.info("📭 まだプレイリスト履歴がありません")
    st.stop()


def format_created_at(value: str, tz_name: str) -> str:
    try:
        normalized_value = value.replace("Z", "+00:00")
        created_dt = datetime.fromisoformat(normalized_value)
        if created_dt.tzinfo is None:
            created_dt = created_dt.replace(tzinfo=ZoneInfo("UTC"))
        try:
            display_tz = ZoneInfo(tz_name)
        except Exception:
            display_tz = ZoneInfo("Asia/Tokyo")
        created_dt = created_dt.astimezone(display_tz)
        return created_dt.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return value[:19].replace("T", " ")


# ヘッダー一覧
st.markdown("### 📋 プレイリスト一覧")
creator_subs = [header["creator_sub"] for header in headers]
display_name_map = get_display_names_by_subs(creator_subs)

for idx, header in enumerate(headers, 1):
    creator_sub = header.get("creator_sub") or ""
    playlist_name = header["playlist_name"]
    playlist_id = header["playlist_id"]
    playlist_url = header["playlist_url"]
    creator_display_name = display_name_map.get(creator_sub) or "-"
    created_at_display = format_created_at(header["created_at"], timezone)

    items = playlist_db.get_playlist_items(playlist_id)
    first_song_id = items[0]["song_id"] if items else "-"

    header_comment = header.get("header_comment") or ""

    header_df = pd.DataFrame(
        {
            "項目": [
                "プレイリスト名",
                "最初の曲",
                "プレイリストID",
                "URL",
                "作成者",
                "作成日時",
            ],
            "内容": [
                playlist_name,
                first_song_id,
                playlist_id,
                playlist_url,
                creator_display_name,
                created_at_display,
            ],
        }
    )
    st.dataframe(header_df, use_container_width=True, hide_index=True)

    # 削除ボタン（作成者のみ表示）
    if user_sub and creator_sub == user_sub:
        delete_button_key = f"delete_playlist_{playlist_id}"
        if st.session_state.delete_confirm_id == playlist_id:
            st.warning("本当に削除しますか？この操作は取り消せません。")
            col_confirm, col_cancel = st.columns(2)
            with col_confirm:
                if st.button(
                    "削除を確定", key=f"confirm_{playlist_id}", type="primary"
                ):
                    if playlist_db.delete_playlist(playlist_id, user_sub):
                        st.session_state["delete_notice"] = (
                            f"プレイリスト「{playlist_name}」を削除しました"
                        )
                        st.session_state.delete_confirm_id = ""
                        st.rerun()
                    else:
                        st.error("プレイリストの削除に失敗しました")
            with col_cancel:
                if st.button("キャンセル", key=f"cancel_{playlist_id}"):
                    st.session_state.delete_confirm_id = ""
                    st.rerun()
        else:
            if st.button(
                "🗑️ このプレイリストを削除",
                key=delete_button_key,
                type="secondary",
                help="このプレイリストを完全に削除します",
            ):
                st.session_state.delete_confirm_id = playlist_id
                st.rerun()

    if header_comment:
        header_comment_html = html.escape(header_comment).replace("\n", "<br>")
        st.markdown(
            f"**プレイリストコメント**<br>{header_comment_html}",
            unsafe_allow_html=True,
        )

    # Fetch all comments for count and pagination
    all_comments = playlist_db.list_playlist_comments(playlist_id, limit=500)
    comment_count = len(all_comments)

    with st.expander(f"コメント ({comment_count}件)", expanded=False):
        # Initialize session state for comments pagination per playlist
        comments_per_page = 20
        comments_state_key = f"comments_to_show_{playlist_id}"

        # Initialize or reset session state for this playlist
        if comments_state_key not in st.session_state:
            st.session_state[comments_state_key] = comments_per_page

        # Calculate display range
        end_idx = min(st.session_state[comments_state_key], len(all_comments))
        displayed_comments = all_comments[0:end_idx]

        comment_user_subs = [comment["user_sub"] for comment in displayed_comments]
        comment_display_name_map = get_display_names_by_subs(comment_user_subs)

        if displayed_comments:
            for comment in displayed_comments:
                comment_display_name = comment_display_name_map.get(
                    comment["user_sub"], "-"
                )
                comment_time = format_created_at(comment["created_at"], timezone)
                with st.chat_message("user"):
                    st.markdown(f"**{comment_display_name}** · {comment_time}")
                    st.write(comment["comment"])

            # Load more button if there are more comments
            if end_idx < len(all_comments):
                remaining = len(all_comments) - end_idx
                cols = st.columns([1, 2, 1])
                with cols[1]:
                    if st.button(
                        f"📖 さらに{min(comments_per_page, remaining)}件読み込む",
                        type="primary",
                        use_container_width=True,
                        key=f"load_more_comments_{playlist_id}",
                    ):
                        st.session_state[comments_state_key] += comments_per_page
                        st.rerun()
                is_creator = comment["user_sub"] == creator_sub
                is_own_comment = comment["user_sub"] == user_sub
                is_deleted = comment.get("is_deleted", False)

                # 作成者のコメントは異なる背景色を使用
                background_color = "#f5fffa" if is_creator else "#fafafa"

                # コメント内容を決定
                if is_deleted:
                    comment_text = "(削除されました)"
                    comment_display = f'<div style="font-style: italic; color: #999;">{comment_text}</div>'
                else:
                    comment_display = html.escape(comment["comment"]).replace(
                        "\n", "<br>"
                    )

                # カード形式でコメントを表示
                st.markdown(
                    f"""
                    <div style="
                        background-color: {background_color};
                        padding: 12px;
                        border-radius: 8px;
                        margin-bottom: 10px;
                        border-left: 4px solid {'#4CAF50' if is_creator else '#2196F3'};
                    ">
                        <div style="font-weight: bold; margin-bottom: 4px;">
                            {html.escape(comment_display_name)} · <span style="font-weight: normal; color: #666;">{comment_time}</span>
                        </div>
                        <div>{comment_display}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                # 削除ボタン（自分のコメントかつ未削除の場合のみ表示）
                if is_own_comment and not is_deleted:
                    delete_key = f"delete_comment_{comment['id']}"
                    if st.button("削除", key=delete_key, type="secondary"):
                        if playlist_db.delete_playlist_comment(
                            comment_id=comment["id"],
                            user_sub=user_sub,
                        ):
                            st.success("コメントを削除しました")
                            st.rerun()
                        else:
                            st.error("コメントの削除に失敗しました")
        else:
            st.info("コメントはまだありません")

        if user_sub:
            form_key = f"playlist_comment_form_{playlist_id}"
            input_key = f"playlist_comment_input_{playlist_id}"
            with st.form(key=form_key, clear_on_submit=True):
                comment_input = st.text_area(
                    "コメントを追加",
                    key=input_key,
                    placeholder="このプレイリストへのコメントを書く",
                )
                st.caption("500文字以内")
                submitted = st.form_submit_button("送信", type="primary")

            if submitted:
                normalized_comment = (comment_input or "").strip()
                if not normalized_comment:
                    st.warning("コメントが空です")
                elif len(normalized_comment) > 500:
                    st.warning("コメントは500文字以内で入力してください")
                elif playlist_db.add_playlist_comment(
                    playlist_id=playlist_id,
                    user_sub=user_sub,
                    comment=normalized_comment,
                ):
                    st.success("コメントを追加しました")
                    st.rerun()
                else:
                    st.warning("コメントを追加できませんでした")
        else:
            st.info("コメント投稿にはログインが必要です")

    with st.expander(f"プレイリスト一覧 ({len(items)}曲)", expanded=False):
        if not items:
            st.warning("明細が見つかりません")
            st.divider()
            continue

        # Fetch source_dir for all songs in the playlist
        song_ids = [item["song_id"] for item in items]
        song_metadata = song_metadata_db.get_songs_as_dict(song_ids)

        table_rows = []
        distances = []
        for item in items:
            distance = float(item["cosine_distance"])
            distances.append(distance)
            song_id = item["song_id"]
            metadata = song_metadata.get(song_id, {})
            source_dir = metadata.get("source_dir", "-")
            table_rows.append(
                {
                    "Seq": item["seq"],
                    "Song ID": song_id,
                    "Source Dir": source_dir,
                    "コサイン距離": f"{distance:.6f}",
                }
            )

        df = pd.DataFrame(table_rows)
        styled_df = style_distance_column(df)

        col_count, col_avg = st.columns(2)
        with col_count:
            st.metric("曲数", f"{len(items)}曲")
        with col_avg:
            avg_distance = sum(distances) / len(distances) if distances else 0.0
            st.metric("平均コサイン距離", f"{avg_distance:.6f}")

        st.dataframe(
            styled_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Seq": st.column_config.NumberColumn("Seq", width="small"),
                "Song ID": st.column_config.TextColumn("Song ID", width="medium"),
                "Source Dir": st.column_config.TextColumn("Source Dir", width="medium"),
                "コサイン距離": st.column_config.TextColumn(
                    "コサイン距離", width="small"
                ),
            },
            height=400,
        )

    st.divider()
