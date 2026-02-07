"""
ユーザー設定ページ
"""

import streamlit as st
import json

from core.user_db import get_user_alias, update_user_alias
from core.user_ytmusic_auth import (
    has_user_oauth,
    get_user_oauth,
    save_user_oauth,
    delete_user_oauth,
)


st.set_page_config(
    page_title="ユーザー設定",
    page_icon="⚙️",
    layout="wide",
)

alias_notice = st.session_state.pop("alias_notice", "")
if alias_notice:
    st.toast(alias_notice)

st.title("⚙️ ユーザー設定")
st.markdown("---")

user_sub = getattr(st.user, "sub", "")
user_email = getattr(st.user, "email", "")

if not user_sub:
    st.error("ログインユーザー情報が取得できません")
    st.stop()

st.markdown("### 👤 ユーザー情報")

# 現在のメールアドレスを表示
st.text_input(
    "メールアドレス",
    value=user_email,
    disabled=True,
    help="メールアドレスは変更できません",
)

# エイリアスの取得と表示
current_alias = get_user_alias(user_sub)

st.markdown("### ✏️ 表示名の変更")
st.markdown(
    "プレイリストやコメントで表示される名前を設定できます。設定しない場合はメールアドレスが表示されます。"
)

with st.form(key="alias_form"):
    new_alias = st.text_input(
        "表示名",
        value=current_alias,
        max_chars=100,
        placeholder="表示名を入力してください（最大100文字）",
        help="プレイリスト履歴やコメントで表示される名前です",
    )

    col1, col2 = st.columns([1, 5])
    with col1:
        submitted = st.form_submit_button("保存", type="primary", use_container_width=True)
    with col2:
        st.caption("※ 表示名は100文字以内で入力してください")

if submitted:
    normalized_alias = (new_alias or "").strip()

    if len(normalized_alias) > 100:
        st.error("表示名は100文字以内で入力してください")
    else:
        if update_user_alias(user_sub, normalized_alias):
            if normalized_alias:
                st.session_state["alias_notice"] = (
                    f"表示名を「{normalized_alias}」に更新しました"
                )
            else:
                st.session_state["alias_notice"] = (
                    "表示名をクリアしました（メールアドレスが表示されます）"
                )
            st.rerun()
        else:
            st.error("表示名の更新に失敗しました")

st.markdown("---")

# YouTube Music 認証セクション
st.markdown("### 🎵 YouTube Music 認証")
st.markdown(
    "プレイリストを自分のYouTube Musicアカウントに作成するには、YouTube Music APIの認証が必要です。"
)

# 認証状態を確認
auth_status = has_user_oauth(user_sub)

if auth_status:
    st.success("✅ YouTube Music 認証済み")
    st.info("あなたのYouTube Musicアカウントでプレイリストを作成できます。")

    if st.button("🗑️ 認証を解除", type="secondary"):
        if delete_user_oauth(user_sub):
            st.success("認証を解除しました")
            st.rerun()
        else:
            st.error("認証の解除に失敗しました")
else:
    st.warning("⚠️ YouTube Music 認証が未設定です")
    st.info(
        """
        **認証を設定するには:**
        
        1. YouTube Music認証ファイル（oauth.json）を取得してください
        2. 下記のファイルアップロードエリアにアップロードしてください
        
        詳しい手順は [YouTube Music OAuth 設定ガイド](https://github.com/ktakahiro150397/song-recommender/blob/main/YOUTUBE_OAUTH_SETUP.md) を参照してください。
        """
    )

    uploaded_file = st.file_uploader(
        "YouTube Music 認証ファイル (oauth.json)",
        type=["json"],
        help="ytmusicapiで生成したoauth.jsonファイルをアップロードしてください",
    )

    if uploaded_file is not None:
        try:
            # JSONファイルを読み込み
            oauth_data = json.load(uploaded_file)

            # 必要なキーが含まれているか確認
            required_keys = ["access_token", "refresh_token", "token_type"]
            if not all(key in oauth_data for key in required_keys):
                st.error(
                    "❌ 無効なOAuthファイルです。必要なキー（access_token, refresh_token, token_type）が含まれていません。"
                )
            else:
                # OAuth情報を保存
                oauth_json_str = json.dumps(oauth_data)
                if save_user_oauth(user_sub, oauth_json_str):
                    st.success("✅ YouTube Music 認証を設定しました")
                    st.balloons()
                    st.rerun()
                else:
                    st.error("❌ 認証の保存に失敗しました")
        except json.JSONDecodeError:
            st.error("❌ JSONファイルの形式が正しくありません")
        except Exception as e:
            st.error(f"❌ エラーが発生しました: {str(e)}")

st.markdown("---")
st.markdown("### 💡 ヒント")
st.info(
    """
- 表示名を設定すると、プレイリスト履歴やコメントでメールアドレスの代わりに表示されます
- 表示名を空にすると、メールアドレスが表示されるようになります
- 表示名は後からいつでも変更できます
- YouTube Music 認証を設定すると、プレイリストがあなたのアカウントに作成されます
"""
)
