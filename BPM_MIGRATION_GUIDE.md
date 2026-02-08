# BPM Migration Guide

既存の楽曲にBPMを追加するためのマイグレーションガイド

## 概要

データベース内の既存楽曲で、BPMが未設定（NULL）のものについて、元の音声ファイルから特徴量を抽出してBPMを更新します。

## 前提条件

1. 音声ファイルが以下のパス構造で保存されている:
   ```
   base_path/source_dir/song_id
   ```
   例: `F:\song-recommender-data\data\gakumas_mv\song.mp3`

2. データベースに接続可能（MySQL）

3. 必要なPythonパッケージがインストール済み（librosa, sqlalchemy等）

## 使い方

### 1. ドライラン（テスト実行）

実際にはデータベースを更新せず、処理内容のみを確認:

```bash
uv run migrate_bpm.py --dry-run
```

### 2. 一部の曲のみ更新

最初の10曲のみ処理して動作確認:

```bash
uv run migrate_bpm.py --limit 10
```

### 3. カスタムベースパスを指定

デフォルトと異なるパスに音声ファイルがある場合:

```bash
uv run migrate_bpm.py --base-path "/path/to/your/data"
```

### 4. 全曲更新

すべての未設定楽曲を更新:

```bash
uv run migrate_bpm.py
```

## オプション

| オプション | 説明 | デフォルト値 |
|-----------|------|-------------|
| `--base-path` | 音声ファイルのベースパス | `F:\song-recommender-data\data` |
| `--limit` | 処理する曲数の上限 | なし（全件） |
| `--dry-run` | テストモード（更新しない） | False |

## 処理フロー

```
1. データベースからbpm IS NULLの楽曲を取得
   ↓
2. 各楽曲について:
   a. ファイルパスを構築: base_path + source_dir + song_id
   b. ファイルの存在確認
   c. 音声ファイルから特徴量を抽出（30秒間）
   d. BPM値を取得
   e. データベースを更新
   ↓
3. 結果サマリーを表示
```

## 実行例

### ドライラン実行例

```bash
$ uv run migrate_bpm.py --dry-run --limit 3
============================================================
🎵 BPMマイグレーションスクリプト
============================================================
ベースパス: F:\song-recommender-data\data
モード: DRY RUN (更新しない)
============================================================

📊 BPMが未設定の楽曲: 3件

[1/3] song1.mp3
   source_dir: gakumas_mv
   📁 ファイル: F:\song-recommender-data\data\gakumas_mv\song1.mp3
   ✅ BPM: 128.5

[2/3] song2.wav
   source_dir: scsp_mv
   📁 ファイル: F:\song-recommender-data\data\scsp_mv\song2.wav
   ✅ BPM: 140.2

[3/3] song3.mp3
   source_dir: youtube
   ❌ ファイルが見つかりません

============================================================
📊 結果サマリー
============================================================
処理対象: 3件
更新成功: 2件
ファイル未検出: 1件
BPM抽出失敗: 0件

⚠️  DRY RUNモードのため、実際にはデータベースは更新されていません
   本番実行する場合は --dry-run オプションを外してください
```

## エラー対処

### ファイルが見つからない

**エラー**: `❌ ファイルが見つかりません`

**原因**: 
- ベースパスが正しくない
- source_dirの値が実際のディレクトリ構造と異なる
- ファイルが移動または削除された

**対処**:
1. `--base-path` オプションで正しいパスを指定
2. データベースの source_dir の値を確認
3. ファイルシステムを確認

### BPM抽出失敗

**エラー**: `❌ BPM抽出失敗`

**原因**:
- 音声ファイルが破損している
- 対応していない形式
- ビートが検出できない（極端に遅い/速い曲、アンビエント等）

**対処**:
1. 音声ファイルの形式を確認（.wav, .mp3 のみサポート）
2. 別のツールで再生できるか確認
3. 該当楽曲をスキップして続行

## 注意事項

- 処理には時間がかかります（1曲あたり数秒～数十秒）
- 大量の楽曲を処理する場合は、まず `--limit 10` 等で動作確認することを推奨
- ネットワーク接続が必要（MySQLへの接続）
- 処理中は音声ファイルの読み込みでディスクI/Oが発生します

## トラブルシューティング

### MySQLへの接続エラー

.envファイルのMySQL接続情報を確認:
```
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=song_recommender
MYSQL_USER=app_user
MYSQL_PASSWORD=app_password
```

### メモリ不足

大量の楽曲を処理する場合、`--limit` オプションで分割処理:
```bash
# 100曲ずつ処理
uv run migrate_bpm.py --limit 100
# 完了後、再実行すると次の100曲が処理される
```

## 関連ファイル

- `migrate_bpm.py`: マイグレーションスクリプト本体
- `core/feature_extractor.py`: BPM抽出ロジック
- `core/models.py`: Songモデル（bpmフィールド定義）
- `register_songs.py`: 新規登録時のBPM抽出ロジック
