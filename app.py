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

st.title("🎵 楽曲レコメンドシステム")

st.markdown("""
### ようこそ！

このアプリでは以下の機能が利用できます：

- **🔍 連鎖検索**: 指定した楽曲から似た曲を連鎖的に検索
- **🎵 楽曲検索**: キーワードで楽曲を検索
- **🗄️ DBメンテナンス**: データベースの管理と曲の削除

左のサイドバーからページを選択してください。
""")

st.info("📌 左側のサイドバーからページを選択してください")

# DBの統計情報を表示
st.subheader("データベース統計")

from pathlib import Path
from core.db_manager import SongVectorDB

DB_PATHS = {
    "Full": "data/chroma_db_cos_full",
    "Balance": "data/chroma_db_cos_balance",
    "Minimal": "data/chroma_db_cos_minimal",
}

cols = st.columns(3)
for idx, (name, path) in enumerate(DB_PATHS.items()):
    with cols[idx]:
        if Path(path).exists():
            try:
                db = SongVectorDB(db_path=path, distance_fn="cosine")
                count = db.count()
                st.metric(label=f"{name} DB", value=f"{count:,} 曲")
            except Exception as e:
                st.error(f"{name}: エラー")
        else:
            st.warning(f"{name}: 未作成")
