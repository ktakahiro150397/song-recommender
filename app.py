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

- **🔍 曲調おすすめプレイリスト**: 指定した楽曲から似た曲を連鎖的に検索
- **🎵 個別曲検索**: キーワードで楽曲を検索
- **🗄️ DBメンテナンス**: データベースの管理と曲の削除
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
                
                # フォルダ全体のサイズを計算
                total_size = 0
                db_path = Path(path)
                for file in db_path.rglob('*'):
                    if file.is_file():
                        total_size += file.stat().st_size
                
                # 適切な単位で表示
                if total_size < 1024:
                    size_str = f"{total_size} B"
                elif total_size < 1024 * 1024:
                    size_str = f"{total_size / 1024:.1f} KB"
                elif total_size < 1024 * 1024 * 1024:
                    size_str = f"{total_size / (1024 * 1024):.1f} MB"
                else:
                    size_str = f"{total_size / (1024 * 1024 * 1024):.2f} GB"
                
                st.metric(label=f"{name} DB", value=f"{count:,} 曲")
                st.caption(f"💾 {size_str}")
            except Exception as e:
                st.error(f"{name}: エラー")
        else:
            st.warning(f"{name}: 未作成")
