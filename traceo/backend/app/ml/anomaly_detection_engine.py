#!/usr/bin/env python3
"""
Unified Anomaly Detection Engine
Consolidates all anomaly detection logic across cost, security, and ML domains
Provides single source of truth for z-score and IsolationForest-based detection

Date: November 21, 2024
"""

import logging
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)


class AnomalySeverity(Enum):
    """Anomaly severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AnomalyResult:
    """Unified anomaly detection result"""
    is_anomaly: bool
    score: float  # 0-1 or 0-100 depending on detector
    z_score: Optional[float] = None
    severity: str = "low"
    confidence: float = 0.0  # Confidence level (0-1)
    threshold: Optional[float] = None
    message: str = ""


class ZScoreAnomalyDetector:
    """Unified Z-score based anomaly detection

    Uses mean and standard deviation to detect statistical outliers.
    Threshold of 2.5σ corresponds to 98% confidence interval.
    """

    # Standard thresholds
    THRESHOLD_WARNING = 2.0      # 95% confidence
    THRESHOLD_CRITICAL = 2.5     # 98% confidence
    MIN_DATA_POINTS = 5

    @staticmethod
    def calculate_statistics(data: List[float]) -> Tuple[float, float]:
        """Calculate mean and standard deviation

        Args:
            data: List of numerical values

        Returns:
            Tuple of (mean, std)
        """
        if not data or len(data) < ZScoreAnomalyDetector.MIN_DATA_POINTS:
            raise ValueError(
                f"Insufficient data: need {ZScoreAnomalyDetector.MIN_DATA_POINTS}+ points"
            )

        values = np.array(data, dtype=float)
        mean = np.mean(values)
        std = np.std(values)

        # Avoid division by zero
        if std == 0:
            std = mean * 0.1 if mean != 0 else 1.0

        return float(mean), float(std)

    @staticmethod
    def detect_anomaly(
        current_value: float,
        historical_data: List[float],
        threshold: float = THRESHOLD_CRITICAL
    ) -> AnomalyResult:
        """Detect if current value is an anomaly based on z-score

        Args:
            current_value: Value to check
            historical_data: Historical values for baseline
            threshold: Z-score threshold (default: 2.5σ)

        Returns:
            AnomalyResult with detection info
        """
        try:
            if not historical_data or len(historical_data) < ZScoreAnomalyDetector.MIN_DATA_POINTS:
                return AnomalyResult(
                    is_anomaly=False,
                    score=0,
                    z_score=0,
                    severity="unknown",
                    confidence=0.0,
                    message="Insufficient historical data"
                )

            mean, std = ZScoreAnomalyDetector.calculate_statistics(historical_data)
            z_score = (current_value - mean) / std if std != 0 else 0
            is_anomaly = abs(z_score) > threshold

            # Calculate percentage deviation
            deviation_pct = ((current_value - mean) / max(mean, 1)) * 100

            # Determine severity based on z-score
            if abs(z_score) > ZScoreAnomalyDetector.THRESHOLD_CRITICAL:
                severity = "high"
                confidence = min(abs(z_score) / 5.0, 1.0)  # Normalized to 0-1
            elif abs(z_score) > ZScoreAnomalyDetector.THRESHOLD_WARNING:
                severity = "medium"
                confidence = min(abs(z_score) / 3.0, 1.0)
            else:
                severity = "low"
                confidence = abs(z_score) / 2.0

            message = f"Z-score: {z_score:.2f}σ, Deviation: {deviation_pct:+.1f}%"

            return AnomalyResult(
                is_anomaly=is_anomaly,
                score=float(abs(z_score)),
                z_score=float(z_score),
                severity=severity,
                confidence=float(confidence),
                threshold=threshold,
                message=message
            )

        except Exception as e:
            logger.error(f"Z-score anomaly detection failed: {str(e)}")
            return AnomalyResult(
                is_anomaly=False,
                score=0,
                severity="error",
                message=f"Detection error: {str(e)}"
            )

    @staticmethod
    def detect_batch_anomalies(
        data: List[float],
        threshold: float = THRESHOLD_WARNING
    ) -> List[Tuple[int, AnomalyResult]]:
        """Detect anomalies in batch of values

        Args:
            data: List of values to check
            threshold: Z-score threshold

        Returns:
            List of (index, AnomalyResult) tuples for anomalies
        """
        anomalies = []

        if len(data) < ZScoreAnomalyDetector.MIN_DATA_POINTS:
            return anomalies

        try:
            mean, std = ZScoreAnomalyDetector.calculate_statistics(data)

            for idx, value in enumerate(data):
                z_score = (value - mean) / std if std != 0 else 0

                if abs(z_score) > threshold:
                    result = ZScoreAnomalyDetector.detect_anomaly(
                        value, data, threshold
                    )
                    anomalies.append((idx, result))

        except Exception as e:
            logger.error(f"Batch anomaly detection failed: {str(e)}")

        return anomalies

    @staticmethod
    def get_normal_range(
        historical_data: List[float],
        confidence: float = 0.95
    ) -> Tuple[float, float]:
        """Get normal range (confidence interval) for data

        Args:
            historical_data: Historical values
            confidence: Confidence level (0.95 = 95%)

        Returns:
            Tuple of (lower_bound, upper_bound)
        """
        try:
            if len(historical_data) < ZScoreAnomalyDetector.MIN_DATA_POINTS:
                return 0, float('inf')

            mean, std = ZScoreAnomalyDetector.calculate_statistics(historical_data)

            # Critical z-values for different confidence levels
            z_critical = 1.96 if confidence >= 0.95 else 1.64

            lower_bound = max(0, mean - (z_critical * std))
            upper_bound = mean + (z_critical * std)

            return float(lower_bound), float(upper_bound)

        except Exception as e:
            logger.error(f"Failed to calculate normal range: {str(e)}")
            return 0, float('inf')


class IsolationForestAnomalyDetector:
    """Unified IsolationForest-based anomaly detection

    Uses Isolation Forest ML algorithm for anomaly detection.
    Works well for multivariate data and complex patterns.
    """

    def __init__(self, contamination: float = 0.1, random_state: int = 42):
        """Initialize detector

        Args:
            contamination: Expected proportion of anomalies (0.0-0.5)
            random_state: Random seed for reproducibility
        """
        self.model = IsolationForest(
            contamination=contamination,
            random_state=random_state,
            n_estimators=100
        )
        self.scaler = StandardScaler()
        self.is_fitted = False
        self.contamination = contamination

    def fit(self, data: np.ndarray):
        """Fit the Isolation Forest model

        Args:
            data: Training data (samples x features)
        """
        if len(data) < 10:
            logger.warning(f"Need at least 10 samples for training, got {len(data)}")
            return

        # Handle 1D data
        if data.ndim == 1:
            data = data.reshape(-1, 1)

        # Fit scaler and model
        data_scaled = self.scaler.fit_transform(data)
        self.model.fit(data_scaled)
        self.is_fitted = True

        logger.info(f"IsolationForest fitted on {len(data)} samples")

    def detect_anomalies(self, data: np.ndarray) -> List[int]:
        """Detect anomalies in data

        Args:
            data: Data to check (samples x features)

        Returns:
            List of anomaly indices (-1 = anomaly, 1 = normal)
        """
        if not self.is_fitted:
            logger.warning("Model not fitted. Call fit() first.")
            return []

        # Handle 1D data
        if data.ndim == 1:
            data = data.reshape(-1, 1)

        try:
            data_scaled = self.scaler.transform(data)
            predictions = self.model.predict(data_scaled)
            anomaly_indices = [i for i, pred in enumerate(predictions) if pred == -1]
            return anomaly_indices
        except Exception as e:
            logger.error(f"Anomaly detection failed: {str(e)}")
            return []

    def get_anomaly_scores(self, data: np.ndarray) -> np.ndarray:
        """Get anomaly scores (0-1) for each sample

        Args:
            data: Data to score

        Returns:
            Array of anomaly scores (0=normal, 1=anomalous)
        """
        if not self.is_fitted:
            logger.warning("Model not fitted. Call fit() first.")
            return np.array([])

        # Handle 1D data
        if data.ndim == 1:
            data = data.reshape(-1, 1)

        try:
            data_scaled = self.scaler.transform(data)
            # Get decision function scores
            scores = self.model.score_samples(data_scaled)
            # Convert to 0-1 range (more negative = more anomalous)
            normalized_scores = 1 / (1 + np.exp(scores))
            return normalized_scores
        except Exception as e:
            logger.error(f"Score calculation failed: {str(e)}")
            return np.array([])

    def detect_single(self, sample: np.ndarray) -> AnomalyResult:
        """Detect anomaly for single sample

        Args:
            sample: Single sample to check

        Returns:
            AnomalyResult with detection info
        """
        if not self.is_fitted:
            return AnomalyResult(
                is_anomaly=False,
                score=0,
                message="Model not fitted"
            )

        try:
            # Handle 1D sample
            if sample.ndim == 0:
                sample = np.array([sample])
            if sample.ndim == 1:
                sample = sample.reshape(1, -1)

            sample_scaled = self.scaler.transform(sample)
            prediction = self.model.predict(sample_scaled)[0]
            score = self.model.score_samples(sample_scaled)[0]

            # Normalize score to 0-1
            normalized_score = 1 / (1 + np.exp(score))

            return AnomalyResult(
                is_anomaly=(prediction == -1),
                score=float(normalized_score),
                severity="high" if normalized_score > 0.7 else "medium" if normalized_score > 0.5 else "low",
                confidence=float(normalized_score)
            )

        except Exception as e:
            logger.error(f"Single sample detection failed: {str(e)}")
            return AnomalyResult(
                is_anomaly=False,
                score=0,
                message=f"Detection error: {str(e)}"
            )


class AnomalyDetectionFactory:
    """Factory for creating domain-specific anomaly detectors

    Provides adapters and helpers for different use cases:
    - Cost anomaly detection
    - Security threat detection
    - ML model anomaly detection
    """

    @staticmethod
    def create_cost_detector() -> 'CostAnomalyDetector':
        """Create detector tuned for cost anomalies

        Returns:
            CostAnomalyDetector instance
        """
        return CostAnomalyDetector()

    @staticmethod
    def create_threat_detector() -> IsolationForestAnomalyDetector:
        """Create detector tuned for security threats

        Returns:
            IsolationForestAnomalyDetector instance (0.05 contamination for stricter detection)
        """
        return IsolationForestAnomalyDetector(contamination=0.05)

    @staticmethod
    def create_ml_detector() -> IsolationForestAnomalyDetector:
        """Create detector tuned for ML training

        Returns:
            IsolationForestAnomalyDetector instance (0.1 contamination for general use)
        """
        return IsolationForestAnomalyDetector(contamination=0.1)


class CostAnomalyDetector:
    """Domain-specific adapter for cost anomaly detection

    Combines z-score and IsolationForest for robust cost anomaly detection.
    """

    def __init__(self):
        self.z_score_detector = ZScoreAnomalyDetector()
        self.isolation_forest = IsolationForestAnomalyDetector(contamination=0.1)
        self.baseline_mean = None
        self.baseline_std = None
        self.is_fitted = False

    def fit(self, cost_data: List[float]):
        """Train detector on historical cost data

        Args:
            cost_data: List of daily costs
        """
        if len(cost_data) < 10:
            logger.warning(f"Need at least 10 data points, got {len(cost_data)}")
            return

        # Calculate baseline statistics
        self.baseline_mean, self.baseline_std = ZScoreAnomalyDetector.calculate_statistics(cost_data)

        # Also fit isolation forest
        X = np.array(cost_data).reshape(-1, 1)
        self.isolation_forest.fit(X)

        self.is_fitted = True
        logger.info(f"Cost detector fitted: mean=${self.baseline_mean:.2f}, std=${self.baseline_std:.2f}")

    def detect_anomaly(
        self,
        current_cost: float,
        cost_history: Optional[List[float]] = None
    ) -> AnomalyResult:
        """Detect if current cost is anomalous

        Args:
            current_cost: Current cost value
            cost_history: Optional historical data (if not pre-fitted)

        Returns:
            AnomalyResult
        """
        if not self.is_fitted:
            if not cost_history:
                return AnomalyResult(
                    is_anomaly=False,
                    score=0,
                    message="Not fitted and no history provided"
                )
            self.fit(cost_history)

        # Use z-score detector
        return ZScoreAnomalyDetector.detect_anomaly(
            current_cost,
            cost_history or [self.baseline_mean],
            threshold=2.5
        )

    def calculate_anomaly_score(self, cost: float) -> float:
        """Legacy method for compatibility

        Returns anomaly score 0-1
        """
        if not self.is_fitted:
            return 0.0

        if self.baseline_std == 0:
            return 0.0

        z_score = abs((cost - self.baseline_mean) / self.baseline_std)
        # Convert z-score to 0-1 scale
        return min(z_score / 3.0, 1.0)


# Export public API
__all__ = [
    'AnomalyResult',
    'AnomalySeverity',
    'ZScoreAnomalyDetector',
    'IsolationForestAnomalyDetector',
    'AnomalyDetectionFactory',
    'CostAnomalyDetector',
]
