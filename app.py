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
st.subheader("📊 データベース統計")

from core.db_manager import SongVectorDB
from core.channel_db import ChannelDB
from core.song_queue_db import SongQueueDB

# データを取得
try:
    # 曲数を取得（Fullデータベースから）
    db = SongVectorDB(
        collection_name="songs_full", distance_fn="cosine", use_remote=True
    )
    total_songs = db.count()
except Exception as e:
    total_songs = 0
    st.warning(f"曲数の取得に失敗しました: {e}")

try:
    # チャンネル数を取得
    channel_db = ChannelDB()
    total_channels = channel_db.get_channel_count()
except Exception as e:
    total_channels = 0
    st.warning(f"チャンネル数の取得に失敗しました: {e}")

try:
    # キュー統計を取得
    queue_db = SongQueueDB()
    queue_counts = queue_db.get_counts()
except Exception as e:
    queue_counts = {"pending": 0, "processed": 0, "failed": 0, "total": 0}
    st.warning(f"キュー統計の取得に失敗しました: {e}")

# メトリクスを表示
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        label="🎵 登録済み楽曲数",
        value=f"{total_songs:,}",
        help="ベクトルデータベースに登録されている楽曲の総数"
    )

with col2:
    st.metric(
        label="📺 登録チャンネル数",
        value=f"{total_channels:,}",
        help="登録されているYouTubeチャンネルの数"
    )

with col3:
    st.metric(
        label="⏳ 処理待ち楽曲",
        value=f"{queue_counts['pending']:,}",
        help="YouTube動画からのダウンロード・登録待ちの楽曲数"
    )

with col4:
    st.metric(
        label="✅ 処理済み楽曲",
        value=f"{queue_counts['processed']:,}",
        help="YouTubeから処理完了した楽曲の数"
    )

# データベース詳細情報（展開可能）
with st.expander("🔍 データベース詳細情報"):
    st.markdown("### ベクトルデータベース")
    st.markdown("""
    楽曲の音声特徴量を3つの異なるモードで保存しています：
    - **Full**: 全特徴量（72次元）- 細かい違いを見たい場合
    - **Balance**: バランス型（33次元）- 汎用的な検索に推奨
    - **Minimal**: 最小限（15次元）- テンポ・明るさ重視
    """)
    
    db_cols = st.columns(3)
    DB_COLLECTIONS = {
        "Full": "songs_full",
        "Balance": "songs_balanced",
        "Minimal": "songs_minimal",
    }
    
    for idx, (name, collection_name) in enumerate(DB_COLLECTIONS.items()):
        with db_cols[idx]:
            try:
                db_detail = SongVectorDB(
                    collection_name=collection_name, distance_fn="cosine", use_remote=True
                )
                count = db_detail.count()
                st.metric(label=f"{name} DB", value=f"{count:,} 曲")
            except Exception as e:
                st.metric(label=f"{name} DB", value="エラー")
    
    st.markdown("### YouTube楽曲キュー")
    if queue_counts["total"] > 0:
        queue_df_data = {
            "ステータス": ["⏳ 処理待ち", "✅ 処理済み", "❌ 失敗"],
            "件数": [
                queue_counts["pending"],
                queue_counts["processed"],
                queue_counts["failed"]
            ]
        }
        import pandas as pd
        queue_df = pd.DataFrame(queue_df_data)
        st.dataframe(queue_df, hide_index=True, use_container_width=True)
    else:
        st.info("キューにデータがありません")
