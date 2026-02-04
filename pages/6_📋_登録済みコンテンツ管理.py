"""
登録済みコンテンツ管理ページ

YouTubeチャンネルと動画キューの一覧表示と管理
"""

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from datetime import datetime
from core.channel_db import ChannelDB
from core.song_queue_db import SongQueueDB


# ========== ページ設定 ==========

st.set_page_config(
    page_title="登録済みコンテンツ管理",
    page_icon="📋",
    layout="wide",
)

st.title("📋 登録済みコンテンツ管理")
st.markdown("---")


# ========== メイン処理 ==========

# データベース初期化
channel_db = ChannelDB()
song_db = SongQueueDB()

# タブで切り替え
tab1, tab2 = st.tabs(["📺 チャンネル", "🎵 動画キュー"])

# ========== チャンネルタブ ==========
with tab1:
    # 全チャンネルを取得
    channels = channel_db.get_all_channels()

    if not channels:
        st.info("📭 まだチャンネルが登録されていません")
        st.markdown("「YouTube登録」ページからチャンネルを登録してください")
    else:
        # エクスポート機能
        st.markdown("### 💾 データエクスポート")

        col_export1, col_export2 = st.columns(2)

        with col_export1:
            if st.button("📄 CSV形式でダウンロード", use_container_width=True):
                df = pd.DataFrame(channels)
                csv = df.to_csv(index=False, encoding="utf-8-sig")

                st.download_button(
                    label="⬇️ CSVファイルをダウンロード",
                    data=csv,
                    file_name=f"youtube_channels_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True,
                )

        with col_export2:
            if st.button("📋 URLリストをコピー", use_container_width=True):
                url_list = "\n".join([ch["url"] for ch in channels])
                st.code(url_list, language="text")
                st.info("上記のテキストをコピーしてご利用ください")

        st.markdown("---")

        # 統計情報を表示
        st.markdown("### 📊 統計情報")
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("登録チャンネル数", f"{len(channels)}件")

        with col2:
            if channels:
                latest_date = channels[0]["registered_at"][:10]
                st.metric("最終登録日", latest_date)

        with col3:
            if channels:
                oldest_date = channels[-1]["registered_at"][:10]
                st.metric("最古の登録日", oldest_date)

        st.markdown("---")

        # フィルター・検索機能
        st.markdown("### 🔍 フィルター")
        col_search, col_sort = st.columns([2, 1])

        with col_search:
            search_query = st.text_input(
                "URL・チャンネル名で検索",
                placeholder="キーワードを入力...",
                label_visibility="collapsed",
            )

        with col_sort:
            sort_order = st.selectbox(
                "並び順", ["新しい順", "古い順"], label_visibility="collapsed"
            )

        # フィルタリング
        filtered_channels = channels
        if search_query:
            filtered_channels = [
                ch
                for ch in channels
                if search_query.lower() in ch["url"].lower()
                or (
                    ch.get("channel_name")
                    and search_query.lower() in ch["channel_name"].lower()
                )
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
            # 無限スクロール設定
            items_per_page = 20

            # セッションステートの初期化（検索条件が変わったらリセット）
            current_search_key = f"{search_query}_{sort_order}"
            if (
                "last_search_key" not in st.session_state
                or st.session_state.last_search_key != current_search_key
            ):
                st.session_state.items_to_show = items_per_page
                st.session_state.last_search_key = current_search_key

            # 表示範囲を計算
            end_idx = min(st.session_state.items_to_show, len(filtered_channels))
            page_channels = filtered_channels[0:end_idx]

            # チャンネルをカード形式で表示
            for i, channel in enumerate(page_channels, start=1):
                with st.container():
                    # カード風デザイン（レスポンシブ対応）
                    card_col1, card_col2 = st.columns([1, 3])

                    with card_col1:
                        # サムネイルを表示
                        thumbnail_url = channel.get("thumbnail_url")
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
                            f"</div>",
                            unsafe_allow_html=True,
                        )

                        # アーティスト名編集用のテキストボックス（デフォルトは非表示）
                        edit_key = f"edit_{channel['id']}"
                        if st.session_state.get(f"editing_{channel['id']}", False):
                            new_name = st.text_input(
                                "アーティスト名を編集",
                                value=channel.get("channel_name", ""),
                                key=edit_key,
                                label_visibility="collapsed",
                            )
                            col_save, col_cancel = st.columns(2)
                            with col_save:
                                if st.button(
                                    "保存",
                                    key=f"save_{channel['id']}",
                                    type="primary",
                                    use_container_width=True,
                                ):
                                    success, message = channel_db.update_channel_name(
                                        channel["id"], new_name
                                    )
                                    if success:
                                        st.success(message)
                                        del st.session_state[f"editing_{channel['id']}"]
                                        st.rerun()
                                    else:
                                        st.error(message)
                            with col_cancel:
                                if st.button(
                                    "キャンセル",
                                    key=f"cancel_edit_{channel['id']}",
                                    use_container_width=True,
                                ):
                                    del st.session_state[f"editing_{channel['id']}"]
                                    st.rerun()
                        else:
                            if st.button(
                                "✏️ アーティスト名を編集",
                                key=f"edit_btn_{channel['id']}",
                                type="secondary",
                            ):
                                st.session_state[f"editing_{channel['id']}"] = True
                                st.rerun()

                        # URL
                        st.markdown(
                            f"🔗 [{channel['url']}]({channel['url']})",
                            unsafe_allow_html=True,
                        )
                        # チャンネルIDと登録日時を横並び
                        info_col1, info_col2 = st.columns(2)
                        with info_col1:
                            channel_id = channel.get("channel_id", "N/A")
                            st.caption(f"📺 ID: `{channel_id}`")
                        with info_col2:
                            registered_time = channel["registered_at"]
                            try:
                                dt = datetime.fromisoformat(registered_time)
                                formatted_time = dt.strftime("%Y/%m/%d %H:%M")
                            except Exception:
                                formatted_time = registered_time[:16]
                            st.caption(f"📅 {formatted_time}")
                        # 削除ボタン
                        if st.button(
                            "🗑️ 削除",
                            key=f"delete_{channel['id']}",
                            type="secondary",
                            help="削除",
                        ):
                            st.session_state[f"confirm_delete_{channel['id']}"] = True
                        # 削除確認ダイアログ
                        if st.session_state.get(
                            f"confirm_delete_{channel['id']}", False
                        ):
                            st.warning("本当に削除しますか？")
                            col_yes, col_no = st.columns(2)
                            with col_yes:
                                if st.button(
                                    "削除",
                                    key=f"confirm_yes_{channel['id']}",
                                    type="primary",
                                    use_container_width=True,
                                ):
                                    success, message = channel_db.delete_channel(
                                        channel["id"]
                                    )
                                    if success:
                                        st.success(message)
                                        if (
                                            f"confirm_delete_{channel['id']}"
                                            in st.session_state
                                        ):
                                            del st.session_state[
                                                f"confirm_delete_{channel['id']}"
                                            ]
                                        st.rerun()
                                    else:
                                        st.error(message)
                            with col_no:
                                if st.button(
                                    "キャンセル",
                                    key=f"confirm_no_{channel['id']}",
                                    use_container_width=True,
                                ):
                                    del st.session_state[
                                        f"confirm_delete_{channel['id']}"
                                    ]
                                    st.rerun()

                    st.divider()

            # 無限スクロール: 自動読み込み
            if end_idx < len(filtered_channels):
                remaining = len(filtered_channels) - end_idx

                # ボタンを中央に配置
                cols = st.columns([1, 2, 1])
                with cols[1]:
                    if st.button(
                        f"📖 さらに{min(items_per_page, remaining)}件読み込む",
                        type="primary",
                        use_container_width=True,
                        key="load_more_channels",
                    ):
                        st.session_state.items_to_show += items_per_page
                        st.rerun()

                # 自動読み込みトリガー用の不可視要素
                st.markdown(
                    '<div id="load-more-trigger-channels" style="height: 1px;"></div>',
                    unsafe_allow_html=True,
                )

                # 自動クリック用のJavaScript（チャンネルタブ専用）
                components.html(
                    """
                    <script>
                        let autoLoadTriggered = false;
                        let scrollListener = null;
                        let checkInterval = null;
                        
                        function autoClickLoadMore() {
                            if (autoLoadTriggered) return;
                            
                            try {
                                const parentDoc = window.parent.document;
                                
                                // チャンネルタブ専用のトリガーがあるかチェック
                                const trigger = parentDoc.getElementById('load-more-trigger-channels');
                                if (!trigger) {
                                    return;
                                }
                                
                                // トリガー要素が実際に表示されているかチェック（タブが非表示の場合はスキップ）
                                const style = window.parent.getComputedStyle(trigger);
                                if (style.display === 'none' || style.visibility === 'hidden') {
                                    return;
                                }
                                
                                // トリガーの親要素がタブコンテンツで非表示になっていないかチェック
                                let parent = trigger.parentElement;
                                while (parent) {
                                    const parentStyle = window.parent.getComputedStyle(parent);
                                    if (parentStyle.display === 'none' || parentStyle.visibility === 'hidden') {
                                        return;
                                    }
                                    // Streamlitのタブコンテンツの親まで到達したら終了
                                    if (parent.getAttribute('role') === 'tabpanel') {
                                        const isHidden = parent.getAttribute('aria-hidden') === 'true';
                                        if (isHidden) {
                                            return;
                                        }
                                        break;
                                    }
                                    parent = parent.parentElement;
                                }
                                
                                const rect = trigger.getBoundingClientRect();
                                const windowHeight = window.parent.innerHeight;
                                const isVisible = rect.top >= 0 && rect.top < windowHeight;
                                
                                if (isVisible) {
                                    const buttons = parentDoc.querySelectorAll('button[kind="primary"]');
                                    for (let btn of buttons) {
                                        const text = btn.textContent || '';
                                        if (text.includes('さらに') && text.includes('件読み込む')) {
                                            autoLoadTriggered = true;
                                            btn.click();
                                            break;
                                        }
                                    }
                                }
                            } catch (e) {
                                console.error('Auto-load error:', e);
                            }
                        }
                        
                        function cleanup() {
                            if (scrollListener) {
                                try {
                                    window.parent.removeEventListener('scroll', scrollListener);
                                } catch (e) {}
                            }
                            if (checkInterval) {
                                clearInterval(checkInterval);
                            }
                        }
                        
                        // スクロールリスナーを追加
                        try {
                            scrollListener = autoClickLoadMore;
                            window.parent.addEventListener('scroll', scrollListener, { passive: true });
                        } catch (e) {
                            console.error('Failed to add scroll listener:', e);
                        }
                        
                        // 定期チェック（フォールバック）
                        checkInterval = setInterval(autoClickLoadMore, 500);
                        
                        // 初回チェック
                        setTimeout(autoClickLoadMore, 800);
                        
                        // タブが切り替わったら自動的にクリーンアップ
                        setTimeout(cleanup, 30000); // 30秒後にクリーンアップ
                    </script>
                    """,
                    height=0,
                )

                st.caption(
                    f"📄 残り{remaining}件 - スクロールすると自動的に読み込まれます"
                )
            else:
                st.success(
                    f"✅ すべてのチャンネル ({len(filtered_channels)}件) を表示しました"
                )


