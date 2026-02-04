"""
楽曲レコメンドシステム - Streamlitアプリ

使い方:
    streamlit run app.py
"""

import streamlit as st

st.set_page_config(
    page_title="楽曲レコメンドシステム",
    page_icon="🎵",
    layout="wide",
)

# ページ定義
pages = [
    st.Page("home_page.py", title="TOP", icon="🏠", default=True),
    st.Page("pages/1_🎵_楽曲検索.py", title="楽曲検索", icon="🎵"),
    st.Page("pages/5_📺_YouTube登録.py", title="YouTube登録", icon="📺"),
    st.Page(
        "pages/6_📋_登録済みコンテンツ管理.py",
        title="登録済みコンテンツ管理",
        icon="📋",
    ),
    st.Page("pages/3_🗄️_DBメンテナンス.py", title="DBメンテナンス", icon="🗄️"),
]

# ナビゲーションを設定
pg = st.navigation(pages)

# ページを実行
pg.run()
