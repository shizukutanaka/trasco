#!/usr/bin/env python3
"""
Phase 7H: ML Models for Advanced Analytics
Implements:
- Predictive Failure Forecasting (Prophet)
- Anomaly Detection (Ensemble: Isolation Forest + LSTM + Statistical)
- Root Cause Analysis (Random Forest)
- Log Correlation (DBSCAN clustering)
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Any
import warnings
warnings.filterwarnings('ignore')

# ML Libraries
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import DBSCAN
from sklearn.feature_extraction.text import TfidfVectorizer
from scipy import stats
import joblib
import pickle

try:
    from prophet import Prophet
    HAS_PROPHET = True
except ImportError:
    HAS_PROPHET = False
    print("Warning: Prophet not installed. Install with: pip install prophet")

try:
    import tensorflow as tf
    from tensorflow.keras import Sequential
    from tensorflow.keras.layers import LSTM, RepeatVector, TimeDistributed, Dense
    HAS_TENSORFLOW = True
except ImportError:
    HAS_TENSORFLOW = False
    print("Warning: TensorFlow not installed. Install with: pip install tensorflow")


###############################################################################
# 1. PREDICTIVE FAILURE FORECASTING (PROPHET)
###############################################################################

class FailurePredictor:
    """Predict infrastructure failures 1-7 days in advance"""

    def __init__(self, metric_name: str = "metric"):
        self.metric_name = metric_name
        self.model = None
        self.scaler = StandardScaler()
        self.fitted = False

    def train(self, timestamps: np.ndarray, values: np.ndarray,
              regressors: Dict[str, np.ndarray] = None):
        """
        Train Prophet model on historical data

        Args:
            timestamps: Unix timestamps
            values: Metric values
            regressors: Optional external regressors (CPU, memory, etc)
        """
        if not HAS_PROPHET:
            raise ImportError("Prophet required: pip install prophet")

        # Prepare data
        df = pd.DataFrame({
            'ds': pd.to_datetime(timestamps, unit='s'),
            'y': values
        })

        # Add regressors if provided
        if regressors:
            for name, data in regressors.items():
                df[name] = data

        # Initialize and fit model
        self.model = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=True,
            daily_seasonality=True,
            interval_width=0.95,
            changepoint_prior_scale=0.05,
            seasonality_prior_scale=10
        )

        if regressors:
            for name in regressors.keys():
                self.model.add_regressor(name)

        self.model.fit(df)
        self.fitted = True

        print(f"✓ Prophet model trained for {self.metric_name}")
        return self

    def predict(self, days_ahead: int = 7,
               regressors: Dict[str, np.ndarray] = None) -> Dict[str, Any]:
        """
        Forecast metric value for next N days

        Args:
            days_ahead: Days to forecast (1-7)
            regressors: Optional external regressors

        Returns:
            Dict with forecast, confidence intervals, and anomaly info
        """
        if not self.fitted or self.model is None:
            raise ValueError("Model not fitted. Call train() first.")

        # Create future dataframe
        future = self.model.make_future_dataframe(periods=days_ahead)

        # Add regressors if provided
        if regressors:
            for name, data in regressors.items():
                future[name] = np.concatenate([
                    np.zeros(len(future) - len(data)),
                    data
                ])

        # Get forecast
        forecast = self.model.predict(future)

        # Extract last N days
        forecast = forecast.tail(days_ahead)

        return {
            'timestamps': forecast['ds'].values,
            'forecast': forecast['yhat'].values,
            'lower_bound': forecast['yhat_lower'].values,
            'upper_bound': forecast['yhat_upper'].values,
            'trend': forecast['trend'].values,
            'metric': self.metric_name
        }

    def save(self, filepath: str):
        """Save model to file"""
        with open(filepath, 'wb') as f:
            pickle.dump(self.model, f)

    def load(self, filepath: str):
        """Load model from file"""
        with open(filepath, 'rb') as f:
            self.model = pickle.load(f)
        self.fitted = True


###############################################################################
# 2. ANOMALY DETECTION (ENSEMBLE)
###############################################################################

class AnomalyDetectionEnsemble:
    """Multi-algorithm ensemble for anomaly detection"""

    def __init__(self, contamination: float = 0.05):
        """
        Initialize ensemble

        Args:
            contamination: Expected anomaly rate (0-1)
        """
        self.contamination = contamination
        self.iso_forest = IsolationForest(
            contamination=contamination,
            random_state=42
        )
        self.scaler = StandardScaler()
        self.lstm_model = None
        self.fitted = False

    def train(self, X: np.ndarray, window_size: int = 100):
        """
        Train ensemble on normal data

        Args:
            X: Training data (shape: n_samples, n_features)
            window_size: Window size for LSTM
        """
        # Fit Isolation Forest
        self.iso_forest.fit(X)

        # Scale data
        X_scaled = self.scaler.fit_transform(X)

        # Train LSTM if available
        if HAS_TENSORFLOW and len(X) >= window_size * 2:
            self._build_and_train_lstm(X_scaled, window_size)

        self.fitted = True
        print("✓ Anomaly Detection Ensemble trained")
        return self

    def _build_and_train_lstm(self, X_scaled: np.ndarray, window_size: int):
        """Build and train LSTM autoencoder"""
        self.lstm_model = Sequential([
            LSTM(64, activation='relu', input_shape=(window_size, X_scaled.shape[1])),
            RepeatVector(window_size),
            LSTM(64, activation='relu', return_sequences=True),
            TimeDistributed(Dense(X_scaled.shape[1]))
        ])
        self.lstm_model.compile(optimizer='adam', loss='mse', verbose=0)

        # Prepare sequences
        X_train = []
        for i in range(len(X_scaled) - window_size):
            X_train.append(X_scaled[i:i+window_size])
        X_train = np.array(X_train)

        # Train with early stopping
        self.lstm_model.fit(
            X_train, X_train,
            epochs=50,
            batch_size=32,
            validation_split=0.1,
            verbose=0
        )

    def detect(self, X: np.ndarray, window_size: int = 100) -> Dict[str, Any]:
        """
        Detect anomalies using ensemble

        Args:
            X: Input data (shape: n_samples, n_features)
            window_size: Window size for LSTM

        Returns:
            Dict with anomaly scores, flags, and confidence
        """
        if not self.fitted:
            raise ValueError("Model not fitted. Call train() first.")

        # Score 1: Isolation Forest
        iso_scores = self.iso_forest.decision_function(X)

        # Score 2: LSTM (if available)
        lstm_scores = None
        if self.lstm_model is not None:
            X_scaled = self.scaler.transform(X)
            X_sequences = []
            for i in range(len(X_scaled) - window_size + 1):
                X_sequences.append(X_scaled[i:i+window_size])

            if len(X_sequences) > 0:
                X_sequences = np.array(X_sequences)
                lstm_pred = self.lstm_model.predict(X_sequences, verbose=0)
                lstm_scores = np.mean(
                    (X_sequences - lstm_pred) ** 2,
                    axis=(1, 2)
                )

        # Score 3: Statistical (Z-score)
        z_scores = np.abs(
            (X - np.mean(X, axis=0)) / (np.std(X, axis=0) + 1e-6)
        )
        z_scores = np.mean(z_scores, axis=1)

        # Normalize scores
        iso_norm = self._normalize(iso_scores)
        lstm_norm = self._normalize(lstm_scores) if lstm_scores is not None else None
        z_norm = self._normalize(z_scores)

        # Ensemble: Weighted voting
        if lstm_norm is not None:
            ensemble_score = (0.3 * iso_norm + 0.4 * lstm_norm + 0.3 * z_norm)
        else:
            ensemble_score = (0.5 * iso_norm + 0.5 * z_norm)

        # Adaptive threshold
        threshold = np.mean(ensemble_score) + 2 * np.std(ensemble_score)
        is_anomaly = ensemble_score > threshold

        return {
            'is_anomaly': is_anomaly,
            'anomaly_score': ensemble_score,
            'threshold': threshold,
            'iso_forest_score': iso_scores,
            'z_score': z_scores,
            'confidence': np.mean(ensemble_score[is_anomaly]) if np.any(is_anomaly) else 0
        }

    def _normalize(self, scores: np.ndarray) -> np.ndarray:
        """Normalize scores to [0, 1]"""
        if scores is None:
            return None
        min_val = np.min(scores)
        max_val = np.max(scores)
        if max_val == min_val:
            return np.zeros_like(scores)
        return (scores - min_val) / (max_val - min_val)

    def save(self, filepath: str):
        """Save model"""
        models = {
            'iso_forest': self.iso_forest,
            'scaler': self.scaler,
            'lstm_model': self.lstm_model,
            'fitted': self.fitted
        }
        joblib.dump(models, filepath)

    def load(self, filepath: str):
        """Load model"""
        models = joblib.load(filepath)
        self.iso_forest = models['iso_forest']
        self.scaler = models['scaler']
        self.lstm_model = models['lstm_model']
        self.fitted = models['fitted']


###############################################################################
# 3. ROOT CAUSE ANALYSIS (RANDOM FOREST)
###############################################################################

class RootCauseAnalyzer:
    """Classify root cause of incidents using ML"""

    def __init__(self):
        self.model = RandomForestClassifier(
            n_estimators=100,
            max_depth=15,
            min_samples_split=10,
            random_state=42
        )
        self.scaler = StandardScaler()
        self.feature_names = None
        self.class_names = None
        self.fitted = False

    def train(self, X: np.ndarray, y: np.ndarray,
             feature_names: List[str] = None,
             class_names: List[str] = None):
        """
        Train random forest classifier

        Args:
            X: Features (n_samples, n_features)
            y: Root cause labels (n_samples,)
            feature_names: Feature names
            class_names: Root cause class names
        """
        # Scale features
        X_scaled = self.scaler.fit_transform(X)

        # Train model
        self.model.fit(X_scaled, y)

        self.feature_names = feature_names or [f"feature_{i}" for i in range(X.shape[1])]
        self.class_names = class_names or list(set(y))
        self.fitted = True

        print(f"✓ Root Cause Analyzer trained ({len(self.class_names)} classes)")
        return self

    def predict(self, X: np.ndarray) -> Dict[str, Any]:
        """
        Predict root cause

        Args:
            X: Features (n_samples, n_features)

        Returns:
            Dict with predictions, confidence, and feature importance
        """
        if not self.fitted:
            raise ValueError("Model not fitted. Call train() first.")

        X_scaled = self.scaler.transform(X)
        predictions = self.model.predict(X_scaled)
        probabilities = self.model.predict_proba(X_scaled)

        return {
            'root_cause': predictions,
            'confidence': np.max(probabilities, axis=1),
            'probabilities': probabilities,
            'classes': self.class_names,
            'feature_importance': dict(zip(
                self.feature_names,
                self.model.feature_importances_
            ))
        }

    def save(self, filepath: str):
        """Save model"""
        models = {
            'model': self.model,
            'scaler': self.scaler,
            'feature_names': self.feature_names,
            'class_names': self.class_names,
            'fitted': self.fitted
        }
        joblib.dump(models, filepath)

    def load(self, filepath: str):
        """Load model"""
        models = joblib.load(filepath)
        self.model = models['model']
        self.scaler = models['scaler']
        self.feature_names = models['feature_names']
        self.class_names = models['class_names']
        self.fitted = models['fitted']


###############################################################################
# 4. LOG CORRELATION (CLUSTERING)
###############################################################################

class LogCorrelator:
    """Cluster and correlate similar logs"""

    def __init__(self, eps: float = 0.1, min_samples: int = 5):
        self.vectorizer = TfidfVectorizer(
            analyzer='char',
            ngram_range=(2, 3),
            max_features=1000
        )
        self.clusterer = DBSCAN(eps=eps, min_samples=min_samples)
        self.fitted = False

    def fit(self, logs: List[str]):
        """
        Fit clustering on log corpus

        Args:
            logs: List of log strings
        """
        # Vectorize logs
        X = self.vectorizer.fit_transform(logs)

        # Fit clustering
        self.clusterer.fit(X.toarray())

        self.fitted = True
        print(f"✓ Log Correlator fitted")
        return self

    def cluster(self, logs: List[str]) -> Dict[int, List[str]]:
        """
        Cluster logs

        Args:
            logs: List of log strings

        Returns:
            Dict mapping cluster_id to list of logs
        """
        if not self.fitted:
            self.fit(logs)

        # Vectorize logs
        X = self.vectorizer.transform(logs)

        # Get clustering labels
        labels = self.clusterer.fit_predict(X.toarray())

        # Group logs by cluster
        clusters = {}
        for log, label in zip(logs, labels):
            if label not in clusters:
                clusters[label] = []
            clusters[label].append(log)

        return clusters

    def get_common_patterns(self, cluster_logs: List[str]) -> Dict[str, Any]:
        """
        Extract common patterns from cluster

        Args:
            cluster_logs: List of logs in cluster

        Returns:
            Dict with patterns and frequency
        """
        if len(cluster_logs) < 2:
            return {}

        # Simple pattern extraction: common substrings
        patterns = {}

        # Extract words
        all_words = []
        for log in cluster_logs:
            words = log.lower().split()
            all_words.extend(words)

        # Count frequencies
        from collections import Counter
        word_freq = Counter(all_words)

        # Get top words as patterns
        patterns = {
            word: count
            for word, count in word_freq.most_common(10)
        }

        return patterns

    def save(self, filepath: str):
        """Save model"""
        models = {
            'vectorizer': self.vectorizer,
            'clusterer': self.clusterer,
            'fitted': self.fitted
        }
        joblib.dump(models, filepath)

    def load(self, filepath: str):
        """Load model"""
        models = joblib.load(filepath)
        self.vectorizer = models['vectorizer']
        self.clusterer = models['clusterer']
        self.fitted = models['fitted']


###############################################################################
# EXAMPLE USAGE & TESTING
###############################################################################

def example_usage():
    """Demonstrate model usage"""
    print("\n" + "="*60)
    print("Phase 7H: ML Models Example Usage")
    print("="*60 + "\n")

    # 1. Failure Prediction
    print("1. FAILURE PREDICTION")
    print("-" * 60)

    if HAS_PROPHET:
        # Generate synthetic data
        dates = pd.date_range(start='2024-01-01', periods=365, freq='D')
        trend = np.linspace(50, 80, 365)
        seasonality = 20 * np.sin(2 * np.pi * np.arange(365) / 365)
        noise = np.random.normal(0, 5, 365)
        values = trend + seasonality + noise

        # Train
        predictor = FailurePredictor("disk_io_utilization")
        predictor.train(
            dates.astype(int) // 10**9,
            values
        )

        # Predict
        forecast = predictor.predict(days_ahead=7)
        print(f"✓ Predicted next 7 days: {forecast['forecast'][:3]}...")
    else:
        print("⚠ Prophet not available")

    # 2. Anomaly Detection
    print("\n2. ANOMALY DETECTION")
    print("-" * 60)

    # Generate synthetic normal + anomalous data
    normal_data = np.random.normal(100, 10, (1000, 5))
    test_data = np.vstack([
        normal_data[-100:],
        np.random.normal(200, 50, (10, 5))  # anomalies
    ])

    detector = AnomalyDetectionEnsemble()
    detector.train(normal_data)
    results = detector.detect(test_data)

    anomalies = np.sum(results['is_anomaly'])
    print(f"✓ Detected {anomalies} anomalies in {len(test_data)} samples")

    # 3. Root Cause Analysis
    print("\n3. ROOT CAUSE ANALYSIS")
    print("-" * 60)

    # Generate synthetic incident data
    X_train = np.random.randn(500, 8)
    y_train = np.random.choice(['database', 'network', 'cpu', 'memory'], 500)

    analyzer = RootCauseAnalyzer()
    analyzer.train(
        X_train, y_train,
        feature_names=['error_rate', 'latency', 'cpu', 'memory', 'disk', 'network', 'connection_pool', 'query_time'],
        class_names=['database', 'network', 'cpu', 'memory']
    )

    X_test = np.random.randn(10, 8)
    predictions = analyzer.predict(X_test)
    print(f"✓ Predicted root causes: {predictions['root_cause'][:5]}")

    # 4. Log Correlation
    print("\n4. LOG CORRELATION")
    print("-" * 60)

    logs = [
        "ERROR: Database connection timeout after 30s",
        "ERROR: Database connection timeout after 35s",
        "ERROR: Database query execution failed",
        "ERROR: API gateway request timeout",
        "WARN: High latency detected on API gateway",
    ]

    correlator = LogCorrelator()
    clusters = correlator.cluster(logs)
    print(f"✓ Grouped {len(logs)} logs into {len(clusters)} clusters")

    print("\n" + "="*60)


if __name__ == "__main__":
    example_usage()