# ========== 動画キュータブ ==========
with tab2:
    # 統計情報を表示
    counts = song_db.get_counts()

    st.markdown("### 📊 統計情報")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("合計", f"{counts['total']}件")
    with col2:
        st.metric("未処理", f"{counts['pending']}件", help="ダウンロード・登録待ち")
    with col3:
        st.metric("処理済み", f"{counts['processed']}件", help="DB登録完了")
    with col4:
        st.metric("失敗", f"{counts['failed']}件", help="エラーが発生")

    st.markdown("---")

    # フィルター・検索機能
    st.markdown("### 🔍 フィルター")
    col_filter, col_search = st.columns([1, 2])

    with col_filter:
        status_filter = st.selectbox(
            "ステータスでフィルタ",
            ["すべて", "未処理", "処理済み", "失敗"],
            index=0,
        )

    with col_search:
        search_query_song = st.text_input(
            "動画ID・URLで検索",
            placeholder="キーワードを入力...",
            key="song_search",
        )

    # データを取得
    songs = song_db.get_all_songs(limit=1000)

    # フィルタ適用
    if status_filter == "未処理":
        songs = [s for s in songs if s["status"] == "pending"]
    elif status_filter == "処理済み":
        songs = [s for s in songs if s["status"] == "processed"]
    elif status_filter == "失敗":
        songs = [s for s in songs if s["status"] == "failed"]

    # 検索適用
    if search_query_song:
        songs = [
            s
            for s in songs
            if search_query_song.lower() in s["video_id"].lower()
            or search_query_song.lower() in s["url"].lower()
        ]

    st.markdown(f"**{len(songs)}件** の動画が見つかりました")
    st.markdown("---")

    # 動画一覧を表示
    st.markdown("### 🎵 動画キュー一覧")

    if not songs:
        st.info("動画が登録されていません")
    else:
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
                    "ステータス": status_emoji,
                    "タイトル": song.get("title", ""),
                    "アーティスト名": song.get("artist_name", ""),
                    "URL": song["url"],
                    "動画ID": song["video_id"],
                    "登録日時": (
                        song["registered_at"][:19] if song["registered_at"] else ""
                    ),
                }
            )

        st.dataframe(display_data, use_container_width=True, hide_index=True)

    # 一括操作
    st.markdown("---")
    st.markdown("### ⚙️ 一括操作")

    if counts["failed"] > 0:
        if st.button("🔄 失敗した曲を未処理に戻す", use_container_width=True):
            reset_count = song_db.reset_failed()
            st.success(f"{reset_count}件を未処理に戻しました")
            st.rerun()
    else:
        st.button(
            "🔄 失敗した曲を未処理に戻す", disabled=True, use_container_width=True
        )

    # 使い方の説明
    with st.expander("📝 動画キューの使い方"):
        st.markdown(
            """
        **処理の流れ**：
        1. 「YouTube登録」ページで動画URLを登録（キューに追加）
        2. `register_songs.py` を実行してダウンロード＆DB登録
           ```
           uv run register_songs.py --parallel process
           ```
        3. 登録された楽曲は「楽曲検索」で検索・再生可能になります
        
        **ステータスの意味**：
        - ⏳ 未処理: ダウンロード・登録待ち
        - ✅ 完了: DB登録完了
        - ❌ 失敗: エラーが発生（再試行可能）
        """
        )

# フッター
st.markdown("---")
st.caption("💡 新しいコンテンツの登録は「YouTube登録」ページから行えます")
