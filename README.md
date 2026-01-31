# Song Recommender

曲調が似ている楽曲をベクトルDBから検索し、類似度の高いものを出力するCLIアプリケーション。

> アーティストやジャンルではなく、**音声特徴量（曲調）** に基づいたレコメンドを行います。

## 概要

```
音楽ファイル → 音声特徴量抽出 → ベクトル化 → ベクトルDB登録
                                              ↓
検索クエリ楽曲 → 同様にベクトル化 → 類似ベクトル検索 → 結果出力
                                              ↓
                              YouTube Music プレイリスト自動作成
```

## 抽出する音声特徴量

| 特徴量 | 次元 | 意味 |
|--------|------|------|
| MFCC | 20 | 音色・質感（メル周波数ケプストラム係数） |
| MFCC Delta | 20 | 音色の時間変化 |
| Chroma | 12 | 和音・調性（12音階の分布） |
| Tonnetz | 6 | 和声的関係（コード進行） |
| Spectral Contrast | 7 | 音の谷と山（ジャンル識別） |
| Spectral Centroid | 1 | 音の明るさ |
| Spectral Rolloff | 1 | 高周波成分の割合 |
| Spectral Bandwidth | 1 | 音の広がり |
| Spectral Flatness | 1 | ノイズっぽさ（電子音 vs 生音） |
| Zero Crossing Rate | 1 | ノイジーさ・打楽器感 |
| RMS Energy | 1 | 音量レベル |
| Tempo (BPM) | 1 | 曲の速さ |

## 特徴量モード

用途に応じて3つのモードを選択可能：

| モード | 次元数 | 含まれる特徴量 | 用途 |
|--------|--------|---------------|------|
| **minimal** | 15 | Chroma, Centroid, RMS, Tempo | テンポ・明るさ重視 |
| **balanced** | 33 | ↑ + MFCC(10), Contrast, Bandwidth | 汎用的（推奨） |
| **full** | 72 | 全特徴量 | 細かい違いを見たい |

## 距離関数

| 距離関数 | 説明 | 推奨 |
|----------|------|------|
| **cosine** | ベクトルの向き（角度）で比較。音量差を吸収できる | ✅ |
| l2 | ユークリッド距離。絶対的な位置で比較 | |
| ip | 内積 | |

## 技術スタック

| 用途 | ライブラリ |
|------|-----------|
| 音声特徴量抽出 | librosa |
| ベクトルDB | ChromaDB（ローカル永続化） |
| YouTube Music連携 | ytmusicapi |
| 数値計算 | numpy |
| パッケージ管理 | uv |

## プロジェクト構成

```
song-recommender/
├── main.py                        # 連鎖検索・曲一覧表示CLI
├── register_songs.py              # 音声ファイルのベクトルDB登録
├── create_playlist_from_chain.py  # 連鎖検索→YouTube Musicプレイリスト作成
├── test_ytmusic.py                # YouTube Music API テストスクリプト
├── browser.json                   # YouTube Music認証ファイル
├── core/
│   ├── feature_extractor.py       # 音声特徴量抽出
│   ├── db_manager.py              # ベクトルDB操作
│   └── ytmusic_manager.py         # YouTube Music API操作
├── data/
│   ├── chroma_db_cos_minimal/     # minimal モードDB
│   ├── chroma_db_cos_balance/     # balanced モードDB
│   └── chroma_db_cos_full/        # full モードDB
├── .vscode/
│   └── tasks.json                 # VS Codeタスク設定
├── pyproject.toml
└── README.md
```

## 使い方

### インストール

```bash
uv sync
```

---

### 1. 楽曲の登録

音声ファイルをベクトルDBに登録します。

```bash
# 直列処理（デフォルト）
uv run register_songs.py

# ThreadPool並列処理
uv run register_songs.py --parallel thread

# ProcessPool並列処理（CPU効率◎、推奨）
uv run register_songs.py --parallel process
uv run register_songs.py -p process  # 短縮形
```

登録対象のディレクトリは `register_songs.py` 内の `SOUND_DIRS` で設定します。

