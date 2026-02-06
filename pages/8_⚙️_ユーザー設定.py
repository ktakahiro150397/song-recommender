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
                st.success(f"表示名を「{normalized_alias}」に更新しました")
            else:
                st.success("表示名をクリアしました（メールアドレスが表示されます）")
            st.rerun()
        else:
            st.error("表示名の更新に失敗しました")

st.markdown("---")
st.markdown("### 💡 ヒント")
st.info(
    """
- 表示名を設定すると、プレイリスト履歴やコメントでメールアドレスの代わりに表示されます
- 表示名を空にすると、メールアドレスが表示されるようになります
- 表示名は後からいつでも変更できます
"""
)
