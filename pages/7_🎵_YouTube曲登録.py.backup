"""
YouTube曲登録ページ

YouTube動画のURLを入力してキューに登録する
（実際のダウンロード・DB登録は register_songs.py で行う）
"""

import streamlit as st
from core.song_queue_db import SongQueueDB


# ========== ページ設定 ==========

st.set_page_config(
    page_title="YouTube曲登録",
    page_icon="🎵",
    layout="wide",
)

st.title("🎵 YouTube曲登録")
st.markdown("---")


# ========== メイン処理 ==========

# データベース初期化
db = SongQueueDB()

# 現在の登録状況を表示
counts = db.get_counts()
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("合計", f"{counts['total']}件")
with col2:
    st.metric("未処理", f"{counts['pending']}件", help="ダウンロード・登録待ち")
with col3:
    st.metric("処理済み", f"{counts['processed']}件", help="DB登録完了")
with col4:
    st.metric("失敗", f"{counts['failed']}件", help="エラーが発生")

st.markdown("### YouTubeの動画URLを登録")

# URL入力欄
with st.form("youtube_song_registration_form"):
    url_input = st.text_area(
        "YouTube動画のURLを入力してください（改行区切りで複数URL可）",
        placeholder="https://www.youtube.com/watch?v=xxxxx\nhttps://music.youtube.com/watch?v=yyyyy\nhttps://youtu.be/zzzzz",
        help="YouTube Music、通常のYouTube、短縮URL（youtu.be）に対応しています。複数のURLを改行で区切って入力できます。",
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
                success, message, video_id = db.add_song(url)

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


# 登録済みリストの表示
st.markdown("---")
st.markdown("### 📋 登録済みリスト")

# フィルタ
status_filter = st.selectbox(
    "ステータスでフィルタ",
    ["すべて", "未処理", "処理済み", "失敗"],
    index=0,
)

songs = db.get_all_songs(limit=200)

# フィルタ適用
if status_filter == "未処理":
    songs = [s for s in songs if s["status"] == "pending"]
elif status_filter == "処理済み":
    songs = [s for s in songs if s["status"] == "processed"]
elif status_filter == "失敗":
    songs = [s for s in songs if s["status"] == "failed"]

if songs:
    # テーブル表示用にデータを整形
    display_data = []
    for song in songs:
        status_emoji = {
            "pending": "⏳ 未処理",
            "processed": "✅ 完了",
            "failed": "❌ 失敗",
        }.get(song["status"], song["status"])

        display_data.append(
            {
                "動画ID": song["video_id"],
                "ステータス": status_emoji,
                "登録日時": song["registered_at"][:19] if song["registered_at"] else "",
                "URL": song["url"],
            }
        )

    st.dataframe(display_data, use_container_width=True, hide_index=True)

    # 失敗した曲のリセットボタン
    if counts["failed"] > 0:
        if st.button("🔄 失敗した曲を未処理に戻す"):
            reset_count = db.reset_failed()
            st.success(f"{reset_count}件を未処理に戻しました")
            st.rerun()
else:
    st.info("登録された曲はありません")


# 使い方の説明
st.markdown("---")
st.markdown("### 📝 使い方")

with st.expander("対応するURL形式"):
    st.markdown(
        """
    以下のURL形式に対応しています：
    
    - ✅ `https://www.youtube.com/watch?v=xxxxx`
    - ✅ `https://music.youtube.com/watch?v=xxxxx`
    - ✅ `https://youtu.be/xxxxx`
    - ✅ 動画ID（11文字）のみ: `xxxxx`
    """
    )

with st.expander("処理の流れ"):
    st.markdown(
        """
    1. このページでYouTube動画のURLを登録（キューに追加）
    2. `register_songs.py` を実行してダウンロード＆DB登録
       ```
       uv run register_songs.py --parallel process
       ```
    3. 登録された楽曲は「曲調おすすめプレイリスト」や「個別曲検索」で利用可能
    """
    )

# フッター
st.markdown("---")
st.caption(
    "💡 登録後、`uv run register_songs.py --parallel process` を実行してDB登録を完了してください"
)
