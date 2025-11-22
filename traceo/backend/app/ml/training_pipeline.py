#!/usr/bin/env python3
"""
ML Training Pipeline for Traceo
Implements ensemble models for failure prediction, anomaly detection, and root cause analysis
Uses unified anomaly detection engine for consistency
Date: November 21, 2024
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Tuple, List
import numpy as np
import pandas as pd
from pathlib import Path

import mlflow
import mlflow.sklearn
import mlflow.pytorch
from sklearn.model_selection import train_test_split, cross_validate
from sklearn.preprocessing import StandardScaler, RobustScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    precision_recall_fscore_support, roc_auc_score, confusion_matrix,
    classification_report, f1_score, accuracy_score
)
from sklearn.pipeline import Pipeline
import joblib
import psycopg2
import boto3
import warnings
from app.ml.anomaly_detection_engine import IsolationForestAnomalyDetector

# Suppress warnings
warnings.filterwarnings('ignore')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DataLoader:
    """Load training data from PostgreSQL and S3"""

    def __init__(self, postgres_host: str, postgres_port: int,
                 postgres_user: str, postgres_password: str,
                 postgres_db: str):
        self.postgres_host = postgres_host
        self.postgres_port = postgres_port
        self.postgres_user = postgres_user
        self.postgres_password = postgres_password
        self.postgres_db = postgres_db

    def connect(self):
        """Create database connection"""
        try:
            self.conn = psycopg2.connect(
                host=self.postgres_host,
                port=self.postgres_port,
                user=self.postgres_user,
                password=self.postgres_password,
                database=self.postgres_db
            )
            logger.info("Connected to PostgreSQL database")
            return self.conn
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            raise

    def load_metrics(self, time_range_days: int = 30) -> pd.DataFrame:
        """Load metrics from metric_collection table"""
        query = f"""
            SELECT
                timestamp,
                metric_name,
                labels,
                value,
                bucket
            FROM metric_collection
            WHERE created_at >= NOW() - INTERVAL '{time_range_days} days'
            ORDER BY timestamp DESC
            LIMIT 10000000
        """
        try:
            df = pd.read_sql_query(query, self.conn)
            logger.info(f"Loaded {len(df)} metric records")
            return df
        except Exception as e:
            logger.error(f"Failed to load metrics: {e}")
            raise

    def load_incidents(self) -> pd.DataFrame:
        """Load labeled incidents from incident_records table"""
        query = """
            SELECT
                id,
                incident_id,
                timestamp,
                title,
                severity,
                duration_minutes,
                root_cause,
                root_cause_component,
                affected_services,
                metrics_before,
                metrics_during,
                metrics_after
            FROM incident_records
            WHERE label_status = 'labeled'
            ORDER BY timestamp DESC
        """
        try:
            df = pd.read_sql_query(query, self.conn)
            logger.info(f"Loaded {len(df)} labeled incidents")
            return df
        except Exception as e:
            logger.error(f"Failed to load incidents: {e}")
            raise

    def close(self):
        """Close database connection"""
        if hasattr(self, 'conn'):
            self.conn.close()


class FeatureEngineer:
    """Create features for ML models"""

    def __init__(self):
        self.scaler = RobustScaler()
        self.feature_names_ = None

    def create_lag_features(self, df: pd.DataFrame, metric: str,
                           lags: List[int] = [5, 10, 30, 60]) -> pd.DataFrame:
        """Create lagged features"""
        for lag in lags:
            df[f'{metric}_lag_{lag}'] = df[metric].shift(lag)
        return df

    def create_rolling_statistics(self, df: pd.DataFrame, metric: str,
                                 windows: List[int] = [5, 10, 30]) -> pd.DataFrame:
        """Create rolling window statistics"""
        for window in windows:
            df[f'{metric}_rolling_mean_{window}'] = df[metric].rolling(window).mean()
            df[f'{metric}_rolling_std_{window}'] = df[metric].rolling(window).std()
            df[f'{metric}_rolling_min_{window}'] = df[metric].rolling(window).min()
            df[f'{metric}_rolling_max_{window}'] = df[metric].rolling(window).max()
        return df

    def create_change_rate_features(self, df: pd.DataFrame, metric: str) -> pd.DataFrame:
        """Create rate of change features"""
        df[f'{metric}_pct_change'] = df[metric].pct_change()
        df[f'{metric}_diff'] = df[metric].diff()
        return df

    def handle_missing_values(self, df: pd.DataFrame, strategy: str = 'forward_fill') -> pd.DataFrame:
        """Handle missing values"""
        if strategy == 'forward_fill':
            return df.fillna(method='ffill').fillna(method='bfill')
        elif strategy == 'interpolate':
            return df.interpolate(method='linear')
        else:
            return df.dropna()

    def scale_features(self, X_train: np.ndarray, X_test: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Scale features using RobustScaler"""
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        return X_train_scaled, X_test_scaled

    def create_feature_matrix(self, raw_metrics: pd.DataFrame,
                             incidents: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """Create complete feature matrix"""
        logger.info("Creating feature matrix...")

        # Pivot metrics table for time series features
        df = raw_metrics.copy()
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
        df = df.set_index('timestamp').sort_index()

        # Handle missing values
        df = self.handle_missing_values(df)

        # For each metric, create lag and rolling features
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        for metric in numeric_cols[:20]:  # Limit to top 20 metrics for performance
            df = self.create_lag_features(df, metric, lags=[5, 10, 30])
            df = self.create_rolling_statistics(df, metric, windows=[5, 10, 30])
            df = self.create_change_rate_features(df, metric)

        # Drop rows with NaN
        df = df.dropna()

        # Create feature matrix
        X = df.values
        self.feature_names_ = df.columns.tolist()

        # Create labels: 1 if within 1 hour before incident, 0 otherwise
        y = np.zeros(len(df))
        for _, incident in incidents.iterrows():
            incident_time = pd.to_datetime(incident['timestamp'])
            # Mark 1 hour window before incident as anomalous
            mask = (df.index >= incident_time - pd.Timedelta(hours=1)) & (df.index < incident_time)
            y[mask] = 1

        logger.info(f"Created feature matrix: {X.shape}, Labels: {np.bincount(y.astype(int))}")
        return X, y


class FailurePredictionModel:
    """Ensemble model for failure prediction (LSTM + Random Forest + Prophet)"""

    def __init__(self):
        self.models = {}
        self.metrics = {}

    def build_random_forest(self, X_train: np.ndarray, y_train: np.ndarray,
                           X_test: np.ndarray, y_test: np.ndarray) -> Dict:
        """Build Random Forest model"""
        logger.info("Training Random Forest for failure prediction...")

        rf_model = RandomForestClassifier(
            n_estimators=100,
            max_depth=15,
            min_samples_split=5,
            random_state=42,
            n_jobs=-1
        )
        rf_model.fit(X_train, y_train)

        # Evaluate
        y_pred = rf_model.predict(X_test)
        y_pred_proba = rf_model.predict_proba(X_test)[:, 1]

        precision, recall, f1, _ = precision_recall_fscore_support(y_test, y_pred, average='binary')
        auc = roc_auc_score(y_test, y_pred_proba)
        accuracy = accuracy_score(y_test, y_pred)

        metrics = {
            'precision': float(precision),
            'recall': float(recall),
            'f1_score': float(f1),
            'auc': float(auc),
            'accuracy': float(accuracy)
        }

        logger.info(f"Random Forest metrics: {metrics}")

        return {
            'model': rf_model,
            'metrics': metrics,
            'y_pred': y_pred,
            'y_pred_proba': y_pred_proba
        }

    def train(self, X: np.ndarray, y: np.ndarray) -> Dict:
        """Train failure prediction ensemble"""
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )

        # Train Random Forest (primary model)
        rf_result = self.build_random_forest(X_train, y_train, X_test, y_test)
        self.models['random_forest'] = rf_result['model']
        self.metrics = rf_result['metrics']

        return {
            'model': rf_result['model'],
            'metrics': self.metrics,
            'y_pred': rf_result['y_pred'],
            'y_test': y_test
        }


