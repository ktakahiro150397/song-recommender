"""
チャンネル一覧ページ

登録されているYouTubeチャンネルの一覧表示と管理
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from core.channel_db import ChannelDB


# ========== ページ設定 ==========

st.set_page_config(
    page_title="チャンネル一覧",
    page_icon="📋",
    layout="wide",
)

st.title("📋 YouTubeチャンネル一覧")
st.markdown("---")


# ========== メイン処理 ==========

# データベース初期化
db = ChannelDB()

# 全チャンネルを取得
channels = db.get_all_channels()

if not channels:
    st.info("📭 まだチャンネルが登録されていません")
    st.markdown("「YouTubeチャンネル登録」ページからチャンネルを登録してください")
else:
    # 統計情報を表示
    st.markdown(f"### 📊 統計情報")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("登録チャンネル数", f"{len(channels)}件")
    
    with col2:
        if channels:
            latest_date = channels[0]['registered_at'][:10]
            st.metric("最終登録日", latest_date)
    
    with col3:
        if channels:
            oldest_date = channels[-1]['registered_at'][:10]
            st.metric("最古の登録日", oldest_date)
    
    st.markdown("---")
    
    # フィルター・検索機能
    st.markdown("### 🔍 フィルター")
    col_search, col_sort = st.columns([2, 1])
    
    with col_search:
        search_query = st.text_input(
            "URL・チャンネル名で検索",
            placeholder="キーワードを入力...",
            label_visibility="collapsed"
        )
    
    with col_sort:
        sort_order = st.selectbox(
            "並び順",
            ["新しい順", "古い順"],
            label_visibility="collapsed"
        )
    
    # フィルタリング
    filtered_channels = channels
    if search_query:
        filtered_channels = [
            ch for ch in channels 
            if search_query.lower() in ch['url'].lower() 
            or (ch.get('channel_name') and search_query.lower() in ch['channel_name'].lower())
        ]
    
    # ソート
    if sort_order == "古い順":
        filtered_channels = list(reversed(filtered_channels))
    
    st.markdown(f"**{len(filtered_channels)}件** のチャンネルが見つかりました")
    st.markdown("---")
    
    # チャンネル一覧を表示
    st.markdown("### 📺 チャンネル一覧")
    
    if not filtered_channels:
        st.warning("検索条件に一致するチャンネルがありません")
    else:
        # ページネーション設定
        items_per_page = 10
        total_pages = (len(filtered_channels) - 1) // items_per_page + 1
        
        # ページ番号選択
        if total_pages > 1:
            page = st.number_input(
                "ページ",
                min_value=1,
                max_value=total_pages,
                value=1,
                step=1,
                help=f"全{total_pages}ページ"
            )
        else:
            page = 1
        
        # 表示範囲を計算
        start_idx = (page - 1) * items_per_page
        end_idx = min(start_idx + items_per_page, len(filtered_channels))
        page_channels = filtered_channels[start_idx:end_idx]
        
        # チャンネルをカード形式で表示
        for i, channel in enumerate(page_channels, start=start_idx + 1):
            with st.container():
                # カード風デザイン（レスポンシブ対応）
                card_col1, card_col2 = st.columns([1, 3])
                
                with card_col1:
                    # サムネイルを表示
                    thumbnail_url = channel.get('thumbnail_url')
                    if thumbnail_url:
                        st.image(thumbnail_url, width=150)
                    else:
                        st.markdown("🎵")
                
                with card_col2:
                    # 番号とアーティスト名を横並びで余白なし表示
                    st.markdown(
                        f"<div style='display:flex;align-items:center;gap:0.5em;margin-bottom:0;'>"
                        f"<span style='font-weight:bold;font-size:1.2em;'>#{i}</span>"
                        f"<span style='font-weight:bold;font-size:1.2em;'>{channel.get('channel_name','')}</span>"
                        f"</div>", unsafe_allow_html=True
                    )
                    # URL
                    st.markdown(f"🔗 [{channel['url']}]({channel['url']})", unsafe_allow_html=True)
                    # チャンネルIDと登録日時を横並び
                    info_col1, info_col2 = st.columns(2)
                    with info_col1:
                        channel_id = channel.get('channel_id', 'N/A')
                        st.caption(f"📺 ID: `{channel_id}`")
                    with info_col2:
                        registered_time = channel['registered_at']
                        try:
                            dt = datetime.fromisoformat(registered_time)
                            formatted_time = dt.strftime("%Y/%m/%d %H:%M")
                        except:
                            formatted_time = registered_time[:16]
                        st.caption(f"📅 {formatted_time}")
                    # 一番下に削除ボタン（幅固定）
                    st.markdown("<div style='height:0.5em'></div>", unsafe_allow_html=True)
                    btn_style = "display:block;width:120px;margin:0 auto;"
                    btn_placeholder = st.empty()
                    if btn_placeholder.button(
                        "🗑️ 削除",
                        key=f"delete_{channel['id']}",
                        type="secondary",
                        help="削除"
                    ):
                        st.session_state[f"confirm_delete_{channel['id']}"] = True
                    # ボタン幅をCSSで制御
                    st.markdown(f"""
                        <style>
                        div[data-testid='stButton'] button[key='delete_{channel['id']}'] {{
                            width:120px !important;
                            min-width:120px !important;
                            max-width:120px !important;
                        }}
                        </style>
                    """, unsafe_allow_html=True)
                    # 削除確認ダイアログ
                    if st.session_state.get(f"confirm_delete_{channel['id']}", False):
                        st.warning(f"本当に削除しますか？")
                        col_yes, col_no = st.columns(2)
                        with col_yes:
                            if st.button("削除", key=f"confirm_yes_{channel['id']}", type="primary", use_container_width=True):
                                success, message = db.delete_channel(channel['id'])
                                if success:
                                    st.success(message)
                                    if f"confirm_delete_{channel['id']}" in st.session_state:
                                        del st.session_state[f"confirm_delete_{channel['id']}"]
                                    st.rerun()
                                else:
                                    st.error(message)
                        with col_no:
                            if st.button("キャンセル", key=f"confirm_no_{channel['id']}", use_container_width=True):
                                del st.session_state[f"confirm_delete_{channel['id']}"]
                                st.rerun()
                
                st.divider()
        
        # ページネーション情報
        if total_pages > 1:
            st.caption(f"ページ {page} / {total_pages} （{start_idx + 1}-{end_idx}件目を表示中）")

# エクスポート機能
st.markdown("---")
st.markdown("### 💾 データエクスポート")

col_export1, col_export2 = st.columns(2)

with col_export1:
    if st.button("📄 CSV形式でダウンロード", use_container_width=True):
        if channels:
            # DataFrameに変換
            df = pd.DataFrame(channels)
            csv = df.to_csv(index=False, encoding='utf-8-sig')
            
            st.download_button(
                label="⬇️ CSVファイルをダウンロード",
                data=csv,
                file_name=f"youtube_channels_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        else:
            st.warning("エクスポートするデータがありません")

with col_export2:
    if st.button("📋 URLリストをコピー", use_container_width=True):
        if channels:
            # URLのみを抽出してテキスト形式に
            url_list = "\n".join([ch['url'] for ch in channels])
            st.code(url_list, language="text")
            st.info("上記のテキストをコピーしてご利用ください")
        else:
            st.warning("コピーするデータがありません")

# フッター
st.markdown("---")
st.caption("💡 チャンネルの追加は「YouTubeチャンネル登録」ページから行えます")