---

### 2. 連鎖検索

指定した曲から類似曲を連鎖的に辿ります。

```bash
# キーワードで開始曲を検索して連鎖検索を実行
uv run main.py "フェスタ"

# 表示曲数を指定（デフォルト: 60曲）
uv run main.py "SOS" --count 30
uv run main.py "SOS" -n 30
```

複数の曲がヒットした場合は対話的に選択できます。

---

### 3. 曲の検索・一覧表示

キーワードで登録済みの曲を検索し、メタデータ付きで一覧表示します。

```bash
uv run main.py --list "キーワード"
uv run main.py -l "アイマス"
```

---

### 4. YouTube Music プレイリスト作成

連鎖検索の結果をYouTube Musicのプレイリストとして自動作成します。

```bash
# 基本的な使い方
uv run create_playlist_from_chain.py "検索キーワード"

# オプション指定
uv run create_playlist_from_chain.py "フェスタ" --count 30 --name "マイプレイリスト"
```

| オプション | 説明 | デフォルト |
|-----------|------|-----------|
| `keyword` | 開始曲の検索キーワード | （必須） |
| `--count`, `-n` | プレイリストに追加する曲数 | 30 |
| `--name` | プレイリスト名 | "曲調リコメンドプレイリスト" |

#### 処理フロー

1. ベクトルDBから開始曲の類似曲を連鎖的に探索
2. ファイル名から曲名を抽出して検索クエリを生成
3. YouTube Music APIで楽曲を検索
4. プレイリストを作成（既存があれば削除して再作成）
5. Descriptionに処理日と開始曲を記載

---

### 5. YouTube Music API テスト

```bash
# 接続テスト
uv run test_ytmusic.py --test

# プレイリスト一覧
uv run test_ytmusic.py --list

# 検索テスト
uv run test_ytmusic.py --search

# プレイリスト作成テスト
uv run test_ytmusic.py --create "テストプレイリスト"

# プレイリスト削除
uv run test_ytmusic.py --delete "PLAYLIST_ID"
```

---

## VS Code タスク

VS Codeのタスク機能（`Ctrl+Shift+B` または `Terminal > Run Task`）から各処理を実行できます。

| タスク名 | 説明 | 入力 |
|---------|------|------|
| **Register Songs to DB** | 音声ファイルをベクトルDBに登録 | 並列モード（none/thread/process） |
| **Run Chain Search** | 連鎖検索を実行 | 検索キーワード、表示曲数 |
| **List Songs by Keyword** | キーワードで曲を検索・一覧表示 | 検索キーワード |
| **Create Playlist from Chain Search** | 連鎖検索→YouTube Musicプレイリスト作成 | 検索キーワード、曲数、プレイリスト名 |
| **Test YouTube Music Connection** | YouTube Music APIの接続テスト | なし |

### タスクの実行方法

1. `Ctrl+Shift+P` でコマンドパレットを開く
2. `Tasks: Run Task` を選択
3. 実行したいタスクを選択
4. プロンプトに従って入力値を設定

---

## Pythonからの利用

```python
from core.db_manager import SongVectorDB
from core.feature_extractor import FeatureExtractor

# DB・抽出器の初期化
db = SongVectorDB(db_path="data/chroma_db_cos_balance", distance_fn="cosine")
extractor = FeatureExtractor(duration=90, mode="balanced")

# 楽曲を登録
embedding = extractor.extract_to_vector("song.wav")
db.add_song(song_id="song.wav", embedding=embedding, metadata={"filename": "song.wav"})

# 類似楽曲を検索
song = db.get_song("song.wav")
results = db.search_similar(query_embedding=song["embedding"], n_results=5)
```

---

## 開発フェーズ

- [x] **Phase 1**: librosa + ChromaDB で基本実装（MVP）
- [x] **Phase 2**: YouTube Music連携（プレイリスト自動作成）
- [x] **Phase 2.5**: CLI引数対応・VS Codeタスク統合
- [ ] **Phase 3**: 精度向上が必要な場合、CLAP / OpenL3 等の深層学習モデルを導入
