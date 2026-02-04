"""
YouTube登録ページ（統合版）

YouTubeチャンネルと動画の両方に対応した統合登録ページ
"""

import streamlit as st
from core.youtube_registration import YouTubeRegistration
from core.channel_db import ChannelDB
from core.song_queue_db import SongQueueDB


# ========== ページ設定 ==========

st.set_page_config(
    page_title="YouTube登録",
    page_icon="📺",
    layout="wide",
)

st.title("📺 YouTube登録（チャンネル / 曲 / プレイリスト）")
st.markdown("---")


# ========== メイン処理 ==========

# 統合登録システム初期化
registration = YouTubeRegistration()

# YTMusic初期化（認証なしモードでサムネイル取得）
ytmusic = None
try:
    from ytmusicapi import YTMusic

    ytmusic = YTMusic()
    st.success("✅ YouTube Music API準備完了（サムネイル自動取得有効）")
except Exception as e:
    st.warning(
        f"⚠️ YouTube Music APIの初期化に失敗（サムネイルなしで登録します）: {str(e)}"
    )

# 現在の登録状況を表示
channel_db = ChannelDB()
song_db = SongQueueDB()

col1, col2 = st.columns(2)
with col1:
    channel_count = channel_db.get_channel_count()
    st.metric("登録チャンネル数", f"{channel_count}件")
with col2:
    song_counts = song_db.get_counts()
    st.metric(
        "登録曲数（キュー）",
        f"{song_counts['total']}件",
        help=f"未処理: {song_counts['pending']}件 / 処理済み: {song_counts['processed']}件",
    )

st.markdown("### YouTubeのURLを登録")

