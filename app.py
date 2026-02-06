"""
楽曲レコメンドシステム - Streamlitアプリ

使い方:
    streamlit run app.py
"""

import streamlit as st

from core.user_db import upsert_user_identity

st.set_page_config(
    page_title="楽曲レコメンドシステム",
    page_icon="🎵",
    layout="wide",
)

# Require login before loading any pages.
if not st.user.is_logged_in:
    st.title("ログイン")
    st.write("Googleアカウントでログインしてください")
    if st.button("Googleでログイン"):
        st.login()
    st.stop()

upsert_user_identity(
    user_sub=getattr(st.user, "sub", ""),
    email=getattr(st.user, "email", ""),
)

# ページ定義
pages = [
    st.Page("home_page.py", title="TOP", icon="🏠", default=True),
    st.Page("pages/1_🎵_楽曲検索.py", title="楽曲検索", icon="🎵"),
    st.Page("pages/5_📺_YouTube登録.py", title="YouTube登録", icon="📺"),
    st.Page(
        "pages/7_📋_プレイリスト履歴.py",
        title="プレイリスト履歴",
        icon="📋",
    ),
    st.Page(
        "pages/6_📋_登録済みコンテンツ管理.py",
        title="登録済みコンテンツ管理",
        icon="📋",
    ),
    st.Page("pages/3_🗄️_DBメンテナンス.py", title="DBメンテナンス", icon="🗄️"),
    st.Page("pages/8_⚙️_ユーザー設定.py", title="ユーザー設定", icon="⚙️"),
]

# ナビゲーションを設定
pg = st.navigation(pages)

if pg.title == "TOP":
    user_email = getattr(st.user, "email", "")
    with st.container(border=False):
        email_col, button_col = st.columns([6, 4])
        with email_col:
            st.markdown(f"**{user_email}**" if user_email else "**ログイン中**")
        with button_col:
            if st.button("ログアウト", use_container_width=True):
                st.logout()
            st.markdown(
                """
                <div style="display: flex; justify-content: flex-end; align-items: center; min-width: 400px; max-width: 500px; margin-left: auto;">
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.session_state.get("logout") or st.query_params.get("logout"):
                st.logout()

# ページを実行
pg.run()
