# Song Recommender

曲調が似ている楽曲をベクトルDBから検索し、類似度の高いものを出力するCLIアプリケーション。

> アーティストやジャンルではなく、**音声特徴量（曲調）** に基づいたレコメンドを行います。

## 概要

```
音楽ファイル → 音声特徴量抽出 → ベクトル化 → ベクトルDB登録
                                              ↓
検索クエリ楽曲 → 同様にベクトル化 → 類似ベクトル検索 → 結果出力
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
| 数値計算 | numpy |

## プロジェクト構成

```
song-recommender/
├── main.py                        # 楽曲登録・連鎖検索の実行
├── create_playlist_from_chain.py  # 連鎖検索→YouTube Musicプレイリスト作成
├── test_ytmusic.py                # YouTube Music API テストスクリプト
├── browser.json                   # YouTube Music認証ファイル
├── core/
│   ├── feature_extractor.py       # 音声特徴量抽出
│   ├── db_manager.py              # ベクトルDB操作
│   └── ytmusic_manager.py         # YouTube Music API操作
├── data/
│   └── chroma_db_*/               # ChromaDB永続化先
├── pyproject.toml
└── README.md
```

## 使い方

### インストール

```bash
uv sync
```

### 楽曲の登録

```bash
uv run python main.py
```

`main.py` の `sound_dirs` に指定したディレクトリ内の音声ファイルをベクトルDBに登録します。

### 類似楽曲の連鎖検索

`main.py` 内の `chain_search()` 関数で、指定した曲から類似曲を連鎖的に辿ります。

```python
# main.py の末尾で実行
start_file = "フェスタ・イルミネーション [0Oj57StVGKk].wav"
chain_search(
    start_filename=start_file,
    dbs=[db_full, db_balance, db_minimal],
    n_songs=60,
)
```

### YouTube Music プレイリスト作成

連鎖検索の結果をYouTube Musicのプレイリストとして自動作成します。

```bash
uv run create_playlist_from_chain.py
```

#### 設定（定数を編集）

| 定数 | 説明 | 例 |
|------|------|-----|
| `PLAYLIST_NAME` | プレイリスト名 | `"曲調リコメンドプレイリスト"` |
| `START_SONG` | 開始曲のファイル名 | `"曲名 [videoId].wav"` |
| `N_SONGS` | プレイリストに追加する曲数 | `30` |
| `PRIVACY` | 公開設定 | `"PRIVATE"` / `"PUBLIC"` / `"UNLISTED"` |

#### 処理フロー

1. ベクトルDBから開始曲の類似曲を連鎖的に探索
2. ファイル名から曲名を抽出して検索クエリを生成
3. YouTube Music APIで楽曲を検索
4. プレイリストを作成（既存があれば削除して再作成）
5. Descriptionに処理日と開始曲を記載

### YouTube Music API テスト

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

### Pythonからの利用

```python
from core.db_manager import SongVectorDB
from core.feature_extractor import FeatureExtractor

# DB・抽出器の初期化
db = SongVectorDB(db_path="data/chroma_db", distance_fn="cosine")
extractor = FeatureExtractor(duration=90, mode="balanced")

# 楽曲を登録
embedding = extractor.extract_to_vector("song.wav")
db.add_song(song_id="song.wav", embedding=embedding, metadata={"filename": "song.wav"})

# 類似楽曲を検索
song = db.get_song("song.wav")
results = db.search_similar(query_embedding=song["embedding"], n_results=5)
```

## 開発フェーズ

- [x] **Phase 1**: librosa + ChromaDB で基本実装（MVP）
- [x] **Phase 2**: YouTube Music連携（プレイリスト自動作成）
- [ ] **Phase 3**: 精度向上が必要な場合、CLAP / OpenL3 等の深層学習モデルを導入
