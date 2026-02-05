"""
音声特徴量の統計情報を計算するモジュール
"""

import numpy as np
from typing import Dict, List


class FeatureStatistics:
    """音声特徴量の統計情報を計算・管理するクラス"""

    # 特徴量のインデックスマッピング（fullモード: 72次元）
    FEATURE_MAPPING = {
        "MFCC": (0, 20),  # 20次元
        "MFCC Delta": (20, 40),  # 20次元
        "Chroma": (40, 52),  # 12次元
        "Tonnetz": (52, 58),  # 6次元
        "Spectral Contrast": (58, 65),  # 7次元
        "Spectral Centroid": (65, 66),  # 1次元
        "Spectral Rolloff": (66, 67),  # 1次元
        "Spectral Bandwidth": (67, 68),  # 1次元
        "Spectral Flatness": (68, 69),  # 1次元
        "Zero Crossing Rate": (69, 70),  # 1次元
        "RMS Energy": (70, 71),  # 1次元
        "Tempo": (71, 72),  # 1次元（正規化済み: /200.0）
    }

    @staticmethod
    def calculate_statistics(embeddings: List[List[float]]) -> Dict:
        """
        音声特徴量の統計情報を計算する

        Args:
            embeddings: 音声特徴量ベクトルのリスト

        Returns:
            統計情報の辞書（各特徴量の平均、標準偏差、最小値、最大値）
        """
        if not embeddings:
            return {}

        # numpy配列に変換
        embeddings_array = np.array(embeddings, dtype=np.float32)
        
        # データが1次元の場合のチェック
        if embeddings_array.ndim == 1:
            return {}
        
        if len(embeddings_array.shape) < 2:
            return {}

        # 全体の統計
        statistics = {
            "sample_size": len(embeddings),
            "total_dimensions": int(embeddings_array.shape[1]),
            "features": {},
        }

        # 各特徴量の統計を計算
        for feature_name, (start, end) in FeatureStatistics.FEATURE_MAPPING.items():
            if int(end) <= int(embeddings_array.shape[1]):
                feature_data = embeddings_array[:, start:end]

                # 次元ごとの統計を計算
                feature_stats = {
                    "mean": float(np.mean(feature_data)),
                    "std": float(np.std(feature_data)),
                    "min": float(np.min(feature_data)),
                    "max": float(np.max(feature_data)),
                    "dimensions": end - start,
                }

                # 多次元特徴量の場合、次元ごとの統計も保存
                if end - start > 1:
                    feature_stats["per_dimension"] = {
                        "mean": feature_data.mean(axis=0).tolist(),
                        "std": feature_data.std(axis=0).tolist(),
                    }

                statistics["features"][feature_name] = feature_stats

        return statistics

    @staticmethod
    def get_feature_groups() -> Dict[str, List[str]]:
        """
        特徴量をカテゴリごとにグループ化

        Returns:
            カテゴリ名と特徴量名のリストの辞書
        """
        return {
            "音色・質感": ["MFCC", "MFCC Delta"],
            "和音・調性": ["Chroma", "Tonnetz"],
            "音の明るさ・質感": [
                "Spectral Centroid",
                "Spectral Contrast",
                "Spectral Bandwidth",
                "Spectral Flatness",
            ],
            "リズム・エネルギー": ["Tempo", "RMS Energy", "Zero Crossing Rate"],
        }
