"""
チャンネル一覧ページ

登録されているYouTubeチャンネルの一覧表示と管理
"""

import streamlit as st
import streamlit.components.v1 as components
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
        items_per_page = 10
        
        # セッションステートの初期化（検索条件が変わったらリセット）
        current_search_key = f"{search_query}_{sort_order}"
        if "last_search_key" not in st.session_state or st.session_state.last_search_key != current_search_key:
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
                                success, message = db.update_channel_name(
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
                        except:
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
                    if st.session_state.get(f"confirm_delete_{channel['id']}", False):
                        st.warning(f"本当に削除しますか？")
                        col_yes, col_no = st.columns(2)
                        with col_yes:
                            if st.button(
                                "削除",
                                key=f"confirm_yes_{channel['id']}",
                                type="primary",
                                use_container_width=True,
                            ):
                                success, message = db.delete_channel(channel["id"])
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
                                del st.session_state[f"confirm_delete_{channel['id']}"]
                                st.rerun()

                st.divider()

        # 無限スクロール: 自動読み込み
        if end_idx < len(filtered_channels):
            remaining = len(filtered_channels) - end_idx
            
            # ボタンを中央に配置
            cols = st.columns([1, 2, 1])
            with cols[1]:
                load_more_clicked = st.button(
                    f"📖 さらに{min(items_per_page, remaining)}件読み込む",
                    type="primary",
                    use_container_width=True,
                    key="load_more_auto"
                )
                
                if load_more_clicked:
                    st.session_state.items_to_show += items_per_page
                    st.rerun()
            
            # 自動読み込みトリガー用の不可視要素
            st.markdown('<div id="load-more-trigger" style="height: 1px;"></div>', unsafe_allow_html=True)
            
            # 自動クリック用のJavaScript
            # スクロールして要素が表示されたら自動的にボタンをクリック
            components.html(
                """
                <script>
                    let autoLoadTriggered = false;
                    
                    function autoClickLoadMore() {
                        if (autoLoadTriggered) return;
                        
                        try {
                            // 親ウィンドウのドキュメントにアクセス
                            const parentDoc = window.parent.document;
                            const trigger = parentDoc.getElementById('load-more-trigger');
                            
                            if (!trigger) {
                                return;
                            }
                            
                            // トリガー要素が画面内に表示されているかチェック
                            const rect = trigger.getBoundingClientRect();
                            const windowHeight = window.parent.innerHeight;
                            const isVisible = rect.top >= 0 && rect.top < windowHeight;
                            
                            if (isVisible) {
                                // "さらに読み込む"ボタンを探してクリック
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
                    
                    // 親ウィンドウのスクロールイベントを監視
                    try {
                        window.parent.addEventListener('scroll', autoClickLoadMore, { passive: true });
                    } catch (e) {
                        console.error('Failed to add scroll listener:', e);
                    }
                    
                    // 定期的にチェック（フォールバック）
                    setInterval(autoClickLoadMore, 500);
                    
                    // ページ読み込み後に初回チェック
                    setTimeout(autoClickLoadMore, 800);
                </script>
                """,
                height=0,
            )
            
            st.caption(f"📄 残り{remaining}件 - スクロールすると自動的に読み込まれます")
        else:
            st.success(f"✅ すべてのチャンネル ({len(filtered_channels)}件) を表示しました")

# エクスポート機能
st.markdown("---")
st.markdown("### 💾 データエクスポート")

col_export1, col_export2 = st.columns(2)

with col_export1:
    if st.button("📄 CSV形式でダウンロード", use_container_width=True):
        if channels:
            # DataFrameに変換
            df = pd.DataFrame(channels)
            csv = df.to_csv(index=False, encoding="utf-8-sig")

            st.download_button(
                label="⬇️ CSVファイルをダウンロード",
                data=csv,
                file_name=f"youtube_channels_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True,
            )
        else:
            st.warning("エクスポートするデータがありません")

with col_export2:
    if st.button("📋 URLリストをコピー", use_container_width=True):
        if channels:
            # URLのみを抽出してテキスト形式に
            url_list = "\n".join([ch["url"] for ch in channels])
            st.code(url_list, language="text")
            st.info("上記のテキストをコピーしてご利用ください")
        else:
            st.warning("コピーするデータがありません")

# フッター
st.markdown("---")
st.caption("💡 チャンネルの追加は「YouTubeチャンネル登録」ページから行えます")
