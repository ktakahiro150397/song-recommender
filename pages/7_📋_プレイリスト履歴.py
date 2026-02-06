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


st.set_page_config(
    page_title="プレイリスト履歴",
    page_icon="📋",
    layout="wide",
)

st.title("📋 作成済みプレイリスト履歴")
st.markdown("---")


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
email_map = get_emails_by_subs(creator_subs)

for idx, header in enumerate(headers, 1):
    creator_sub = header.get("creator_sub") or ""
    playlist_name = header["playlist_name"]
    playlist_id = header["playlist_id"]
    playlist_url = header["playlist_url"]
    creator_email = email_map.get(creator_sub) or "-"
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
                creator_email,
                created_at_display,
            ],
        }
    )
    st.dataframe(header_df, use_container_width=True, hide_index=True)

    if header_comment:
        header_comment_html = html.escape(header_comment).replace("\n", "<br>")
        st.markdown(
            f"**プレイリストコメント**<br>{header_comment_html}",
            unsafe_allow_html=True,
        )

    with st.expander("コメント", expanded=False):
        comments = playlist_db.list_playlist_comments(playlist_id, limit=200)
        comment_user_subs = [comment["user_sub"] for comment in comments]
        comment_email_map = get_emails_by_subs(comment_user_subs)

        if comments:
            for comment in comments:
                comment_email = comment_email_map.get(comment["user_sub"], "-")
                comment_time = format_created_at(comment["created_at"], timezone)
                with st.chat_message("user"):
                    st.markdown(f"**{comment_email}** · {comment_time}")
                    st.write(comment["comment"])
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

        table_rows = []
        distances = []
        for item in items:
            distance = float(item["cosine_distance"])
            distances.append(distance)
            table_rows.append(
                {
                    "Seq": item["seq"],
                    "Song ID": item["song_id"],
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

        st.dataframe(styled_df, use_container_width=True, hide_index=True)

    st.divider()