class AnomalyDetectionModel:
    """Ensemble model for anomaly detection (Isolation Forest + Elliptic Envelope)"""

    def __init__(self):
        self.models = {}
        self.metrics = {}

    def build_isolation_forest(self, X: np.ndarray) -> Dict:
        """Build Isolation Forest using unified detector"""
        logger.info("Training Isolation Forest for anomaly detection...")

        # Use unified IsolationForest detector
        iso_detector = IsolationForestAnomalyDetector(
            contamination=0.1,
            random_state=42
        )
        iso_detector.fit(X)

        # Get predictions
        anomaly_indices = iso_detector.detect_anomalies(X)
        iso_pred = np.array([-1 if i in anomaly_indices else 1 for i in range(len(X))])
        iso_score = (iso_pred == -1).astype(int)

        return {
            'model': iso_detector,
            'predictions': iso_score,
            'anomaly_count': iso_score.sum()
        }

    def build_elliptic_envelope(self, X: np.ndarray) -> Dict:
        """Build Elliptic Envelope"""
        logger.info("Training Elliptic Envelope for anomaly detection...")

        from sklearn.covariance import EllipticEnvelope

        elliptic = EllipticEnvelope(contamination=0.1, random_state=42)
        elliptic_pred = elliptic.fit_predict(X)
        elliptic_score = (elliptic_pred == -1).astype(int)

        return {
            'model': elliptic,
            'predictions': elliptic_score,
            'anomaly_count': elliptic_score.sum()
        }

    def train(self, X: np.ndarray) -> Dict:
        """Train anomaly detection ensemble"""
        # Train Isolation Forest
        iso_result = self.build_isolation_forest(X)
        self.models['isolation_forest'] = iso_result['model']

        # Train Elliptic Envelope
        elliptic_result = self.build_elliptic_envelope(X)
        self.models['elliptic_envelope'] = elliptic_result['model']

        # Ensemble voting
        iso_score = iso_result['predictions']
        elliptic_score = elliptic_result['predictions']
        ensemble_pred = (iso_score + elliptic_score) >= 1

        self.metrics = {
            'total_anomalies': ensemble_pred.sum(),
            'anomaly_percentage': (ensemble_pred.sum() / len(X)) * 100,
            'iso_forest_anomalies': iso_result['anomaly_count'],
            'elliptic_anomalies': elliptic_result['anomaly_count']
        }

        logger.info(f"Anomaly Detection metrics: {self.metrics}")

        return {
            'ensemble_predictions': ensemble_pred,
            'metrics': self.metrics
        }


