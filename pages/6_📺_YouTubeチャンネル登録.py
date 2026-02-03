"""
YouTubeチャンネル登録ページ

YouTubeチャンネルのURLを登録する
"""

import streamlit as st
from core.channel_db import ChannelDB
from core.ytmusic_manager import YTMusicManager
from pathlib import Path


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

# YTMusic初期化（認証なしモードでサムネイル取得）
ytmusic = None
try:
    from ytmusicapi import YTMusic
    ytmusic = YTMusic()  # 認証なしモード（公開情報のみ取得可能）
    st.success("✅ YouTube Music API準備完了（サムネイル自動取得有効）")
except Exception as e:
    st.warning(f"⚠️ YouTube Music APIの初期化に失敗（サムネイルなしで登録します）: {str(e)}")

# 現在の登録数を表示
channel_count = db.get_channel_count()
st.info(f"現在 **{channel_count}件** のチャンネルが登録されています")

st.markdown("### チャンネルURLを登録")

# URL入力欄
with st.form("channel_registration_form"):
    url_input = st.text_input(
        "YouTubeチャンネルのURLを入力してください",
        placeholder="https://music.youtube.com/channel/UCxxxxxxxxxxxxx",
        help="/channel/UCxxxxx 形式のみ受け付けます（例: https://music.youtube.com/channel/UC8p5DuhOMR7fZLgnybVX0sA）"
    )
    
    submit_button = st.form_submit_button("🔖 登録する", type="primary")

# フォーム送信時の処理
if submit_button:
    if not url_input:
        st.error("URLを入力してください")
    else:
        # URLを登録（YTMusicインスタンスを渡す）
        success, message, thumbnail_url = db.add_channel(url_input.strip(), ytmusic=ytmusic)
        
        if success:
            st.success(message)
            
            # サムネイルが取得できた場合はプレビュー表示
            if thumbnail_url:
                st.markdown("#### 🖼️ チャンネル情報")
                col1, col2 = st.columns([1, 3])
                with col1:
                    st.image(thumbnail_url, width=150)
                with col2:
                    # チャンネル情報を再取得して表示
                    channels = db.get_all_channels()
                    if channels:
                        latest = channels[0]
                        if latest.get('channel_name'):
                            st.markdown(f"**チャンネル名:** {latest['channel_name']}")
                        st.markdown(f"**URL:** {url_input}")
                        st.caption("サムネイルとチャンネル名を取得しました！")
            
            # 登録後、入力欄をクリア（再実行で反映）
            st.rerun()
        else:
            st.error(message)

# 使い方の説明
st.markdown("---")
st.markdown("### 📝 使い方")

with st.expander("対応するURL形式"):
    st.markdown("""
    **チャンネルID形式のみ対応しています：**
    
    - ✅ `https://music.youtube.com/channel/UCxxxxx`
    - ✅ `https://www.youtube.com/channel/UCxxxxx`
    - ✅ `https://youtube.com/channel/UCxxxxx`
    
    ❌ その他の形式（@username、/c/xxx、/user/xxx）には対応していません
    
    **チャンネルIDの確認方法：**
    1. YouTubeでチャンネルページを開く
    2. URLを確認し、`/channel/UC` で始まる形式であることを確認
    3. そのURLをコピーして登録
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
            # チャンネル名がある場合は表示
            channel_name = channel.get('channel_name')
            if channel_name:
                st.markdown(f"{i}. **{channel_name}** - [{channel['url']}]({channel['url']})")
            else:
                st.markdown(f"{i}. [{channel['url']}]({channel['url']})")
    if len(channels) > 5:
        st.info(f"他 {len(channels) - 5} 件のチャンネルが登録されています。一覧は「チャンネル一覧」ページで確認できます。")
else:
    st.info("まだチャンネルが登録されていません")

# フッター
st.markdown("---")
st.caption("💡 登録したチャンネルは「チャンネル一覧」ページで管理できます")
