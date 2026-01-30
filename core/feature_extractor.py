"""
音声ファイルから特徴量を抽出するモジュール
"""

import numpy as np
import librosa
from pathlib import Path
from dataclasses import dataclass
from typing import Literal


# 特徴量モードの型
FeatureMode = Literal["minimal", "balanced", "full"]


@dataclass
class AudioFeatures:
    """抽出した音声特徴量を保持するクラス"""

    # 基本特徴量
    mfcc: np.ndarray  # メル周波数ケプストラム係数 (20次元)
    mfcc_delta: np.ndarray  # MFCCの変化量 (20次元)
    chroma: np.ndarray  # クロマグラム (12次元)
    tonnetz: np.ndarray  # 和声的関係 (6次元)

    # スペクトル特徴量
    spectral_centroid: float  # スペクトル重心（音の明るさ）
    spectral_rolloff: float  # スペクトルロールオフ（高周波成分）
    spectral_bandwidth: float  # スペクトル帯域幅（音の広がり）
    spectral_contrast: np.ndarray  # スペクトルコントラスト (7次元)
    spectral_flatness: float  # スペクトル平坦度（ノイズっぽさ）

    # リズム・エネルギー特徴量
    zero_crossing_rate: float  # ゼロ交差率（ノイジーさ）
    rms_energy: float  # RMSエネルギー（音量）
    tempo: float  # テンポ (BPM)

    def to_vector(self, mode: FeatureMode = "full") -> list[float]:
        """
        特徴量を1次元ベクトルに変換する

        Args:
            mode: 特徴量モード
                - "minimal": 最小構成（15次元）テンポ・明るさ重視
                - "balanced": バランス型（30次元）汎用的
                - "full": 全特徴量（72次元）細かい違いを見たい

        Returns:
            特徴量ベクトル
        """
        if mode == "minimal":
            # ミニマル: テンポ、明るさ、音量、調性の基本
            # Tempo(1) + Chroma(12) + Centroid(1) + RMS(1) = 15次元
            return self.chroma.tolist() + [  # 12
                self.spectral_centroid,  # 1
                self.rms_energy,  # 1
                self.tempo / 200.0,  # 1
            ]

        elif mode == "balanced":
            # バランス: ミニマル + MFCC上位10個 + Contrast + Bandwidth
            # MFCC(10) + Chroma(12) + Contrast(7) + Centroid(1) + Bandwidth(1) + RMS(1) + Tempo(1) = 33次元
            return (
                self.mfcc[:10].tolist()  # 10（上位10個）
                + self.chroma.tolist()  # 12
                + self.spectral_contrast.tolist()  # 7
                + [
                    self.spectral_centroid,  # 1
                    self.spectral_bandwidth,  # 1
                    self.rms_energy,  # 1
                    self.tempo / 200.0,  # 1
                ]
            )

        else:  # full
            # フル: 全特徴量（72次元）
            return (
                self.mfcc.tolist()  # 20
                + self.mfcc_delta.tolist()  # 20
                + self.chroma.tolist()  # 12
                + self.tonnetz.tolist()  # 6
                + self.spectral_contrast.tolist()  # 7
                + [
                    self.spectral_centroid,  # 1
                    self.spectral_rolloff,  # 1
                    self.spectral_bandwidth,  # 1
                    self.spectral_flatness,  # 1
                    self.zero_crossing_rate,  # 1
                    self.rms_energy,  # 1
                    self.tempo / 200.0,  # 1
                ]
            )

    def get_vector_dim(self, mode: FeatureMode = "full") -> int:
        """指定モードでのベクトル次元数を返す"""
        return len(self.to_vector(mode))


# 各モードの次元数（参照用）
FEATURE_DIMENSIONS = {
    "minimal": 15,
    "balanced": 33,
    "full": 72,
}