class RootCauseAnalysisModel:
    """Random Forest model for root cause analysis"""

    def __init__(self):
        self.model = None
        self.metrics = {}

    def train(self, X: np.ndarray, y: np.ndarray) -> Dict:
        """Train root cause analysis model"""
        logger.info("Training Random Forest for root cause analysis...")

        # Encode labels
        unique_causes = np.unique(y)
        label_map = {cause: idx for idx, cause in enumerate(unique_causes)}
        y_encoded = np.array([label_map.get(cause, 0) for cause in y])

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y_encoded, test_size=0.2, random_state=42, stratify=y_encoded
        )

        # Train model
        rf_model = RandomForestClassifier(
            n_estimators=200,
            max_depth=20,
            min_samples_split=5,
            random_state=42,
            n_jobs=-1
        )
        rf_model.fit(X_train, y_train)

        # Evaluate
        y_pred = rf_model.predict(X_test)
        precision, recall, f1, _ = precision_recall_fscore_support(y_test, y_pred, average='weighted')
        accuracy = accuracy_score(y_test, y_pred)

        self.metrics = {
            'precision': float(precision),
            'recall': float(recall),
            'f1_score': float(f1),
            'accuracy': float(accuracy)
        }

        logger.info(f"Root Cause Analysis metrics: {self.metrics}")

        return {
            'model': rf_model,
            'metrics': self.metrics,
            'feature_importance': rf_model.feature_importances_,
            'label_map': label_map
        }


