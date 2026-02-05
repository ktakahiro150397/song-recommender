"""
楽曲レコメンドシステム - ホームページ
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from core.db_manager import SongVectorDB
from core.channel_db import ChannelDB
from core.song_queue_db import SongQueueDB
from core.feature_statistics import FeatureStatistics

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
        help="ベクトルデータベースに登録されている楽曲の総数",
    )

with col2:
    st.metric(
        label="📺 登録チャンネル数",
        value=f"{total_channels:,}",
        help="登録されているYouTubeチャンネルの数",
    )

with col3:
    st.metric(
        label="⏳ 処理待ち楽曲",
        value=f"{queue_counts['pending']:,}",
        help="YouTube動画からのダウンロード・登録待ちの楽曲数",
    )

with col4:
    st.metric(
        label="✅ 処理済み楽曲",
        value=f"{queue_counts['processed']:,}",
        help="YouTubeから処理完了した楽曲の数",
    )

# データベース詳細情報（展開可能）
with st.expander("🔍 データベース詳細情報", expanded=True):
    st.markdown("### ベクトルデータベース")
    st.markdown(
        """
    楽曲の音声特徴量を3つの異なるモードで保存しています：
    - **Full**: 全特徴量（72次元）- 細かい違いを見たい場合
    - **Balance**: バランス型（33次元）- 汎用的な検索に推奨
    - **Minimal**: 最小限（15次元）- テンポ・明るさ重視
    """
    )

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
                    collection_name=collection_name,
                    distance_fn="cosine",
                    use_remote=True,
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
                queue_counts["failed"],
            ],
        }
        queue_df = pd.DataFrame(queue_df_data)
        st.dataframe(queue_df, hide_index=True, use_container_width=True)
    else:
        st.info("キューにデータがありません")

# 音声特徴量の統計情報（ランダムサンプリング）
with st.expander("🎼 音声特徴量の統計情報", expanded=True):
    st.markdown(
        """
    データベースに登録されている楽曲の音声特徴量を分析しています。
    これにより、コレクション全体の傾向（明るさ、テンポ、音色など）がわかります。
    """
    )

    if total_songs > 0:
        try:
            # DBを初期化（上のtry-exceptで失敗していた場合のため）
            db_features = SongVectorDB(
                collection_name="songs_full", distance_fn="cosine", use_remote=True
            )

            # ランダムサンプリングして特徴量を取得（5%、最小10曲、最大1000曲）
            with st.spinner("データベースからランダムサンプリング中..."):
                songs_data = db_features.get_random_sample(sample_percentage=0.05)

            # データ構造を検証
            embeddings_data = songs_data.get("embeddings") if songs_data and isinstance(songs_data, dict) else None
            metadatas_data = songs_data.get("metadatas") if songs_data and isinstance(songs_data, dict) else None
            
            if (
                songs_data
                and isinstance(songs_data, dict)
                and embeddings_data is not None
                and (hasattr(embeddings_data, '__len__') and len(embeddings_data) > 0)
                and metadatas_data is not None
            ):
                sample_size = len(songs_data["ids"])
                st.success(
                    f"📊 データベースから**{sample_size}曲**をランダムサンプリングし、統計を計算しました "
                    f"（全{total_songs}曲の{(sample_size/total_songs*100):.1f}%）"
                )

                # 特徴量統計を計算
                embeddings = songs_data["embeddings"]
                # NumPy配列の場合はリストに変換
                if hasattr(embeddings, 'tolist'):
                    embeddings = embeddings.tolist()
                
                stats = FeatureStatistics.calculate_statistics(embeddings)

                if stats and isinstance(stats, dict) and stats.get("features"):
                    st.markdown("### 📈 特徴量の統計分析")

                    # カテゴリごとにグラフを表示
                    feature_groups = FeatureStatistics.get_feature_groups()

                    for category, feature_names in feature_groups.items():
                        st.markdown(f"#### {category}")

                        # カテゴリ内の特徴量データを集める
                        category_data = []
                        for feature_name in feature_names:
                            if feature_name in stats["features"]:
                                feature_stat = stats["features"][feature_name]
                                category_data.append(
                                    {
                                        "特徴量": feature_name,
                                        "平均": feature_stat["mean"],
                                        "標準偏差": feature_stat["std"],
                                        "最小値": feature_stat["min"],
                                        "最大値": feature_stat["max"],
                                    }
                                )

                        if category_data:
                            # データフレームに変換
                            df = pd.DataFrame(category_data)

                            # 横棒グラフを作成（平均値と標準偏差）
                            fig = go.Figure()

                            # 平均値のバー
                            fig.add_trace(
                                go.Bar(
                                    name="平均",
                                    y=df["特徴量"],
                                    x=df["平均"],
                                    orientation="h",
                                    marker_color="lightblue",
                                )
                            )

                            # 標準偏差をエラーバーとして追加
                            fig.add_trace(
                                go.Scatter(
                                    name="標準偏差",
                                    y=df["特徴量"],
                                    x=df["平均"],
                                    error_x=dict(
                                        type="data",
                                        array=df["標準偏差"],
                                        visible=True,
                                        color="red",
                                    ),
                                    mode="markers",
                                    marker=dict(size=8, color="darkblue"),
                                )
                            )

                            fig.update_layout(
                                title=f"{category}の平均値と標準偏差",
                                xaxis_title="値",
                                yaxis_title="",
                                height=max(250, len(category_data) * 60),
                                showlegend=True,
                                hovermode="y unified",
                            )

                            st.plotly_chart(fig, use_container_width=True)

                            # 詳細データテーブル
                            with st.expander(f"{category}の詳細統計", expanded=True):
                                st.dataframe(
                                    df.style.format(
                                        {
                                            "平均": "{:.4f}",
                                            "標準偏差": "{:.4f}",
                                            "最小値": "{:.4f}",
                                            "最大値": "{:.4f}",
                                        }
                                    ),
                                    hide_index=True,
                                    use_container_width=True,
                                )

                st.markdown("### 🎵 特徴量について")
                st.markdown(
                    """
                このシステムでは以下の音声特徴量を抽出しています：
                
                **音色・質感**
                - MFCC (メル周波数ケプストラム係数): 音色の特徴を20次元で表現
                - MFCC Delta: 音色の時間変化を20次元で表現
                
                **和音・調性**
                - Chroma (クロマグラム): 12音階の分布を12次元で表現
                - Tonnetz: 和声的関係（コード進行）を6次元で表現
                
                **音の明るさ・質感**
                - Spectral Centroid: 音の明るさ（周波数の重心）
                - Spectral Contrast: 音の谷と山の差（ジャンル識別に有効）を7次元で表現
                - Spectral Bandwidth: 音の広がり
                - Spectral Flatness: ノイズっぽさ（電子音 vs 生音）
                
                **リズム・エネルギー**
                - Tempo (BPM): 曲の速さ
                - RMS Energy: 音量レベル
                - Zero Crossing Rate: ノイジーさ・打楽器感
                """
                )
            else:
                st.warning("サンプルデータが取得できませんでした")
        except Exception as e:
            st.warning(f"特徴量統計の計算中にエラーが発生しました: {e}")
    else:
        st.info("登録されている楽曲がありません")
