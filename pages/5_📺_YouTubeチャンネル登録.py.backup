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
    st.warning(
        f"⚠️ YouTube Music APIの初期化に失敗（サムネイルなしで登録します）: {str(e)}"
    )

# 現在の登録数を表示
channel_count = db.get_channel_count()
st.info(f"現在 **{channel_count}件** のチャンネルが登録されています")

st.markdown("### チャンネルURLを登録")

# URL入力欄
with st.form("channel_registration_form"):
    url_input = st.text_area(
        "YouTubeチャンネルのURLを入力してください（改行区切りで複数URL可）",
        placeholder="https://music.youtube.com/channel/UCxxxxxxxxxxxxx\nhttps://music.youtube.com/channel/UCyyyyyyyyyyyyyy\nhttps://music.youtube.com/channel/UCzzzzzzzzzzzzzz",
        help="/channel/UCxxxxx 形式のみ受け付けます。複数のURLを改行で区切って入力できます。",
        height=150,
    )

    submit_button = st.form_submit_button("🔖 登録する", type="primary")

# フォーム送信時の処理
if submit_button:
    if not url_input:
        st.error("URLを入力してください")
    else:
        # 改行で分割してURLリストを作成
        url_list = [url.strip() for url in url_input.split("\n") if url.strip()]

        if not url_list:
            st.error("有効なURLを入力してください")
        else:
            # 登録結果を格納
            success_count = 0
            error_count = 0
            results = []

            # プログレスバーを表示
            progress_bar = st.progress(0)
            status_text = st.empty()

            for idx, url in enumerate(url_list):
                # 進捗を更新
                progress = (idx + 1) / len(url_list)
                progress_bar.progress(progress)
                status_text.text(f"登録中... ({idx + 1}/{len(url_list)})")

                # URLを登録
                success, message, thumbnail_url = db.add_channel(url, ytmusic=ytmusic)

                if success:
                    success_count += 1
                    results.append(
                        {"url": url, "status": "✅ 成功", "message": message}
                    )
                else:
                    error_count += 1
                    results.append(
                        {"url": url, "status": "❌ 失敗", "message": message}
                    )

            # プログレスバーをクリア
            progress_bar.empty()
            status_text.empty()

            # 結果のサマリーを表示
            st.markdown("### 📊 登録結果")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("合計", f"{len(url_list)}件")
            with col2:
                st.metric(
                    "成功",
                    f"{success_count}件",
                    delta=None if success_count == 0 else success_count,
                )
            with col3:
                st.metric(
                    "失敗",
                    f"{error_count}件",
                    delta=None if error_count == 0 else -error_count,
                )

            # 詳細結果を表示
            st.markdown("### 📋 詳細")
            for result in results:
                if result["status"].startswith("✅"):
                    st.success(
                        f"{result['status']} {result['url']}: {result['message']}"
                    )
                else:
                    st.error(f"{result['status']} {result['url']}: {result['message']}")

            # 成功が1件以上あれば画面をリロード
            if success_count > 0:
                st.rerun()

# 使い方の説明
st.markdown("---")
st.markdown("### 📝 使い方")

with st.expander("対応するURL形式"):
    st.markdown(
        """
    **チャンネルID形式のみ対応しています：**
    
    - ✅ `https://music.youtube.com/channel/UCxxxxx`
    - ✅ `https://www.youtube.com/channel/UCxxxxx`
    - ✅ `https://youtube.com/channel/UCxxxxx`
    
    ❌ その他の形式（@username、/c/xxx、/user/xxx）には対応していません
    
    **チャンネルIDの確認方法：**
    1. YouTubeでチャンネルページを開く
    2. URLを確認し、`/channel/UC` で始まる形式であることを確認
    3. そのURLをコピーして登録
    """
    )

with st.expander("URL検証について"):
    st.markdown(
        """
    登録時に以下のチェックが行われます：
    
    ✅ YouTubeの正規ドメインかどうか  
    ✅ チャンネルURL形式として正しいか  
    ✅ 既に登録されていないか（重複チェック）
    """
    )

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
            channel_name = channel.get("channel_name")
            if channel_name:
                st.markdown(
                    f"{i}. **{channel_name}** - [{channel['url']}]({channel['url']})"
                )
            else:
                st.markdown(f"{i}. [{channel['url']}]({channel['url']})")
    if len(channels) > 5:
        st.info(
            f"他 {len(channels) - 5} 件のチャンネルが登録されています。一覧は「チャンネル一覧」ページで確認できます。"
        )
else:
    st.info("まだチャンネルが登録されていません")

# フッター
st.markdown("---")
st.caption("💡 登録したチャンネルは「チャンネル一覧」ページで管理できます")
