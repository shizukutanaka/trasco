"""
ML-Based Threat Detection & Behavioral Analytics System

Hybrid threat detection combining:
- Isolation Forest for real-time anomaly detection
- LSTM Autoencoder for behavioral pattern detection
- XGBoost Ensemble for final threat scoring

Target: 97.9% accuracy, 0.8% false positive rate
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import json
import logging
from abc import ABC, abstractmethod

# ML Libraries
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
import xgboost as xgb
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers

# Setup logging
logger = logging.getLogger(__name__)


class AnomalyType(Enum):
    """Types of detected anomalies"""
    IMPOSSIBLE_TRAVEL = "impossible_travel"
    UNUSUAL_TIME = "unusual_time"
    UNUSUAL_VOLUME = "unusual_volume"
    UNUSUAL_RESOURCES = "unusual_resources"
    BEHAVIORAL_DEVIATION = "behavioral_deviation"
    ANOMALY_ENSEMBLE = "anomaly_ensemble"


class ThreatLevel(Enum):
    """Threat severity levels"""
    LOW = "low"  # 0-20
    MEDIUM = "medium"  # 20-50
    HIGH = "high"  # 50-80
    CRITICAL = "critical"  # 80-100


@dataclass
class UserBehaviorBaseline:
    """User behavioral baseline for anomaly detection"""
    user_id: str
    avg_login_time: float  # Hours of day (0-24)
    typical_locations: List[str]  # Geographic locations
    typical_resources: List[str]  # Common resources accessed
    avg_data_volume: float  # Average data transfer in GB
    typical_login_frequency: float  # Logins per day
    device_fingerprints: List[str]  # Known device signatures

    # Temporal patterns
    login_hours_distribution: Dict[int, float]  # Hour -> probability
    day_of_week_pattern: Dict[int, float]  # Day -> probability

    # Statistical bounds
    data_volume_std: float  # Standard deviation
    location_distance_threshold: float  # Max reasonable travel distance (km)
    max_impossible_travel_speed: float  # km/hour (default 1000)

    created_at: datetime = None
    updated_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()


@dataclass
class UserActivity:
    """Single user activity record"""
    user_id: str
    activity_type: str  # login, data_access, resource_access, etc.
    timestamp: datetime
    location: str  # Geographic location
    latitude: float
    longitude: float
    device_fingerprint: str
    device_name: str
    ip_address: str
    resource_accessed: str
    data_transferred_gb: float
    duration_seconds: int
    success: bool = True
    user_agent: str = ""

    def to_feature_dict(self) -> Dict[str, float]:
        """Convert activity to feature dictionary"""
        return {
            'hour': self.timestamp.hour,
            'day_of_week': self.timestamp.weekday(),
            'data_transferred_gb': self.data_transferred_gb,
            'duration_seconds': self.duration_seconds,
            'latitude': self.latitude,
            'longitude': self.longitude,
        }


@dataclass
class ThreatScore:
    """Threat assessment result"""
    user_id: str
    timestamp: datetime
    threat_score: float  # 0-100
    threat_level: ThreatLevel
    primary_anomalies: List[AnomalyType]
    confidence: float  # 0-1

    # Component scores
    isolation_forest_score: float
    lstm_autoencoder_score: float
    xgboost_ensemble_score: float

    # Detailed findings
    impossible_travel_detected: bool
    unusual_time_detected: bool
    unusual_volume_detected: bool
    unusual_resources_detected: bool
    behavioral_deviation_score: float

    # Recommendations
    recommended_actions: List[str]
    explanation: str


class IsolationForestDetector:
    """Real-time anomaly detection using Isolation Forest"""

    def __init__(self, contamination: float = 0.05, n_estimators: int = 100):
        """
        Initialize Isolation Forest detector

        Args:
            contamination: Expected proportion of anomalies (0.05 = 5%)
            n_estimators: Number of isolation trees
        """
        self.contamination = contamination
        self.model = IsolationForest(
            contamination=contamination,
            n_estimators=n_estimators,
            random_state=42,
            n_jobs=-1
        )
        self.scaler = StandardScaler()
        self.is_trained = False

    def train(self, X: np.ndarray) -> None:
        """Train the detector on normal behavior data"""
        X_scaled = self.scaler.fit_transform(X)
        self.model.fit(X_scaled)
        self.is_trained = True
        logger.info(f"IsolationForest trained on {X.shape[0]} samples")

    def predict_anomaly_score(self, X: np.ndarray) -> np.ndarray:
        """
        Predict anomaly scores (0-100 scale)

        Args:
            X: Feature matrix

        Returns:
            Anomaly scores (0-100, higher = more anomalous)
        """
        if not self.is_trained:
            raise ValueError("Model must be trained first")

        X_scaled = self.scaler.transform(X)

        # Get anomaly scores (-1 to 1, where 1 is normal)
        scores = -self.model.score_samples(X_scaled)

        # Scale to 0-100
        scores_normalized = (scores - scores.min()) / (scores.max() - scores.min() + 1e-10) * 100

        return scores_normalized


class LSTMAutoencoderBehavior:
    """Behavioral anomaly detection using LSTM Autoencoder"""

    def __init__(self, sequence_length: int = 24, feature_dim: int = 8):
        """
        Initialize LSTM Autoencoder

        Args:
            sequence_length: Number of timesteps in sequence
            feature_dim: Number of features per timestep
        """
        self.sequence_length = sequence_length
        self.feature_dim = feature_dim
        self.model = None
        self.threshold = None
        self.is_trained = False
        self.scaler = StandardScaler()

        self._build_model()

    def _build_model(self):
        """Build LSTM Autoencoder architecture"""
        # Encoder
        inputs = keras.Input(shape=(self.sequence_length, self.feature_dim))
        encoded = layers.LSTM(64, activation='relu')(inputs)
        encoded = layers.LSTM(32, activation='relu')(encoded)

        # Decoder
        decoded = layers.RepeatVector(self.sequence_length)(encoded)
        decoded = layers.LSTM(32, activation='relu', return_sequences=True)(decoded)
        decoded = layers.LSTM(64, activation='relu', return_sequences=True)(decoded)
        decoded = layers.TimeDistributed(layers.Dense(self.feature_dim))(decoded)

        # Autoencoder
        self.model = keras.Model(inputs, decoded)
        self.model.compile(
            optimizer='adam',
            loss='mse'
        )

    def train(self, X_sequences: np.ndarray, epochs: int = 50, validation_split: float = 0.1):
        """
        Train the autoencoder on normal behavior sequences

        Args:
            X_sequences: Shape (n_samples, sequence_length, feature_dim)
            epochs: Training epochs
            validation_split: Validation data split
        """
        if X_sequences.shape[1] != self.sequence_length:
            raise ValueError(f"Expected sequence length {self.sequence_length}, got {X_sequences.shape[1]}")

        self.model.fit(
            X_sequences, X_sequences,
            epochs=epochs,
            batch_size=32,
            validation_split=validation_split,
            verbose=0
        )

        # Calculate reconstruction error threshold (95th percentile on training data)
        train_predictions = self.model.predict(X_sequences)
        train_mse = np.mean(np.power(X_sequences - train_predictions, 2), axis=(1, 2))
        self.threshold = np.percentile(train_mse, 95)

        self.is_trained = True
        logger.info(f"LSTM Autoencoder trained with threshold={self.threshold:.4f}")

    def predict_anomaly_score(self, X_sequences: np.ndarray) -> np.ndarray:
        """
        Predict anomaly scores based on reconstruction error

        Args:
            X_sequences: Shape (n_samples, sequence_length, feature_dim)

        Returns:
            Anomaly scores (0-100)
        """
        if not self.is_trained:
            raise ValueError("Model must be trained first")

        predictions = self.model.predict(X_sequences, verbose=0)
        mse = np.mean(np.power(X_sequences - predictions, 2), axis=(1, 2))

        # Scale to 0-100 based on threshold
        anomaly_scores = (mse / (self.threshold + 1e-10)) * 100
        anomaly_scores = np.clip(anomaly_scores, 0, 100)

        return anomaly_scores


class XGBoostEnsembleClassifier:
    """Final threat classification using XGBoost ensemble"""

    def __init__(self, max_depth: int = 6, learning_rate: float = 0.1):
        """Initialize XGBoost classifier"""
        self.model = xgb.XGBClassifier(
            max_depth=max_depth,
            learning_rate=learning_rate,
            n_estimators=100,
            objective='binary:logistic',
            random_state=42,
            n_jobs=-1,
            eval_metric='logloss'
        )
        self.is_trained = False

    def train(self, X: np.ndarray, y: np.ndarray):
        """
        Train the ensemble classifier

        Args:
            X: Feature matrix
            y: Binary labels (0=normal, 1=threat)
        """
        self.model.fit(X, y, verbose=False)
        self.is_trained = True
        logger.info(f"XGBoost trained on {X.shape[0]} samples")

    def predict_threat_probability(self, X: np.ndarray) -> np.ndarray:
        """
        Predict threat probability (0-1)

        Args:
            X: Feature matrix

        Returns:
            Threat probabilities (0-1)
        """
        if not self.is_trained:
            raise ValueError("Model must be trained first")

        probabilities = self.model.predict_proba(X)[:, 1]
        return probabilities


class HybridThreatDetector:
    """
    Hybrid threat detection combining:
    - Isolation Forest (real-time detection)
    - LSTM Autoencoder (behavioral patterns)
    - XGBoost Ensemble (final scoring)

    Target: 97.9% accuracy, 0.8% false positive rate
    """

    def __init__(self):
        """Initialize hybrid threat detector"""
        self.isolation_forest = IsolationForestDetector()
        self.lstm_autoencoder = LSTMAutoencoderBehavior()
        self.xgboost_ensemble = XGBoostEnsembleClassifier()

        # User baselines storage
        self.user_baselines: Dict[str, UserBehaviorBaseline] = {}
        self.user_activity_history: Dict[str, List[UserActivity]] = {}

        # Threat score history
        self.threat_history: Dict[str, List[ThreatScore]] = {}

        # Configuration
        self.impossible_travel_threshold = 1000  # km/hour
        self.data_volume_deviation_threshold = 3.0  # Standard deviations
        self.unusual_resource_threshold = 0.05  # 5% anomaly probability

        self.is_trained = False

    def establish_baseline(self, user_id: str, activities: List[UserActivity], days: int = 30):
        """
        Establish behavioral baseline for a user

        Args:
            user_id: User identifier
            activities: Historical activity records
            days: Number of days to consider for baseline
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        relevant_activities = [a for a in activities if a.timestamp >= cutoff_date]

        if not relevant_activities:
            logger.warning(f"Insufficient data for user {user_id}")
            return

        # Calculate temporal patterns
        hours = [a.timestamp.hour for a in relevant_activities]
        days_of_week = [a.timestamp.weekday() for a in relevant_activities]

        hour_counts = {}
        for h in range(24):
            count = sum(1 for hh in hours if hh == h)
            hour_counts[h] = count / max(len(hours), 1)

        day_counts = {}
        for d in range(7):
            count = sum(1 for dd in days_of_week if dd == d)
            day_counts[d] = count / max(len(days_of_week), 1)

        # Extract locations and resources
        locations = list(set(a.location for a in relevant_activities))
        resources = list(set(a.resource_accessed for a in relevant_activities))
        device_fps = list(set(a.device_fingerprint for a in relevant_activities))

        # Calculate data volume statistics
        volumes = np.array([a.data_transferred_gb for a in relevant_activities])
        avg_volume = float(np.mean(volumes))
        std_volume = float(np.std(volumes))

        # Create baseline
        baseline = UserBehaviorBaseline(
            user_id=user_id,
            avg_login_time=float(np.mean(hours)),
            typical_locations=locations,
            typical_resources=resources,
            avg_data_volume=avg_volume,
            typical_login_frequency=len(relevant_activities) / max(days, 1),
            device_fingerprints=device_fps,
            login_hours_distribution=hour_counts,
            day_of_week_pattern=day_counts,
            data_volume_std=std_volume,
            location_distance_threshold=500,  # km
            max_impossible_travel_speed=self.impossible_travel_threshold
        )

        self.user_baselines[user_id] = baseline
        self.user_activity_history[user_id] = relevant_activities

        logger.info(f"Baseline established for user {user_id} from {len(relevant_activities)} activities")

    def extract_features(self, activity: UserActivity, baseline: UserBehaviorBaseline) -> Dict[str, float]:
        """
        Extract 16-dimensional feature vector from activity

        Features:
        1. Hour deviation
        2. Day-of-week deviation
        3. Location deviation (unusual location)
        4. Data volume deviation (std devs)
        5. Device fingerprint match (0-1)
        6. Resource frequency (0-1)
        7. Login time hour
        8. Login frequency (logins per day)
        9. Temporal consistency (0-1)
        10. Resource diversity (new resource factor)
        11. Geographic velocity (km/hour)
        12. Session duration deviation
        13. Connection time confidence (0-1)
        14. Behavioral normality score (0-1)
        15. Time zone consistency (0-1)
        16. Cumulative anomaly risk (0-1)
        """
        features = {}

        # 1. Hour deviation
        hour = activity.timestamp.hour
        expected_hour_prob = baseline.login_hours_distribution.get(hour, 0)
        features['hour_deviation'] = 1 - expected_hour_prob

        # 2. Day-of-week deviation
        day = activity.timestamp.weekday()
        expected_day_prob = baseline.day_of_week_pattern.get(day, 0)
        features['day_deviation'] = 1 - expected_day_prob

        # 3. Location deviation
        is_new_location = activity.location not in baseline.typical_locations
        features['location_deviation'] = 1.0 if is_new_location else 0.0

        # 4. Data volume deviation
        volume_deviation = abs(activity.data_transferred_gb - baseline.avg_data_volume)
        if baseline.data_volume_std > 0:
            features['data_volume_deviation'] = min(volume_deviation / baseline.data_volume_std, 5.0) / 5.0
        else:
            features['data_volume_deviation'] = 0.5 if is_new_location else 0.0

        # 5. Device fingerprint match
        is_known_device = activity.device_fingerprint in baseline.device_fingerprints
        features['device_match'] = 1.0 if is_known_device else 0.2

        # 6. Resource frequency
        resource_frequency = baseline.typical_resources.count(activity.resource_accessed) / max(len(baseline.typical_resources), 1)
        features['resource_frequency'] = resource_frequency

        # 7. Login time hour (normalized)
        features['login_hour'] = hour / 24.0

        # 8. Login frequency
        features['login_frequency'] = min(baseline.typical_login_frequency / 24.0, 1.0)

        # 9. Temporal consistency
        temporal_consistency = (expected_hour_prob + expected_day_prob) / 2
        features['temporal_consistency'] = temporal_consistency

        # 10. Resource diversity (new resource factor)
        is_new_resource = activity.resource_accessed not in baseline.typical_resources
        features['resource_diversity'] = 1.0 if is_new_resource else 0.1

        # 11. Geographic velocity (impossible travel check)
        velocity_risk = 0.0
        if len(self.user_activity_history.get(activity.user_id, [])) > 0:
            prev_activity = self.user_activity_history[activity.user_id][-1]
            time_diff_hours = (activity.timestamp - prev_activity.timestamp).total_seconds() / 3600
            if time_diff_hours > 0:
                # Simplified distance calculation (Haversine would be more accurate)
                lat_diff = abs(activity.latitude - prev_activity.latitude)
                lon_diff = abs(activity.longitude - prev_activity.longitude)
                distance_km = np.sqrt(lat_diff**2 + lon_diff**2) * 111  # Rough approximation
                velocity_kmh = distance_km / time_diff_hours

                if velocity_kmh > baseline.max_impossible_travel_speed:
                    velocity_risk = min(velocity_kmh / baseline.max_impossible_travel_speed, 5.0) / 5.0

        features['geographic_velocity'] = velocity_risk

        # 12. Session duration deviation
        features['session_duration'] = min(activity.duration_seconds / 3600, 1.0)  # Normalize to hours

        # 13. Connection time confidence
        hour_confidence = expected_hour_prob
        features['connection_confidence'] = hour_confidence

        # 14. Behavioral normality score
        behavioral_normality = (expected_hour_prob + expected_day_prob + resource_frequency) / 3
        features['behavioral_normality'] = behavioral_normality

        # 15. Time zone consistency
        # Simplified: check if hour matches typical login hours
        avg_hour = baseline.avg_login_time
        hour_diff = abs(hour - avg_hour)
        if hour_diff > 12:
            hour_diff = 24 - hour_diff
        features['timezone_consistency'] = 1 - (hour_diff / 12)

        # 16. Cumulative anomaly risk
        anomaly_count = sum(1 for v in features.values() if v > 0.5)
        features['cumulative_risk'] = min(anomaly_count / 16, 1.0)

        return features

    def detect_anomalies(self, activity: UserActivity, baseline: UserBehaviorBaseline) -> Tuple[List[AnomalyType], float]:
        """
        Detect specific types of anomalies

        Returns:
            Tuple of (anomaly_types, confidence)
        """
        anomalies = []
        confidence_scores = []

        # Check impossible travel
        if len(self.user_activity_history.get(activity.user_id, [])) > 0:
            prev_activity = self.user_activity_history[activity.user_id][-1]
            time_diff_hours = (activity.timestamp - prev_activity.timestamp).total_seconds() / 3600

            if time_diff_hours > 0:
                lat_diff = abs(activity.latitude - prev_activity.latitude)
                lon_diff = abs(activity.longitude - prev_activity.longitude)
                distance_km = np.sqrt(lat_diff**2 + lon_diff**2) * 111
                velocity_kmh = distance_km / time_diff_hours

                if velocity_kmh > baseline.max_impossible_travel_speed:
                    anomalies.append(AnomalyType.IMPOSSIBLE_TRAVEL)
                    confidence_scores.append(min(velocity_kmh / baseline.max_impossible_travel_speed, 1.0))

        # Check unusual time
        hour = activity.timestamp.hour
        hour_prob = baseline.login_hours_distribution.get(hour, 0)
        if hour_prob < 0.1:
            anomalies.append(AnomalyType.UNUSUAL_TIME)
            confidence_scores.append(1 - hour_prob)

        # Check unusual volume
        volume_deviation = abs(activity.data_transferred_gb - baseline.avg_data_volume)
        if baseline.data_volume_std > 0 and volume_deviation > 3 * baseline.data_volume_std:
            anomalies.append(AnomalyType.UNUSUAL_VOLUME)
            confidence_scores.append(min(volume_deviation / (3 * baseline.data_volume_std), 1.0))

        # Check unusual resources
        if activity.resource_accessed not in baseline.typical_resources:
            anomalies.append(AnomalyType.UNUSUAL_RESOURCES)
            confidence_scores.append(0.7)

        avg_confidence = np.mean(confidence_scores) if confidence_scores else 0.0

        return anomalies, float(avg_confidence)

    def predict_threat(self, activity: UserActivity) -> ThreatScore:
        """
        Comprehensive threat detection for a single activity

        Returns:
            ThreatScore with detailed threat assessment
        """
        if activity.user_id not in self.user_baselines:
            logger.warning(f"No baseline for user {activity.user_id}")
            return self._create_baseline_threat_score(activity)

        baseline = self.user_baselines[activity.user_id]

        # Extract features
        features = self.extract_features(activity, baseline)
        feature_array = np.array([list(features.values())])

        # Detect specific anomalies
        anomalies, anomaly_confidence = self.detect_anomalies(activity, baseline)

        # Get scores from each detector
        if_score = self.isolation_forest.predict_anomaly_score(feature_array)[0]
        lstm_score = self.lstm_autoencoder.predict_anomaly_score(
            self._create_sequence(activity, activity.user_id)
        )[0] if len(self.user_activity_history.get(activity.user_id, [])) >= 24 else 0
        xgb_score = self.xgboost_ensemble.predict_threat_probability(feature_array)[0] * 100

        # Ensemble combination (weighted average)
        threat_score = (if_score * 0.35 + lstm_score * 0.35 + xgb_score * 0.30)
        threat_score = float(np.clip(threat_score, 0, 100))

        # Determine threat level
        if threat_score >= 80:
            threat_level = ThreatLevel.CRITICAL
        elif threat_score >= 50:
            threat_level = ThreatLevel.HIGH
        elif threat_score >= 20:
            threat_level = ThreatLevel.MEDIUM
        else:
            threat_level = ThreatLevel.LOW

        # Generate recommendations
        recommendations = self._generate_recommendations(
            threat_level, anomalies, threat_score
        )

        # Create explanation
        explanation = self._create_explanation(
            threat_score, if_score, lstm_score, xgb_score, anomalies
        )

        # Store activity
        if activity.user_id not in self.user_activity_history:
            self.user_activity_history[activity.user_id] = []
        self.user_activity_history[activity.user_id].append(activity)

        # Create threat score
        result = ThreatScore(
            user_id=activity.user_id,
            timestamp=activity.timestamp,
            threat_score=threat_score,
            threat_level=threat_level,
            primary_anomalies=anomalies,
            confidence=float(np.clip(anomaly_confidence, 0, 1)),
            isolation_forest_score=float(if_score),
            lstm_autoencoder_score=float(lstm_score),
            xgboost_ensemble_score=float(xgb_score),
            impossible_travel_detected=AnomalyType.IMPOSSIBLE_TRAVEL in anomalies,
            unusual_time_detected=AnomalyType.UNUSUAL_TIME in anomalies,
            unusual_volume_detected=AnomalyType.UNUSUAL_VOLUME in anomalies,
            unusual_resources_detected=AnomalyType.UNUSUAL_RESOURCES in anomalies,
            behavioral_deviation_score=float(np.mean([
                features.get('location_deviation', 0),
                features.get('device_match', 1) - 1,
                features.get('resource_diversity', 0)
            ])),
            recommended_actions=recommendations,
            explanation=explanation
        )

        # Store in history
        if activity.user_id not in self.threat_history:
            self.threat_history[activity.user_id] = []
        self.threat_history[activity.user_id].append(result)

        return result

    def _create_sequence(self, activity: UserActivity, user_id: str) -> np.ndarray:
        """Create activity sequence for LSTM input"""
        activities = self.user_activity_history.get(user_id, [])
        if len(activities) < 24:
            # Pad with zeros
            sequence = np.zeros((24, 8))
            for i, act in enumerate(activities[-24:]):
                sequence[i] = [
                    act.timestamp.hour / 24,
                    act.timestamp.weekday() / 7,
                    act.data_transferred_gb / 100,  # Normalize
                    act.latitude / 90,
                    act.longitude / 180,
                    1.0 if act.device_fingerprint == activity.device_fingerprint else 0.0,
                    1.0 if act.resource_accessed == activity.resource_accessed else 0.0,
                    act.duration_seconds / 3600
                ]
        else:
            sequence = np.zeros((24, 8))
            for i, act in enumerate(activities[-24:]):
                sequence[i] = [
                    act.timestamp.hour / 24,
                    act.timestamp.weekday() / 7,
                    act.data_transferred_gb / 100,
                    act.latitude / 90,
                    act.longitude / 180,
                    1.0 if act.device_fingerprint == activity.device_fingerprint else 0.0,
                    1.0 if act.resource_accessed == activity.resource_accessed else 0.0,
                    act.duration_seconds / 3600
                ]

        return sequence.reshape(1, 24, 8)

    def _generate_recommendations(self, threat_level: ThreatLevel,
                                 anomalies: List[AnomalyType],
                                 threat_score: float) -> List[str]:
        """Generate recommended actions based on threat assessment"""
        recommendations = []

        if threat_level == ThreatLevel.CRITICAL:
            recommendations.extend([
                "Immediately block user session",
                "Trigger multi-factor authentication challenge",
                "Alert security team for immediate investigation",
                "Revoke active sessions",
                "Require password reset"
            ])
        elif threat_level == ThreatLevel.HIGH:
            recommendations.extend([
                "Require multi-factor authentication",
                "Request identity verification",
                "Log detailed session information",
                "Monitor subsequent activities closely"
            ])
        elif threat_level == ThreatLevel.MEDIUM:
            recommendations.extend([
                "Request additional verification if accessing sensitive resources",
                "Log activity for review",
                "Monitor behavioral patterns"
            ])
        else:
            recommendations.append("Allow login with standard monitoring")

        if AnomalyType.IMPOSSIBLE_TRAVEL in anomalies:
            recommendations.append("Geographic velocity check failed - verify travel legitimacy")
        if AnomalyType.UNUSUAL_TIME in anomalies:
            recommendations.append("Unusual login time - verify user schedule")
        if AnomalyType.UNUSUAL_VOLUME in anomalies:
            recommendations.append("Unusual data access volume - review accessed resources")
        if AnomalyType.UNUSUAL_RESOURCES in anomalies:
            recommendations.append("Accessing unfamiliar resources - verify intent")

        return recommendations

    def _create_explanation(self, overall_score: float, if_score: float,
                          lstm_score: float, xgb_score: float,
                          anomalies: List[AnomalyType]) -> str:
        """Create human-readable threat explanation"""
        parts = [
            f"Overall Threat Score: {overall_score:.1f}/100",
            f"Component Scores: IF={if_score:.1f}, LSTM={lstm_score:.1f}, XGB={xgb_score:.1f}",
        ]

        if anomalies:
            anomaly_names = ", ".join([a.value for a in anomalies])
            parts.append(f"Detected Anomalies: {anomaly_names}")
        else:
            parts.append("No specific anomalies detected")

        return " | ".join(parts)

    def _create_baseline_threat_score(self, activity: UserActivity) -> ThreatScore:
        """Create baseline threat score when no baseline exists"""
        return ThreatScore(
            user_id=activity.user_id,
            timestamp=activity.timestamp,
            threat_score=30.0,  # Medium by default
            threat_level=ThreatLevel.MEDIUM,
            primary_anomalies=[],
            confidence=0.0,
            isolation_forest_score=0.0,
            lstm_autoencoder_score=0.0,
            xgboost_ensemble_score=0.0,
            impossible_travel_detected=False,
            unusual_time_detected=False,
            unusual_volume_detected=False,
            unusual_resources_detected=False,
            behavioral_deviation_score=0.0,
            recommended_actions=["Establish user baseline", "Collect 30 days of activity data"],
            explanation="No baseline available - insufficient data for threat assessment"
        )


def create_hybrid_threat_detector() -> HybridThreatDetector:
    """Factory function to create and configure threat detector"""
    detector = HybridThreatDetector()
    logger.info("Hybrid Threat Detector initialized")
    return detector
