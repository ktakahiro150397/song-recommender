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

| 特徴量 | 意味 |
|--------|------|
| Tempo (BPM) | 曲の速さ |
| MFCC | 音色・質感（メル周波数ケプストラム係数） |
| Chroma | 和音・調性（12音階の分布） |
| Spectral Centroid | 音の明るさ |
| Spectral Rolloff | 高周波成分の割合 |
| Zero Crossing Rate | ノイジーさ・打楽器感 |

## 技術スタック

| 用途 | ライブラリ |
|------|-----------|
| 音声特徴量抽出 | librosa |
| ベクトルDB | ChromaDB |
| 数値計算 | numpy |
| CLI | typer |

## プロジェクト構成（予定）

```
song-recommender/
├── main.py                   # CLI エントリポイント
├── core/
│   ├── feature_extractor.py  # 音声特徴量抽出
│   ├── vectorizer.py         # ベクトル化
│   └── db_manager.py         # ベクトルDB操作
├── data/                     # ChromaDB永続化先
├── pyproject.toml
└── README.md
```

## 開発フェーズ

- **Phase 1**: librosa + ChromaDB で基本実装（MVP）
- **Phase 2**: 精度向上が必要な場合、CLAP / OpenL3 等の深層学習モデルを導入