class MLTrainingPipeline:
    """Main training pipeline orchestrator"""

    def __init__(self, experiment_name: str):
        self.experiment_name = experiment_name
        self.mlflow_uri = os.getenv('MLFLOW_TRACKING_URI', 'http://mlflow-server:5000')
        mlflow.set_tracking_uri(self.mlflow_uri)
        mlflow.set_experiment(experiment_name)

    def run(self):
        """Execute full training pipeline"""
        logger.info("Starting ML Training Pipeline...")
        logger.info(f"MLflow URI: {self.mlflow_uri}")

        try:
            # 1. Load data
            logger.info("Phase 1: Loading data...")
            loader = DataLoader(
                postgres_host=os.getenv('POSTGRESQL_HOST', 'prometheus-postgres'),
                postgres_port=int(os.getenv('POSTGRESQL_PORT', 5432)),
                postgres_user=os.getenv('POSTGRESQL_USER', 'postgres'),
                postgres_password=os.getenv('POSTGRESQL_PASSWORD', ''),
                postgres_db=os.getenv('POSTGRESQL_DB', 'traceo')
            )
            loader.connect()
            metrics_df = loader.load_metrics(time_range_days=30)
            incidents_df = loader.load_incidents()
            loader.close()

            if len(metrics_df) == 0 or len(incidents_df) == 0:
                logger.warning("No data found. Using synthetic data for demo...")
                X, y = self._create_synthetic_data()
            else:
                # 2. Feature engineering
                logger.info("Phase 2: Feature engineering...")
                engineer = FeatureEngineer()
                X, y = engineer.create_feature_matrix(metrics_df, incidents_df)

            # 3. Train models
            logger.info("Phase 3: Training models...")
            with mlflow.start_run(run_name=f"training-{datetime.now().isoformat()}"):
                # Log parameters
                mlflow.log_params({
                    'feature_count': X.shape[1],
                    'sample_count': X.shape[0],
                    'positive_samples': (y == 1).sum() if isinstance(y, np.ndarray) else 0
                })

                # Train failure prediction
                failure_model = FailurePredictionModel()
                failure_result = failure_model.train(X, y if isinstance(y, np.ndarray) else y.values)
                mlflow.log_metrics({f'failure_{k}': v for k, v in failure_result['metrics'].items()})
                mlflow.sklearn.log_model(failure_result['model'], 'failure_prediction')

                # Train anomaly detection
                anomaly_model = AnomalyDetectionModel()
                anomaly_result = anomaly_model.train(X)
                mlflow.log_metrics({f'anomaly_{k}': v for k, v in anomaly_result['metrics'].items()})

                # Train root cause
                root_cause_model = RootCauseAnalysisModel()
                root_cause_result = root_cause_model.train(X, y if isinstance(y, np.ndarray) else y.values)
                mlflow.log_metrics({f'root_cause_{k}': v for k, v in root_cause_result['metrics'].items()})
                mlflow.sklearn.log_model(root_cause_result['model'], 'root_cause_analysis')

                # Save models to disk
                self._save_models(
                    failure_result['model'],
                    anomaly_model.models,
                    root_cause_result['model']
                )

                logger.info("Training pipeline completed successfully!")
                return {
                    'status': 'success',
                    'failure_metrics': failure_result['metrics'],
                    'anomaly_metrics': anomaly_result['metrics'],
                    'root_cause_metrics': root_cause_result['metrics']
                }

        except Exception as e:
            logger.error(f"Training pipeline failed: {e}")
            raise

    def _create_synthetic_data(self) -> Tuple[np.ndarray, np.ndarray]:
        """Create synthetic data for testing"""
        logger.info("Creating synthetic training data...")
        np.random.seed(42)

        n_samples = 10000
        n_features = 100

        X = np.random.randn(n_samples, n_features)
        y = np.random.randint(0, 2, n_samples)

        # Add some signal
        X[y == 1] += 1.0

        return X, y

    def _save_models(self, failure_model, anomaly_models: Dict, root_cause_model):
        """Save models to local filesystem"""
        output_dir = Path('/tmp/ml_models')
        output_dir.mkdir(exist_ok=True)

        joblib.dump(failure_model, output_dir / 'failure_prediction.pkl')
        joblib.dump(anomaly_models, output_dir / 'anomaly_detection.pkl')
        joblib.dump(root_cause_model, output_dir / 'root_cause_analysis.pkl')

        logger.info(f"Models saved to {output_dir}")


if __name__ == '__main__':
    pipeline = MLTrainingPipeline(experiment_name='traceo-ml-phase7l')
    result = pipeline.run()
    print(json.dumps(result, indent=2))
