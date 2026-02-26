# 曲登録ガイド

曲登録は音声特徴量抽出（librosa）を使うためマシンパワーが必要です。
本番サーバーとは**別のPC**でスクリプトを実行してください。

## 前提条件

- Python 3.12+
- uv がインストール済み
- `.env` ファイルに MySQL / ChromaDB の接続情報が設定済み
- MySQL と ChromaDB が起動中（本番サーバー側）

## セットアップ

```bash
# 依存パッケージをインストール
uv sync

# .env を設定（本番サーバーの MySQL / ChromaDB を指すように）
cp .env.example .env
# MYSQL_HOST, CHROMA_HOST を編集
```

## 音声ファイルの準備

音声ファイルは `.wav` または `.mp3` 形式に対応。
ファイル名から曲名・アーティスト名・YouTube ID が自動抽出されます。

### ファイル名フォーマット（推奨）

```
# アーティスト名 - 曲名 [YouTubeVideoID].wav
Ado - 唱 [xxxyyyyzzz].wav

# 「」カギ括弧で曲名指定
アーティスト「曲名」Official MV [xxxyyyyzzz].wav
```

## 曲登録スクリプト

### ローカルファイルを一括登録

```bash
# 指定ディレクトリの音声ファイルを全件登録
uv run scripts/register_songs.py --dir /path/to/music/directory

# YouTubeキューの未処理分を登録
uv run scripts/register_songs.py --youtube-queue
```

### 並列処理オプション

```bash
# 4並列でバッチ処理（大量登録時に推奨）
uv run scripts/register_songs.py --dir /path/to/music --workers 4
```

### セグメント登録（オプション・GPU推奨）

MERT または AST モデルを使ったセグメント登録（高精度だが時間がかかる）：

```bash
uv run scripts/register_segments_mert.py --dir /path/to/music --segment-seconds 5
```

## YouTube URL から登録

YouTube動画/チャンネル/プレイリストのURLを登録キューに追加し、一括ダウンロード・登録できます。

この操作はフロントエンドの「YouTube登録」ページまたは直接DBへの追加で行います。

## プレイリスト作成（CLI）

登録済み曲から連鎖検索でプレイリストを作成：

```bash
uv run scripts/create_playlist_from_chain.py "曲名キーワード" --count 30
uv run scripts/create_playlist_from_chain.py "曲名キーワード" --name "プレイリスト名"
```

## ChromaDB コレクションの使い分け

| コレクション | 推奨用途 |
|-------------|---------|
| `songs_minimal` (15次元) | 速度重視・大量検索 |
| `songs_balanced` (33次元) | 通常利用（推奨） |
| `songs_full` (72次元) | 精度重視 |

スクリプトはデフォルトで3種類すべてに登録します。
