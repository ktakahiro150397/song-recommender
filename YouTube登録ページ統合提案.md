# YouTube登録ページ統合提案書

## 📋 目次

1. [問題の概要](#問題の概要)
2. [現状分析](#現状分析)
3. [ユーザー視点での問題点](#ユーザー視点での問題点)
4. [改善提案](#改善提案)
5. [技術的アプローチ](#技術的アプローチ)
6. [ページ遷移フロー](#ページ遷移フロー)
7. [実装詳細（PR内容）](#実装詳細pr内容)
8. [期待される効果](#期待される効果)

---

## 問題の概要

現在、YouTubeチャンネル登録とYouTube曲登録が別々のページに分かれており、ユーザーにとって登録ページの場所が分かりづらい状態です。技術的には異なる機能（チャンネルDBと曲キューDB）であっても、ユーザーの認知モデルでは「YouTubeのURLを登録する」という同一の概念として捉えられています。

### Issue参照

- **Issue**: チャンネル登録と曲登録について
- **要望**: 同一ページでチャンネルと曲の両方を登録できるようにする
- **判定方法**: URL入力を一つの窓にして、裏側でチャンネルか曲かを自動判別する

---

## 現状分析

### 現在のページ構成

| ページ番号 | ページ名 | ファイル名 | 主な機能 |
|-----------|---------|-----------|---------|
| 5 | 📺 YouTubeチャンネル登録 | `5_📺_YouTubeチャンネル登録.py` | チャンネルURL（`/channel/UCxxxxx`形式）を登録 |
| 7 | 🎵 YouTube曲登録 | `7_🎵_YouTube曲登録.py` | 動画URL（`watch?v=xxxxx`形式）をキューに登録 |

### データベース構造

#### 1. チャンネルDB (`core/channel_db.py`)
- **テーブル**: `YouTubeChannel`
- **対象URL形式**:
  - `https://music.youtube.com/channel/UCxxxxx`
  - `https://www.youtube.com/channel/UCxxxxx`
- **主な機能**:
  - チャンネルIDの抽出（`extract_channel_id`メソッド）
  - サムネイルとチャンネル名の自動取得（YTMusic API）
  - 重複チェック
  - 登録カウント管理

#### 2. 曲キューDB (`core/song_queue_db.py`)
- **テーブル**: `SongQueue`
- **対象URL形式**:
  - `https://www.youtube.com/watch?v=xxxxx`
  - `https://music.youtube.com/watch?v=xxxxx`
  - `https://youtu.be/xxxxx`
  - 動画ID（11文字）のみ
- **主な機能**:
  - 動画IDの抽出（`extract_video_id`メソッド）
  - ステータス管理（pending/processed/failed）
  - キュー管理

### URL判別ロジック

両DBには既にURL解析機能が実装されています：

**チャンネル判定条件**:
```python
# /channel/UCxxxxx 形式を検出
if path.startswith("/channel/UC"):
    return "channel"
```

**動画判定条件**:
```python
# watch?v=xxxxx, youtu.be/xxxxx, 動画ID直接入力を検出
patterns = [
    r"(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/|music\.youtube\.com\/watch\?v=)([a-zA-Z0-9_-]{11})",
    r"^([a-zA-Z0-9_-]{11})$",
]
```

---

## ユーザー視点での問題点

### 現在のユーザーフロー（問題あり）

```
ユーザー: YouTubeのURLを登録したい
    ↓
問題1: どのページで登録すればいいの？
    ↓
左サイドバーを確認
    ├─ 5_📺_YouTubeチャンネル登録
    └─ 7_🎵_YouTube曲登録
    ↓
問題2: 自分のURLはチャンネル？曲？
    ↓
試行錯誤してページを選択
    ↓
問題3: 間違ったページで登録失敗
    ↓
もう一方のページに移動してやり直し
```

### ユーザーの認知モデル

- ✅ 「YouTubeのURLを登録する」という**単一の概念**
- ❌ 「チャンネルと曲を別々に登録する」という認識は薄い
- ❌ URL形式の違い（`/channel/UC` vs `watch?v=`）を意識していない

---

## 改善提案

### コンセプト

**「1つの入力窓で、すべてのYouTube URLを受け付ける」**

ユーザーはURL形式を意識せず、どんなYouTube URLでも同じ場所に入力できます。システムが自動的にチャンネルと動画を判別し、適切なDBに登録します。

### 新しいページ構成

| ページ番号 | ページ名 | ファイル名 | 主な機能 |
|-----------|---------|-----------|---------|
| 5 | 📺 YouTube登録（統合） | `5_📺_YouTube登録.py` | **チャンネルと曲の両方に対応した統合ページ** |
| 6 | 📋 登録済みコンテンツ一覧 | `6_📋_登録済みコンテンツ一覧.py` | チャンネルと曲の一覧を統合表示 |

### 削除されるページ

- ~~`7_🎵_YouTube曲登録.py`~~ → 統合ページに機能移行

---

## 技術的アプローチ

### 1. URL自動判別ロジック

```python
def detect_url_type(url: str) -> tuple[str, str]:
    """
    URLの種類を自動判別する
    
    Returns:
        (種類, エラーメッセージ)
        種類: "channel", "video", "unknown"
    """
    from urllib.parse import urlparse
    
    # 正規化
    url = url.strip()
    
    try:
        parsed = urlparse(url)
        path = parsed.path.rstrip("/")
        
        # チャンネルURL判定
        if "/channel/UC" in path:
            return "channel", ""
        
        # 動画URL判定
        video_patterns = [
            r"watch\?v=([a-zA-Z0-9_-]{11})",  # YouTube標準
            r"youtu\.be/([a-zA-Z0-9_-]{11})",  # 短縮URL
        ]
        
        import re
        for pattern in video_patterns:
            if re.search(pattern, url):
                return "video", ""
        
        # 動画ID直接入力（11文字）
        if re.match(r"^[a-zA-Z0-9_-]{11}$", url):
            return "video", ""
        
        return "unknown", "未対応のURL形式です"
        
    except Exception as e:
        return "unknown", f"URL解析エラー: {str(e)}"
```

### 2. 統合登録処理

```python
def register_youtube_url(url: str, ytmusic=None) -> tuple[bool, str, str]:
    """
    URLを自動判別して適切なDBに登録
    
    Returns:
        (成功/失敗, メッセージ, 種類)
    """
    url_type, error_msg = detect_url_type(url)
    
    if url_type == "unknown":
        return False, error_msg, "unknown"
    
    if url_type == "channel":
        channel_db = ChannelDB()
        success, message, thumbnail = channel_db.add_channel(url, ytmusic=ytmusic)
        return success, message, "channel"
    
    elif url_type == "video":
        song_db = SongQueueDB()
        success, message, video_id = song_db.add_song(url)
        return success, message, "video"
    
    return False, "不明なエラー", "unknown"
```

### 3. UIデザイン

#### 入力エリア
```
┌─────────────────────────────────────────────────┐
│ 📺 YouTube登録（チャンネル / 曲）                    │
├─────────────────────────────────────────────────┤
│                                                 │
│ [入力欄]                                         │
│  YouTubeのURLを入力してください                    │
│  （改行区切りで複数URL可）                         │
│                                                 │
│  対応形式:                                       │
│  ✅ チャンネル: /channel/UCxxxxx                 │
│  ✅ 動画: watch?v=xxxxx, youtu.be/xxxxx          │
│                                                 │
│ [🔖 登録する]                                    │
└─────────────────────────────────────────────────┘
```

#### 登録結果表示
```
┌─────────────────────────────────────────────────┐
│ 📊 登録結果                                      │
├─────────────────────────────────────────────────┤
│ 合計: 5件                                        │
│ チャンネル: 2件 (成功: 2, 失敗: 0)                │
│ 動画: 3件 (成功: 2, 失敗: 1)                      │
├─────────────────────────────────────────────────┤
│ 📋 詳細                                          │
│ ✅ [チャンネル] https://...UCxxxxx               │
│    → チャンネル「アーティスト名」を登録しました      │
│                                                 │
│ ✅ [動画] https://...watch?v=yyyyy               │
│    → キューに登録しました: yyyyy                  │
│                                                 │
│ ❌ [動画] https://...watch?v=zzzzz               │
│    → 既に登録済みです: zzzzz                      │
└─────────────────────────────────────────────────┘
```

---

## ページ遷移フロー

### 改善前（現状）

```
[トップページ]
    │
    ├─ [1_🎵_楽曲検索]
    ├─ [2_📤_楽曲ファイルアップロード]
    ├─ [3_🗄️_DBメンテナンス]
    ├─ [4_🗄️_DBメンテナンス_楽曲登録]
    ├─ [5_📺_YouTubeチャンネル登録] ← 別ページ
    ├─ [6_📋_チャンネル一覧]
    └─ [7_🎵_YouTube曲登録] ← 別ページ
```

### 改善後（提案）

```
[トップページ]
    │
    ├─ [1_🎵_楽曲検索]
    ├─ [2_📤_楽曲ファイルアップロード]
    ├─ [3_🗄️_DBメンテナンス]
    ├─ [4_🗄️_DBメンテナンス_楽曲登録]
    ├─ [5_📺_YouTube登録] ← 統合ページ（チャンネル+曲）
    └─ [6_📋_登録済みコンテンツ一覧] ← チャンネル一覧 + 曲一覧
```

### ユーザー操作フロー（改善後）

```
[トップページ]
    │
    ↓
[5_📺_YouTube登録]
    │
    ├─ ユーザー: YouTubeのURLを入力（形式は気にしない）
    │
    ├─ システム: 自動判別
    │   ├─ チャンネル → ChannelDBに登録
    │   └─ 動画 → SongQueueDBに登録
    │
    └─ 結果表示
        ├─ ✅ チャンネル「XXX」を登録しました
        └─ ✅ 動画「YYY」をキューに登録しました
```

---

## 実装詳細（PR内容）

### Phase 1: コアモジュール実装

#### 1. 新規ファイル: `core/youtube_url_detector.py`

```python
"""
YouTube URLの種類を自動判別するモジュール
"""

import re
from urllib.parse import urlparse
from typing import Literal, Tuple


URLType = Literal["channel", "video", "unknown"]


class YouTubeURLDetector:
    """YouTube URLの種類を自動判別するクラス"""
    
    # チャンネルURL判定パターン
    CHANNEL_PATTERNS = [
        r"/channel/UC[a-zA-Z0-9_-]+",
    ]
    
    # 動画URL判定パターン
    VIDEO_PATTERNS = [
        r"youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})",
        r"music\.youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})",
        r"youtu\.be/([a-zA-Z0-9_-]{11})",
        r"youtube\.com/embed/([a-zA-Z0-9_-]{11})",
    ]
    
    @classmethod
    def detect(cls, url: str) -> Tuple[URLType, str]:
        """
        URLの種類を判別
        
        Args:
            url: 判別対象のURL
            
        Returns:
            (URLタイプ, エラーメッセージ)
        """
        url = url.strip()
        
        if not url:
            return "unknown", "URLが入力されていません"
        
        try:
            parsed = urlparse(url)
            
            # YouTubeドメインチェック
            valid_domains = [
                "www.youtube.com",
                "youtube.com",
                "m.youtube.com",
                "music.youtube.com",
                "youtu.be",
            ]
            
            # ドメインチェック（動画ID直接入力の場合はスキップ）
            if parsed.netloc and parsed.netloc not in valid_domains:
                return "unknown", f"YouTubeのURLを入力してください"
            
            # チャンネル判定
            for pattern in cls.CHANNEL_PATTERNS:
                if re.search(pattern, url):
                    return "channel", ""
            
            # 動画判定
            for pattern in cls.VIDEO_PATTERNS:
                if re.search(pattern, url):
                    return "video", ""
            
            # 動画ID直接入力（11文字）
            if re.match(r"^[a-zA-Z0-9_-]{11}$", url):
                return "video", ""
            
            return "unknown", "未対応のURL形式です。チャンネルURL（/channel/UC...）または動画URL（watch?v=...）を入力してください"
            
        except Exception as e:
            return "unknown", f"URL解析エラー: {str(e)}"
```

#### 2. 新規ファイル: `core/youtube_registration.py`

```python
"""
YouTube URL統合登録モジュール
チャンネルと動画の両方に対応
"""

from typing import Tuple, Optional
from core.youtube_url_detector import YouTubeURLDetector
from core.channel_db import ChannelDB
from core.song_queue_db import SongQueueDB


class YouTubeRegistration:
    """YouTube URLの統合登録クラス"""
    
    def __init__(self):
        """初期化"""
        self.channel_db = ChannelDB()
        self.song_db = SongQueueDB()
        self.detector = YouTubeURLDetector()
    
    def register_url(
        self, 
        url: str, 
        ytmusic=None
    ) -> Tuple[bool, str, str]:
        """
        URLを自動判別して登録
        
        Args:
            url: YouTubeのURL
            ytmusic: YTMusicインスタンス（チャンネル登録時のサムネイル取得用）
            
        Returns:
            (成功/失敗, メッセージ, URLタイプ)
        """
        # URLタイプを判別
        url_type, error_msg = self.detector.detect(url)
        
        if url_type == "unknown":
            return False, error_msg, "unknown"
        
        # チャンネル登録
        if url_type == "channel":
            success, message, thumbnail = self.channel_db.add_channel(
                url, ytmusic=ytmusic
            )
            return success, message, "channel"
        
        # 動画登録
        elif url_type == "video":
            success, message, video_id = self.song_db.add_song(url)
            return success, message, "video"
        
        return False, "不明なエラーが発生しました", "unknown"
    
    def register_urls_batch(
        self,
        urls: list[str],
        ytmusic=None,
        progress_callback=None
    ) -> dict:
        """
        複数URLを一括登録
        
        Args:
            urls: URLリスト
            ytmusic: YTMusicインスタンス
            progress_callback: 進捗コールバック関数 (current, total, url)
            
        Returns:
            登録結果の辞書
        """
        results = {
            "total": len(urls),
            "channel_success": 0,
            "channel_failed": 0,
            "video_success": 0,
            "video_failed": 0,
            "unknown": 0,
            "details": []
        }
        
        for idx, url in enumerate(urls, 1):
            # 進捗コールバック
            if progress_callback:
                progress_callback(idx, len(urls), url)
            
            # 登録実行
            success, message, url_type = self.register_url(url, ytmusic=ytmusic)
            
            # 結果を集計
            if url_type == "channel":
                if success:
                    results["channel_success"] += 1
                else:
                    results["channel_failed"] += 1
            elif url_type == "video":
                if success:
                    results["video_success"] += 1
                else:
                    results["video_failed"] += 1
            else:
                results["unknown"] += 1
            
            # 詳細を追加
            results["details"].append({
                "url": url,
                "success": success,
                "message": message,
                "type": url_type
            })
        
        return results
```

### Phase 2: Streamlitページ実装

#### 3. 新規ファイル: `pages/5_📺_YouTube登録.py`

```python
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

st.title("📺 YouTube登録（チャンネル / 曲）")
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
    st.metric("登録曲数（キュー）", f"{song_counts['total']}件", 
              help=f"未処理: {song_counts['pending']}件 / 処理済み: {song_counts['processed']}件")

st.markdown("### YouTubeのURLを登録")

# URL入力欄
with st.form("youtube_registration_form"):
    url_input = st.text_area(
        "YouTubeのURLを入力してください（改行区切りで複数URL可）",
        placeholder="""https://music.youtube.com/channel/UCxxxxxxxxxxxxx
https://www.youtube.com/watch?v=xxxxx
https://youtu.be/yyyyy
https://music.youtube.com/channel/UCyyyyyyyyyyyyyy""",
        help="""対応形式:
✅ チャンネル: /channel/UCxxxxx
✅ 動画: watch?v=xxxxx, youtu.be/xxxxx
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
                url_list,
                ytmusic=ytmusic,
                progress_callback=progress_callback
            )
            
            # プログレスバーをクリア
            progress_bar.empty()
            status_text.empty()

            # 結果のサマリーを表示
            st.markdown("### 📊 登録結果")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("合計", f"{results['total']}件")
            with col2:
                channel_total = results['channel_success'] + results['channel_failed']
                st.metric(
                    "チャンネル",
                    f"{channel_total}件",
                    help=f"成功: {results['channel_success']}件 / 失敗: {results['channel_failed']}件"
                )
            with col3:
                video_total = results['video_success'] + results['video_failed']
                st.metric(
                    "動画",
                    f"{video_total}件",
                    help=f"成功: {results['video_success']}件 / 失敗: {results['video_failed']}件"
                )

            # 詳細結果を表示
            st.markdown("### 📋 詳細")
            for detail in results['details']:
                type_emoji = {
                    "channel": "📺 チャンネル",
                    "video": "🎵 動画",
                    "unknown": "❓ 不明"
                }.get(detail['type'], "❓")
                
                if detail['success']:
                    st.success(
                        f"✅ [{type_emoji}] {detail['url']}: {detail['message']}"
                    )
                else:
                    st.error(
                        f"❌ [{type_emoji}] {detail['url']}: {detail['message']}"
                    )

            # 成功が1件以上あれば画面をリロード
            if results['channel_success'] > 0 or results['video_success'] > 0:
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
    
    **混在入力OK**: チャンネルと動画を混ぜて入力しても自動判別します！
    """
    )

with st.expander("登録後の処理フロー"):
    st.markdown(
        """
    **チャンネル登録の場合**：
    1. チャンネル情報がDBに保存されます
    2. サムネイルとチャンネル名が自動取得されます
    3. 「登録済みコンテンツ一覧」ページで確認・管理できます
    
    **動画登録の場合**：
    1. 動画URLがキューに追加されます
    2. `uv run register_songs.py --parallel process` を実行してダウンロード＆DB登録
    3. 登録後は「楽曲検索」で検索・再生可能になります
    """
    )

with st.expander("複数URL一括登録のコツ"):
    st.markdown(
        """
    - 1行に1つのURLを入力してください
    - チャンネルと動画を混ぜて入力してもOK
    - 重複したURLは自動的にスキップされます
    - 無効なURL形式はエラーとして報告されます
    """
    )

# 最近登録されたコンテンツを表示
st.markdown("---")
st.markdown("### 📋 最近登録されたコンテンツ")

tab1, tab2 = st.tabs(["📺 チャンネル", "🎵 動画（キュー）"])

with tab1:
    channels = channel_db.get_all_channels()
    if channels:
        recent_channels = channels[:5]
        for i, channel in enumerate(recent_channels, 1):
            channel_name = channel.get("channel_name")
            if channel_name:
                st.markdown(
                    f"{i}. **{channel_name}** - [{channel['url']}]({channel['url']})"
                )
            else:
                st.markdown(f"{i}. [{channel['url']}]({channel['url']})")
        if len(channels) > 5:
            st.info(
                f"他 {len(channels) - 5} 件のチャンネルが登録されています。"
            )
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
        if song_counts['total'] > 5:
            st.info(
                f"他 {song_counts['total'] - 5} 件の動画が登録されています。"
            )
    else:
        st.info("まだ動画が登録されていません")

# フッター
st.markdown("---")
st.caption("💡 登録後のコンテンツは「登録済みコンテンツ一覧」ページで確認・管理できます")
```

### Phase 3: 既存ページの更新

#### 4. ファイル名変更: `pages/6_📋_チャンネル一覧.py` → `pages/6_📋_登録済みコンテンツ一覧.py`

既存のチャンネル一覧ページに動画キュー情報も表示するように拡張。

#### 5. ファイル削除

- `pages/5_📺_YouTubeチャンネル登録.py` → 新しい統合ページに置き換え
- `pages/7_🎵_YouTube曲登録.py` → 新しい統合ページに置き換え

### Phase 4: テストとドキュメント

#### 6. テストケース追加

簡易的なテストケースを作成：

```python
# test_youtube_integration.py
from core.youtube_url_detector import YouTubeURLDetector

def test_channel_detection():
    detector = YouTubeURLDetector()
    
    # チャンネルURL
    url_type, _ = detector.detect("https://music.youtube.com/channel/UCxxxxx")
    assert url_type == "channel"
    
    url_type, _ = detector.detect("https://www.youtube.com/channel/UCxxxxx")
    assert url_type == "channel"

def test_video_detection():
    detector = YouTubeURLDetector()
    
    # 動画URL
    url_type, _ = detector.detect("https://www.youtube.com/watch?v=xxxxx123456")
    assert url_type == "video"
    
    url_type, _ = detector.detect("https://youtu.be/xxxxx123456")
    assert url_type == "video"
    
    # 動画ID直接
    url_type, _ = detector.detect("xxxxx123456")
    assert url_type == "video"

def test_invalid_url():
    detector = YouTubeURLDetector()
    
    url_type, error = detector.detect("https://example.com/invalid")
    assert url_type == "unknown"
    assert "YouTube" in error
```

#### 7. README更新

```markdown
## YouTubeコンテンツの登録

### 統合登録ページ（推奨）

**ページ**: 📺 YouTube登録

チャンネルと動画の両方をサポートした統合登録ページです。
URL形式を気にせず、どんなYouTube URLでも同じ場所に入力できます。

**対応形式**:
- チャンネル: `https://music.youtube.com/channel/UCxxxxx`
- 動画: `https://www.youtube.com/watch?v=xxxxx`
- 短縮URL: `https://youtu.be/xxxxx`

システムが自動的にURLの種類を判別し、適切なDBに登録します。
```

---

## 期待される効果

### ユーザーエクスペリエンス

1. **認知負荷の軽減**
   - ページ選択で迷わなくなる
   - URL形式を意識する必要がなくなる
   - 登録失敗によるストレス軽減

2. **操作の簡素化**
   - 1ページで完結
   - ページ移動の手間削減
   - 混在入力が可能

3. **発見性の向上**
   - 「YouTube登録」という明確な名称
   - 機能が探しやすい

### システム側のメリット

1. **コード再利用**
   - 既存のURL判別ロジックを活用
   - DBアクセス層はそのまま使用

2. **拡張性**
   - 将来的に他のURL形式（プレイリストなど）にも対応しやすい
   - 統合ポイントが明確

3. **メンテナンス性**
   - 登録UIが1箇所に集約
   - バグ修正や機能追加が効率的

### データ整合性

- 既存のDBスキーマは変更なし
- データ移行不要
- 後方互換性を維持

---

## マイグレーションプラン

### ステップ1: 新機能追加（影響範囲：なし）

- `core/youtube_url_detector.py` 追加
- `core/youtube_registration.py` 追加

### ステップ2: 新ページ作成（影響範囲：最小）

- `pages/5_📺_YouTube登録.py` 作成（旧ページは残す）
- 新旧ページが一時的に共存

### ステップ3: 動作確認

- 各種URL形式での登録テスト
- DB登録の確認
- エラーハンドリングの確認

### ステップ4: 旧ページ削除（影響範囲：中）

- `pages/5_📺_YouTubeチャンネル登録.py` 削除
- `pages/7_🎵_YouTube曲登録.py` 削除
- ページ番号の再調整

### ステップ5: ドキュメント更新

- README.md 更新
- ユーザーガイド追加

---

## リスク分析

| リスク | 影響度 | 対策 |
|--------|--------|------|
| URL判別ロジックのバグ | 中 | 既存の実装を流用、十分なテスト |
| ユーザーの混乱 | 低 | 明確なUI、説明文の充実 |
| データ不整合 | 低 | 既存DBスキーマを変更しない |
| パフォーマンス低下 | 低 | 既存ロジックと同等の処理 |

---

## 結論

本提案により、ユーザーエクスペリエンスが大幅に向上し、システムの保守性も改善されます。
既存の実装を最大限活用しつつ、最小限の変更で目標を達成できる現実的なアプローチです。

**推奨**: 段階的な実装により、リスクを最小化しながら確実に移行を進めることができます。