class FeatureExtractor:
    """音声ファイルから特徴量を抽出するクラス"""

    def __init__(
        self,
        sr: int = 22050,
        duration: float | None = None,
        mode: FeatureMode = "balanced",
    ):
        """
        Args:
            sr: サンプリングレート
            duration: 読み込む秒数（Noneで全体）
            mode: 特徴量モード ("minimal", "balanced", "full")
        """
        self.sr = sr
        self.duration = duration
        self.mode = mode

    def extract(self, audio_path: str | Path) -> AudioFeatures:
        """
        音声ファイルから特徴量を抽出する

        Args:
            audio_path: 音声ファイルのパス

        Returns:
            AudioFeatures: 抽出した特徴量
        """
        # 音声ファイル読み込み
        y, sr = librosa.load(str(audio_path), sr=self.sr, duration=self.duration)

        # ===== MFCC関連 =====
        # MFCC（20次元、時間平均）
        mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=20)
        mfcc_mean = np.mean(mfcc, axis=1)

        # MFCC Delta（20次元、時間平均）- 音色の時間変化
        mfcc_delta = librosa.feature.delta(mfcc)
        mfcc_delta_mean = np.mean(mfcc_delta, axis=1)

        # ===== 和声・調性関連 =====
        # クロマグラム（12次元、時間平均）
        chroma = librosa.feature.chroma_stft(y=y, sr=sr)
        chroma_mean = np.mean(chroma, axis=1)

        # Tonnetz（6次元、時間平均）- 和声的関係
        tonnetz = librosa.feature.tonnetz(y=y, sr=sr)
        tonnetz_mean = np.mean(tonnetz, axis=1)

        # ===== スペクトル特徴量 =====
        # スペクトル重心（時間平均）- 音の明るさ
        spectral_centroid = librosa.feature.spectral_centroid(y=y, sr=sr)
        spectral_centroid_mean = float(np.mean(spectral_centroid))
        spectral_centroid_normalized = spectral_centroid_mean / 8000.0

        # スペクトルロールオフ（時間平均）- 高周波成分
        spectral_rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)
        spectral_rolloff_mean = float(np.mean(spectral_rolloff))
        spectral_rolloff_normalized = spectral_rolloff_mean / (sr / 2)

        # スペクトル帯域幅（時間平均）- 音の広がり
        spectral_bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr)
        spectral_bandwidth_mean = float(np.mean(spectral_bandwidth))
        spectral_bandwidth_normalized = spectral_bandwidth_mean / 4000.0

        # スペクトルコントラスト（7次元、時間平均）- 音の谷と山
        spectral_contrast = librosa.feature.spectral_contrast(y=y, sr=sr)
        spectral_contrast_mean = np.mean(spectral_contrast, axis=1)
        # 正規化（-100〜100 → 0〜1）
        spectral_contrast_normalized = (spectral_contrast_mean + 100) / 200.0

        # スペクトル平坦度（時間平均）- ノイズっぽさ
        spectral_flatness = librosa.feature.spectral_flatness(y=y)
        spectral_flatness_mean = float(np.mean(spectral_flatness))

        # ===== リズム・エネルギー =====
        # ゼロ交差率（時間平均）- ノイジーさ・打楽器感
        zcr = librosa.feature.zero_crossing_rate(y)
        zcr_mean = float(np.mean(zcr))

        # RMSエネルギー（時間平均）- 音量
        rms = librosa.feature.rms(y=y)
        rms_mean = float(np.mean(rms))

        # テンポ（BPM）
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        tempo_value = float(tempo) if np.isscalar(tempo) else float(tempo[0])

        return AudioFeatures(
            mfcc=mfcc_mean,
            mfcc_delta=mfcc_delta_mean,
            chroma=chroma_mean,
            tonnetz=tonnetz_mean,
            spectral_centroid=spectral_centroid_normalized,
            spectral_rolloff=spectral_rolloff_normalized,
            spectral_bandwidth=spectral_bandwidth_normalized,
            spectral_contrast=spectral_contrast_normalized,
            spectral_flatness=spectral_flatness_mean,
            zero_crossing_rate=zcr_mean,
            rms_energy=rms_mean,
            tempo=tempo_value,
        )

    def extract_to_vector(
        self, audio_path: str | Path, mode: FeatureMode | None = None
    ) -> list[float]:
        """
        音声ファイルから特徴量を抽出し、ベクトルとして返す

        Args:
            audio_path: 音声ファイルのパス
            mode: 特徴量モード（Noneの場合はコンストラクタで指定したモード）

        Returns:
            特徴量ベクトル
        """
        features = self.extract(audio_path)
        return features.to_vector(mode or self.mode)


# ===== 動作確認用 =====
if __name__ == "__main__":
    import sys

    print("=== 音声特徴量抽出テスト ===\n")

    # コマンドライン引数から音声ファイルパスを取得
    if len(sys.argv) < 2:
        print("使い方: python feature_extractor.py <音声ファイルパス> [モード]")
        print("モード: minimal, balanced, full（デフォルト: balanced）")
        print("例: python feature_extractor.py ./sample.mp3 balanced")
        sys.exit(1)

    audio_path = sys.argv[1]
    mode: FeatureMode = sys.argv[2] if len(sys.argv) > 2 else "balanced"  # type: ignore

    print(f"対象ファイル: {audio_path}")
    print(f"モード: {mode}（{FEATURE_DIMENSIONS.get(mode, '?')}次元）\n")

    # 特徴量抽出
    extractor = FeatureExtractor(duration=30, mode=mode)
    features = extractor.extract(audio_path)

    # 結果表示
    print("--- 抽出結果 ---")
    print(f"MFCC (20次元): {features.mfcc[:5]}... (先頭5つ)")
    print(f"MFCC Delta (20次元): {features.mfcc_delta[:5]}... (先頭5つ)")
    print(f"Chroma (12次元): {features.chroma[:5]}... (先頭5つ)")
    print(f"Tonnetz (6次元): {features.tonnetz}")
    print(f"Spectral Contrast (7次元): {features.spectral_contrast}")
    print(f"Spectral Centroid: {features.spectral_centroid:.4f}")
    print(f"Spectral Rolloff: {features.spectral_rolloff:.4f}")
    print(f"Spectral Bandwidth: {features.spectral_bandwidth:.4f}")
    print(f"Spectral Flatness: {features.spectral_flatness:.4f}")
    print(f"Zero Crossing Rate: {features.zero_crossing_rate:.4f}")
    print(f"RMS Energy: {features.rms_energy:.4f}")
    print(f"Tempo (BPM): {features.tempo:.1f}")

    # 各モードのベクトル比較
    print(f"\n--- 各モードのベクトル次元数 ---")
    for m in ["minimal", "balanced", "full"]:
        vec = features.to_vector(m)  # type: ignore
        marker = "◀" if m == mode else ""
        print(f"  {m}: {len(vec)}次元 {marker}")

    print(f"\n--- 選択モード ({mode}) のベクトル ---")
    vector = features.to_vector(mode)
    print(f"次元数: {len(vector)}")
    print(f"ベクトル: {vector[:10]}... (先頭10個)")

    print("\n=== 完了 ===")
