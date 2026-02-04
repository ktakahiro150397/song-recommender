"""
楽曲レコメンドシステム - ホームページ
"""

import streamlit as st
from core.db_manager import SongVectorDB

st.title("🎵 楽曲レコメンドシステム")

st.markdown(
    """
### ようこそ！

このアプリでは以下の機能が利用できます：

- **🔍 曲調おすすめプレイリスト**: 指定した楽曲から似た曲を連鎖的に検索
- **🎵 個別曲検索**: キーワードで楽曲を検索
- **🗄️ DBメンテナンス**: データベースの管理と曲の削除
"""
)

st.info("📌 左側のサイドバーからページを選択してください")

# DBの統計情報を表示
st.subheader("データベース統計")

# リモートChromaDBサーバーのコレクション名
DB_COLLECTIONS = {
    "Full": "songs_full",
    "Balance": "songs_balanced",
    "Minimal": "songs_minimal",
}

cols = st.columns(3)
for idx, (name, collection_name) in enumerate(DB_COLLECTIONS.items()):
    with cols[idx]:
        try:
            # リモートChromaDBサーバーに接続（use_remote=True）
            db = SongVectorDB(
                collection_name=collection_name, distance_fn="cosine", use_remote=True
            )
            count = db.count()

            st.metric(label=f"{name} DB", value=f"{count:,} 曲")
        except Exception as e:
            st.warning(f"{name}: 接続エラー")
