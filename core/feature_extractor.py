"""
音声ファイルから特徴量を抽出するモジュール
"""

import numpy as np
import librosa
from pathlib import Path
from dataclasses import dataclass


@dataclass
class AudioFeatures:
    """抽出した音声特徴量を保持するクラス"""

    mfcc: np.ndarray  # メル周波数ケプストラム係数 (20次元)
    chroma: np.ndarray  # クロマグラム (12次元)
    spectral_centroid: float  # スペクトル重心
    spectral_rolloff: float  # スペクトルロールオフ
    zero_crossing_rate: float  # ゼロ交差率
    tempo: float  # テンポ (BPM)

    def to_vector(self) -> list[float]:
        """特徴量を1次元ベクトルに変換する"""
        return (
            self.mfcc.tolist()
            + self.chroma.tolist()
            + [
                self.spectral_centroid,
                self.spectral_rolloff,
                self.zero_crossing_rate,
                self.tempo / 200.0,  # 正規化（0-200 BPM → 0-1）
            ]
        )

    @property
    def vector_dim(self) -> int:
        """ベクトルの次元数"""
        return len(self.to_vector())


class FeatureExtractor:
    """音声ファイルから特徴量を抽出するクラス"""

    def __init__(self, sr: int = 22050, duration: float | None = None):
        """
        Args:
            sr: サンプリングレート
            duration: 読み込む秒数（Noneで全体）
        """
        self.sr = sr
        self.duration = duration

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

        # MFCC（20次元、時間平均）
        mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=20)
        mfcc_mean = np.mean(mfcc, axis=1)

        # クロマグラム（12次元、時間平均）
        chroma = librosa.feature.chroma_stft(y=y, sr=sr)
        chroma_mean = np.mean(chroma, axis=1)

        # スペクトル重心（時間平均）
        spectral_centroid = librosa.feature.spectral_centroid(y=y, sr=sr)
        spectral_centroid_mean = float(np.mean(spectral_centroid))
        # 正規化（0-8000 Hz → 0-1）
        spectral_centroid_normalized = spectral_centroid_mean / 8000.0

        # スペクトルロールオフ（時間平均）
        spectral_rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)
        spectral_rolloff_mean = float(np.mean(spectral_rolloff))
        # 正規化（0-sr/2 → 0-1）
        spectral_rolloff_normalized = spectral_rolloff_mean / (sr / 2)

        # ゼロ交差率（時間平均）
        zcr = librosa.feature.zero_crossing_rate(y)
        zcr_mean = float(np.mean(zcr))

        # テンポ（BPM）
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        tempo_value = float(tempo) if np.isscalar(tempo) else float(tempo[0])

        return AudioFeatures(
            mfcc=mfcc_mean,
            chroma=chroma_mean,
            spectral_centroid=spectral_centroid_normalized,
            spectral_rolloff=spectral_rolloff_normalized,
            zero_crossing_rate=zcr_mean,
            tempo=tempo_value,
        )

    def extract_to_vector(self, audio_path: str | Path) -> list[float]:
        """
        音声ファイルから特徴量を抽出し、ベクトルとして返す

        Args:
            audio_path: 音声ファイルのパス

        Returns:
            特徴量ベクトル
        """
        features = self.extract(audio_path)
        return features.to_vector()


# ===== 動作確認用 =====
if __name__ == "__main__":
    import sys

    print("=== 音声特徴量抽出テスト ===\n")

    # コマンドライン引数から音声ファイルパスを取得
    if len(sys.argv) < 2:
        print("使い方: python feature_extractor.py <音声ファイルパス>")
        print("例: python feature_extractor.py ./sample.mp3")
        sys.exit(1)

    audio_path = sys.argv[1]
    print(f"対象ファイル: {audio_path}\n")

    # 特徴量抽出
    extractor = FeatureExtractor(duration=30)  # 最初の30秒のみ
    features = extractor.extract(audio_path)

    # 結果表示
    print("--- 抽出結果 ---")
    print(f"MFCC (20次元): {features.mfcc[:5]}... (先頭5つ)")
    print(f"Chroma (12次元): {features.chroma[:5]}... (先頭5つ)")
    print(f"Spectral Centroid: {features.spectral_centroid:.4f}")
    print(f"Spectral Rolloff: {features.spectral_rolloff:.4f}")
    print(f"Zero Crossing Rate: {features.zero_crossing_rate:.4f}")
    print(f"Tempo (BPM): {features.tempo:.1f}")

    print(f"\n--- ベクトル ---")
    vector = features.to_vector()
    print(f"次元数: {len(vector)}")
    print(f"ベクトル: {vector[:10]}... (先頭10つ)")

    print("\n=== 完了 ===")
