"""
YouTubeチャンネル登録ページ

YouTubeチャンネルのURLを登録する
"""

import streamlit as st
from core.channel_db import ChannelDB


# ========== ページ設定 ==========

st.set_page_config(
    page_title="YouTubeチャンネル登録",
    page_icon="📺",
    layout="wide",
)

st.title("📺 YouTubeチャンネル登録")
st.markdown("---")


# ========== メイン処理 ==========

# データベース初期化
db = ChannelDB()

# 現在の登録数を表示
channel_count = db.get_channel_count()
st.info(f"現在 **{channel_count}件** のチャンネルが登録されています")

st.markdown("### チャンネルURLを登録")

# URL入力欄
with st.form("channel_registration_form"):
    url_input = st.text_input(
        "YouTubeチャンネルのURLを入力してください",
        placeholder="https://www.youtube.com/@username または https://www.youtube.com/channel/UCxxxxx",
        help="チャンネルのトップページURLを入力してください"
    )
    
    submit_button = st.form_submit_button("🔖 登録する", type="primary")

# フォーム送信時の処理
if submit_button:
    if not url_input:
        st.error("URLを入力してください")
    else:
        # URLを登録
        success, message = db.add_channel(url_input.strip())
        
        if success:
            st.success(message)
            # 登録後、入力欄をクリア（再実行で反映）
            st.rerun()
        else:
            st.error(message)

# 使い方の説明
st.markdown("---")
st.markdown("### 📝 使い方")

with st.expander("対応するURL形式"):
    st.markdown("""
    以下の形式のYouTubeチャンネルURLに対応しています：
    
    - **新形式（ハンドル）**: `https://www.youtube.com/@username`
    - **チャンネルID形式**: `https://www.youtube.com/channel/UCxxxxx`
    - **カスタムURL**: `https://www.youtube.com/c/channelname`
    - **ユーザー名形式**: `https://www.youtube.com/user/username`
    
    **対応ドメイン**:
    - `www.youtube.com`
    - `youtube.com`
    - `m.youtube.com`
    - `music.youtube.com`
    """)

with st.expander("URL検証について"):
    st.markdown("""
    登録時に以下のチェックが行われます：
    
    ✅ YouTubeの正規ドメインかどうか  
    ✅ チャンネルURL形式として正しいか  
    ✅ 既に登録されていないか（重複チェック）
    """)

# サンプルデータを表示（最近登録された5件）
st.markdown("---")
st.markdown("### 📋 最近登録されたチャンネル")

channels = db.get_all_channels()
if channels:
    # 最新5件を表示
    recent_channels = channels[:5]
    
    for i, channel in enumerate(recent_channels, 1):
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"{i}. [{channel['url']}]({channel['url']})")
        with col2:
            st.caption(f"登録日時: {channel['registered_at'][:19]}")
    
    if len(channels) > 5:
        st.info(f"他 {len(channels) - 5} 件のチャンネルが登録されています。一覧は「チャンネル一覧」ページで確認できます。")
else:
    st.info("まだチャンネルが登録されていません")

# フッター
st.markdown("---")
st.caption("💡 登録したチャンネルは「チャンネル一覧」ページで管理できます")