# URL入力欄
with st.form("youtube_registration_form"):
    url_input = st.text_area(
        "YouTubeのURLを入力してください（改行区切りで複数URL可）",
        placeholder="""https://music.youtube.com/channel/UCxxxxxxxxxxxxx
https://www.youtube.com/watch?v=xxxxx
https://youtu.be/yyyyy
https://www.youtube.com/playlist?list=PLxxxxxxxxxxxxx
https://music.youtube.com/channel/UCyyyyyyyyyyyyyy""",
        help="""対応形式:
✅ チャンネル: /channel/UCxxxxx
✅ 動画: watch?v=xxxxx, youtu.be/xxxxx
✅ プレイリスト: playlist?list=xxxxx
複数のURLを改行で区切って入力できます。自動的に種類を判別します。""",
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
            # プログレスバーを表示
            progress_bar = st.progress(0)
            status_text = st.empty()

            def progress_callback(current, total, url):
                progress = current / total
                progress_bar.progress(progress)
                status_text.text(f"登録中... ({current}/{total})")

            # 一括登録実行
            results = registration.register_urls_batch(
                url_list, ytmusic=ytmusic, progress_callback=progress_callback
            )

            # プログレスバーをクリア
            progress_bar.empty()
            status_text.empty()

            # 結果のサマリーを表示
            st.markdown("### 📊 登録結果")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("合計", f"{results['total']}件")
            with col2:
                channel_total = results["channel_success"] + results["channel_failed"]
                st.metric(
                    "チャンネル",
                    f"{channel_total}件",
                    help=f"成功: {results['channel_success']}件 / 失敗: {results['channel_failed']}件",
                )
            with col3:
                video_total = results["video_success"] + results["video_failed"]
                st.metric(
                    "動画",
                    f"{video_total}件",
                    help=f"成功: {results['video_success']}件 / 失敗: {results['video_failed']}件",
                )
            with col4:
                playlist_total = (
                    results["playlist_success"] + results["playlist_failed"]
                )
                st.metric(
                    "プレイリスト",
                    f"{playlist_total}件",
                    help=f"成功: {results['playlist_success']}件 / 失敗: {results['playlist_failed']}件",
                )

            # 詳細結果を表示
            st.markdown("### 📋 詳細")
            for detail in results["details"]:
                type_emoji = {
                    "channel": "📺 チャンネル",
                    "video": "🎵 動画",
                    "playlist": "📋 プレイリスト",
                    "unknown": "❓ 不明",
                }.get(detail["type"], "❓")

                if detail["success"]:
                    st.success(
                        f"✅ [{type_emoji}] {detail['url']}: {detail['message']}"
                    )
                else:
                    st.error(f"❌ [{type_emoji}] {detail['url']}: {detail['message']}")

            # 成功が1件以上あれば、統計情報を更新するためのボタンを表示
            if (
                results["channel_success"] > 0
                or results["video_success"] > 0
                or results["playlist_success"] > 0
            ):
                st.markdown("---")
                if st.button(
                    "📊 統計情報を更新", type="secondary", use_container_width=True
                ):
                    st.rerun()


# 使い方の説明
st.markdown("---")
st.markdown("### 📝 使い方")

with st.expander("対応するURL形式"):
    st.markdown(
        """
    **チャンネルURL**：
    
    - ✅ `https://music.youtube.com/channel/UCxxxxx`
    - ✅ `https://www.youtube.com/channel/UCxxxxx`
    - ✅ `https://youtube.com/channel/UCxxxxx`
    
    **動画URL**：
    
    - ✅ `https://www.youtube.com/watch?v=xxxxx`
    - ✅ `https://music.youtube.com/watch?v=xxxxx`
    - ✅ `https://youtu.be/xxxxx`
    - ✅ 動画ID（11文字）のみ: `xxxxx`
    
    **プレイリストURL**：
    
    - ✅ `https://www.youtube.com/playlist?list=PLxxxxx`
    - ✅ `https://music.youtube.com/playlist?list=PLxxxxx`
    
    **混在入力OK**: チャンネル、動画、プレイリストを混ぜて入力しても自動判別します！
    """
    )

with st.expander("登録後の処理フロー"):
    st.markdown(
        """
    **チャンネル登録の場合**：
    1. チャンネル情報がDBに保存されます
    2. サムネイルとチャンネル名が自動取得されます
    3. 「チャンネル一覧」ページで確認・管理できます
    
    **動画登録の場合**：
    1. 動画URLがキューに追加されます
    2. `uv run register_songs.py --parallel process` を実行してダウンロード＆DB登録
    3. 登録後は「楽曲検索」で検索・再生可能になります
    
    **プレイリスト登録の場合**：
    1. プレイリスト内の全動画が自動的に抽出されます
    2. 各動画が動画キューに追加されます（既存の動画はスキップされます）
    3. その後は動画登録と同じ処理フローになります
    """
    )

with st.expander("複数URL一括登録のコツ"):
    st.markdown(
        """
    - 1行に1つのURLを入力してください
    - チャンネル、動画、プレイリストを混ぜて入力してもOK
    - 重複したURLは自動的にスキップされます
    - 無効なURL形式はエラーとして報告されます
    - プレイリストの動画は自動的に個別に登録されます
    """
    )

# 最近登録されたコンテンツを表示
st.markdown("---")
st.markdown("### 📋 最近登録されたコンテンツ")

tab1, tab2 = st.tabs(["📺 チャンネル", "🎵 動画（キュー）"])

with tab1:
    channels = channel_db.get_all_channels()
    if channels:
        recent_channels = channels[:15]
        channel_list = []
        for i, channel in enumerate(recent_channels, 1):
            channel_name = channel.get("channel_name")
            if channel_name:
                channel_list.append(f"{i}. **{channel_name}**")
            else:
                # チャンネル名がない場合はチャンネルIDを表示
                channel_id = channel.get("channel_id", "不明")
                channel_list.append(f"{i}. **{channel_id}**")
        st.markdown("  \n".join(channel_list))
        if len(channels) > 15:
            st.info(f"他 {len(channels) - 15} 件のチャンネルが登録されています。")
    else:
        st.info("まだチャンネルが登録されていません")

with tab2:
    songs = song_db.get_all_songs(limit=5)
    if songs:
        for i, song in enumerate(songs, 1):
            status_emoji = {
                "pending": "⏳",
                "processed": "✅",
                "failed": "❌",
            }.get(song["status"], "❓")
            st.markdown(
                f"{i}. {status_emoji} [{song['url']}]({song['url']}) - 動画ID: {song['video_id']}"
            )
        if song_counts["total"] > 5:
            st.info(f"他 {song_counts['total'] - 5} 件の動画が登録されています。")
    else:
        st.info("まだ動画が登録されていません")

# フッター
st.markdown("---")
st.caption("💡 登録後のコンテンツは「チャンネル一覧」ページで確認・管理できます")
