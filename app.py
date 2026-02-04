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
    st.Page(
        "pages/2_📤_楽曲ファイルアップロード.py",
        title="楽曲ファイルアップロード",
        icon="📤",
    ),
    st.Page("pages/3_🗄️_DBメンテナンス.py", title="DBメンテナンス", icon="🗄️"),
    st.Page(
        "pages/4_🗄️_DBメンテナンス_楽曲登録.py",
        title="DBメンテナンス 楽曲登録",
        icon="🗄️",
    ),
    st.Page(
        "pages/5_📺_YouTubeチャンネル登録.py", title="YouTubeチャンネル登録", icon="📺"
    ),
    st.Page("pages/6_📋_チャンネル一覧.py", title="チャンネル一覧", icon="📋"),
    st.Page("pages/7_🎵_YouTube曲登録.py", title="YouTube曲登録", icon="🎵"),
]

# ナビゲーションを設定
pg = st.navigation(pages)

# ページを実行
pg.run()
