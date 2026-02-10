"""
ユーザー設定ページ
"""

import streamlit as st

from core.user_db import get_user_alias, update_user_alias


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
st.markdown("### 🎵 YouTube Music 権限")

# アクセストークンの確認
access_token = st.user.get("access_token") if st.user else None

if access_token:
    st.success("✅ YouTube Music の権限が付与されています")
    st.info("プレイリストを自分のYouTube Musicアカウントに作成できます。")
else:
    st.warning("⚠️ YouTube Music の権限が不足しています")
    st.info(
        """
        **プレイリストを作成するには:**
        
        YouTube Music API の権限が必要です。一度ログアウトして、再度ログインしてください。
        
        **管理者の方へ:**
        `.streamlit/secrets.toml` に以下の設定が必要です：
        
        ```toml
        [auth]
        expose_tokens = ["access", "id"]
        
        [auth.google]
        client_kwargs = { scope = "openid profile email https://www.googleapis.com/auth/youtube" }
        ```
        
        また、Google Cloud Console で YouTube Data API v3 を有効化してください。
        """
    )

st.markdown("---")
st.markdown("### 💡 ヒント")
st.info(
    """
- 表示名を設定すると、プレイリスト履歴やコメントでメールアドレスの代わりに表示されます
- 表示名を空にすると、メールアドレスが表示されるようになります
- 表示名は後からいつでも変更できます
- YouTube Music の権限はログイン時に自動的に付与されます（管理者が設定済みの場合）
"""
)

