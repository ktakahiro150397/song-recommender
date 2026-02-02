"""
楽曲ファイルアップロードページ

複数の楽曲ファイルをサーバーにアップロードして保存
"""

import streamlit as st
from pathlib import Path
import os
import sys

# 親ディレクトリをパスに追加（config.py をインポート可能にする）
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import UPLOAD_DATA_DIR, SUPPORTED_AUDIO_FORMATS

# ========== 設定 ==========
DATA_DIR = UPLOAD_DATA_DIR
SUPPORTED_FORMATS = SUPPORTED_AUDIO_FORMATS

# ========== ページ設定 ==========
st.set_page_config(
    page_title="楽曲ファイルアップロード",
    page_icon="📤",
    layout="wide",
)

# ========== タイトル ==========
st.title("📤 楽曲ファイルアップロード")
st.write("楽曲ファイルをアップロードします。")

st.divider()

# ========== ユーティリティ関数 ==========


def get_existing_subdirs(base_dir: Path) -> list[str]:
    """upload/data/配下の既存サブディレクトリを取得（再帰的）"""
    if not base_dir.exists():
        return []
    
    subdirs = []
    
    # upload/data/配下のすべてのディレクトリを再帰的に探索
    for item in base_dir.rglob("*"):
        if item.is_dir():
            # upload/data/配下の相対パスを取得
            relative_path = item.relative_to(base_dir)
            # chroma_db で始まるディレクトリは除外
            if not str(relative_path).startswith("chroma_db"):
                subdirs.append(str(relative_path))
    
    return sorted(subdirs)


def save_uploaded_file(uploaded_file, target_dir: Path) -> bool:
    """アップロードされたファイルを指定ディレクトリに保存"""
    try:
        # ディレクトリが存在しない場合は作成
        target_dir.mkdir(parents=True, exist_ok=True)
        
        # ファイルを保存
        file_path = target_dir / uploaded_file.name
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        return True
    except Exception as e:
        st.error(f"ファイル保存エラー: {e}")
        return False


# ========== メイン処理 ==========

# ディレクトリ選択セクション
st.subheader("📁 保存先ディレクトリの設定")
st.text("アップロードする楽曲に最も適したディレクトリを選択してください。")

# 新規ディレクトリ作成モードの切り替え
create_new_dir = st.checkbox("新規ディレクトリを作成する", value=False)

if create_new_dir:
    # 新規ディレクトリ名を入力
    help_text="アーティスト名/グループ名/ブランド名を正しく指定してください。検索時に利用するので**非常に**重要です。既存ディレクトリがある場合は可能な限りそちらを選択してください。"
    new_dir_name = st.text_input(
        "新規ディレクトリ名",
        placeholder="例: shiny, gakumas, scsp",
        help=help_text
    )
    st.error(help_text)
    target_subdir = new_dir_name.strip() if new_dir_name else None
else:
    # 既存ディレクトリから選択
    existing_dirs = get_existing_subdirs(DATA_DIR)
    
    if existing_dirs:
        selected_dir = st.selectbox(
            "既存のディレクトリから選択",
            options=existing_dirs,
            help="upload/data/配下の既存ディレクトリ一覧"
        )
        target_subdir = selected_dir
    else:
        st.warning("upload/data/配下に既存のディレクトリが見つかりません。新規ディレクトリを作成してください。")
        target_subdir = None

# 保存先パスの表示
if target_subdir:
    target_path = DATA_DIR / target_subdir
    st.info(f"**保存先:** `{target_path}`")
else:
    st.warning("保存先ディレクトリを指定してください。")

st.divider()

# ファイルアップロードセクション
st.subheader("📂 ファイルアップロード")

uploaded_files = st.file_uploader(
    f"楽曲ファイルを選択（対応フォーマット: {', '.join(SUPPORTED_FORMATS)}）",
    type=[fmt.lstrip('.') for fmt in SUPPORTED_FORMATS],
    accept_multiple_files=True,
    help="複数のファイルを同時に選択できます。"
)

# アップロードされたファイルの一覧表示
if uploaded_files:
    st.write(f"**選択されたファイル数:** {len(uploaded_files)}")
    
    # ファイル名の一覧を表示
    with st.expander("ファイル一覧を表示", expanded=False):
        for i, file in enumerate(uploaded_files, 1):
            file_size_mb = file.size / (1024 * 1024)
            st.write(f"{i}. `{file.name}` ({file_size_mb:.2f} MB)")
    
    st.divider()
    
    # アップロードボタン
    if target_subdir:
        if st.button("🚀 アップロードを実行", type="primary", use_container_width=True):
            target_path = DATA_DIR / target_subdir
            
            # プログレスバー表示
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            success_count = 0
            failed_files = []
            
            for i, uploaded_file in enumerate(uploaded_files):
                status_text.text(f"アップロード中... ({i + 1}/{len(uploaded_files)}): {uploaded_file.name}")
                
                # ファイルを保存
                if save_uploaded_file(uploaded_file, target_path):
                    success_count += 1
                else:
                    failed_files.append(uploaded_file.name)
                
                # プログレスバー更新
                progress_bar.progress((i + 1) / len(uploaded_files))
            
            # 完了メッセージ
            status_text.empty()
            progress_bar.empty()
            
            if success_count == len(uploaded_files):
                st.success(f"✅ すべてのファイル（{success_count}件）をアップロードしました！")
            else:
                st.warning(f"⚠️ {success_count}/{len(uploaded_files)} 件のアップロードに成功しました。")
                if failed_files:
                    st.error("失敗したファイル:")
                    for filename in failed_files:
                        st.write(f"- {filename}")
            
            st.divider()
            
            # 次のステップの案内
            st.info(
                "📌 **次のステップ**\n\n"
                f"アップロードしたファイルをベクトルDBに登録するには、\n\n"
                "「🗄️ DBメンテナンス - 楽曲登録」ページで登録を実行してください。"
            )
    else:
        st.warning("保存先ディレクトリを指定してからアップロードボタンを押してください。")

else:
    st.info("アップロードするファイルを選択してください。")

# ========== フッター ==========
st.divider()
st.caption("💡 アップロード後、曲をベクトルDBに登録するには「🗄️ DBメンテナンス - 楽曲登録」ページを使用してください。")
