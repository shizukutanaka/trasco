#!/usr/bin/env python3
"""
Shared anomaly detection utilities for cost management
Consolidates duplicate anomaly detection logic
Date: November 21, 2024
"""

import logging
from typing import List, Tuple
from dataclasses import dataclass
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class AnomalyResult:
    """Anomaly detection result"""
    is_anomaly: bool
    z_score: float
    threshold: float
    severity: str  # "low", "medium", "high"
    anomaly_percentage: float  # How much above normal


class CostAnomalyDetector:
    """Unified cost anomaly detection"""

    # Z-score thresholds
    THRESHOLD_WARNING = 2.0      # 2σ - 95% confidence
    THRESHOLD_CRITICAL = 2.5     # 2.5σ - 98% confidence

    # Minimum data points for analysis
    MIN_DATA_POINTS = 5

    @staticmethod
    def calculate_statistics(cost_data: List[float]) -> Tuple[float, float]:
        """Calculate mean and standard deviation"""
        if not cost_data or len(cost_data) < CostAnomalyDetector.MIN_DATA_POINTS:
            raise ValueError(f"Insufficient data: need {CostAnomalyDetector.MIN_DATA_POINTS}+ points")

        values = np.array(cost_data, dtype=float)
        mean = np.mean(values)
        std = np.std(values)

        # Avoid division by zero
        if std == 0:
            std = mean * 0.1  # Use 10% of mean as fallback

        return mean, std

    @staticmethod
    def detect_anomaly(current_cost: float, cost_history: List[float],
                      threshold: float = THRESHOLD_CRITICAL) -> AnomalyResult:
        """Detect if current cost is an anomaly"""
        try:
            if not cost_history or len(cost_history) < CostAnomalyDetector.MIN_DATA_POINTS:
                return AnomalyResult(
                    is_anomaly=False,
                    z_score=0,
                    threshold=threshold,
                    severity="unknown",
                    anomaly_percentage=0
                )

            mean, std = CostAnomalyDetector.calculate_statistics(cost_history)
            z_score = (current_cost - mean) / std
            is_anomaly = abs(z_score) > threshold

            # Calculate percentage above normal
            anomaly_pct = ((current_cost - mean) / max(mean, 1)) * 100

            # Determine severity
            if abs(z_score) > CostAnomalyDetector.THRESHOLD_CRITICAL:
                severity = "high"
            elif abs(z_score) > CostAnomalyDetector.THRESHOLD_WARNING:
                severity = "medium"
            else:
                severity = "low"

            return AnomalyResult(
                is_anomaly=is_anomaly,
                z_score=float(z_score),
                threshold=threshold,
                severity=severity,
                anomaly_percentage=float(anomaly_pct)
            )

        except Exception as e:
            logger.error(f"Anomaly detection failed: {str(e)}")
            return AnomalyResult(
                is_anomaly=False,
                z_score=0,
                threshold=threshold,
                severity="error",
                anomaly_percentage=0
            )

    @staticmethod
    def detect_batch_anomalies(costs: List[float],
                              threshold: float = THRESHOLD_WARNING) -> List[Tuple[int, AnomalyResult]]:
        """Detect anomalies in batch of costs"""
        anomalies = []

        if len(costs) < CostAnomalyDetector.MIN_DATA_POINTS:
            return anomalies

        try:
            mean, std = CostAnomalyDetector.calculate_statistics(costs)

            for idx, cost in enumerate(costs):
                z_score = (cost - mean) / std

                if abs(z_score) > threshold:
                    anomaly_pct = ((cost - mean) / max(mean, 1)) * 100
                    severity = "high" if abs(z_score) > CostAnomalyDetector.THRESHOLD_CRITICAL else "medium"

                    anomalies.append((
                        idx,
                        AnomalyResult(
                            is_anomaly=True,
                            z_score=float(z_score),
                            threshold=threshold,
                            severity=severity,
                            anomaly_percentage=float(anomaly_pct)
                        )
                    ))

        except Exception as e:
            logger.error(f"Batch anomaly detection failed: {str(e)}")

        return anomalies

    @staticmethod
    def get_normal_range(cost_history: List[float],
                         confidence: float = 0.95) -> Tuple[float, float]:
        """Get normal cost range based on historical data"""
        try:
            if len(cost_history) < CostAnomalyDetector.MIN_DATA_POINTS:
                return 0, float('inf')

            mean, std = CostAnomalyDetector.calculate_statistics(cost_history)

            # 95% confidence interval = ±1.96σ
            # 99% confidence interval = ±2.58σ
            z_critical = 1.96 if confidence >= 0.95 else 1.64

            lower_bound = max(0, mean - (z_critical * std))
            upper_bound = mean + (z_critical * std)

            return float(lower_bound), float(upper_bound)

        except Exception as e:
            logger.error(f"Failed to calculate normal range: {str(e)}")
            return 0, float('inf')
