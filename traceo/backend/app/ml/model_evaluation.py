#!/usr/bin/env python3
"""
Model Evaluation and A/B Testing Framework for Traceo
Date: November 21, 2024
"""

import logging
import hashlib
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Tuple, List
from dataclasses import dataclass
from enum import Enum
from scipy import stats
import json

logger = logging.getLogger(__name__)


class ExperimentStatus(Enum):
    """A/B test experiment status"""
    PLANNING = 'planning'
    RUNNING = 'running'
    COMPLETED = 'completed'
    FAILED = 'failed'


@dataclass
class ExperimentConfig:
    """A/B test configuration"""
    experiment_id: str
    control_model_id: str
    treatment_model_id: str
    target_metric: str
    significance_level: float = 0.05
    sample_size: int = 10000
    minimum_detectable_effect: float = 0.05
    runtime_days: int = 14


class ABTestingFramework:
    """End-to-end A/B testing framework for ML models"""

    def __init__(self, db_connection=None):
        self.db_connection = db_connection
        self.experiments = {}
        self.results = {}

    def create_experiment(self, config: ExperimentConfig) -> str:
        """Create new A/B test experiment"""
        logger.info(f"Creating experiment: {config.experiment_id}")

        experiment = {
            'id': config.experiment_id,
            'control_model': config.control_model_id,
            'treatment_model': config.treatment_model_id,
            'target_metric': config.target_metric,
            'status': ExperimentStatus.PLANNING.value,
            'created_at': datetime.utcnow(),
            'config': config.__dict__,
            'variants': {
                'control': {'samples': 0, 'metric_values': []},
                'treatment': {'samples': 0, 'metric_values': []}
            },
            'power_analysis': self._calculate_power(config),
            'results': None
        }

        self.experiments[config.experiment_id] = experiment
        return config.experiment_id

    def assign_user_to_variant(self, user_id: str, experiment_id: str) -> str:
        """Consistently assign user to control (0) or treatment (1)"""
        hash_input = f"{user_id}{experiment_id}".encode()
        hash_value = int(hashlib.md5(hash_input).hexdigest(), 16)
        variant = 'control' if (hash_value % 2) == 0 else 'treatment'
        return variant

    def start_experiment(self, experiment_id: str):
        """Start experiment (move from PLANNING to RUNNING)"""
        if experiment_id in self.experiments:
            self.experiments[experiment_id]['status'] = ExperimentStatus.RUNNING.value
            self.experiments[experiment_id]['started_at'] = datetime.utcnow()
            logger.info(f"Experiment {experiment_id} started")

    def collect_metric(self, experiment_id: str, variant: str,
                      user_id: str, metric_value: float, timestamp: datetime = None):
        """Collect metric for A/B test"""
        if timestamp is None:
            timestamp = datetime.utcnow()

        if experiment_id in self.experiments:
            self.experiments[experiment_id]['variants'][variant]['samples'] += 1
            self.experiments[experiment_id]['variants'][variant]['metric_values'].append(metric_value)

    def calculate_statistics(self, experiment_id: str) -> Dict:
        """Calculate statistical significance"""
        if experiment_id not in self.experiments:
            logger.error(f"Experiment {experiment_id} not found")
            return {}

        experiment = self.experiments[experiment_id]
        control_values = np.array(experiment['variants']['control']['metric_values'])
        treatment_values = np.array(experiment['variants']['treatment']['metric_values'])

        if len(control_values) == 0 or len(treatment_values) == 0:
            logger.warning(f"Insufficient data for {experiment_id}")
            return {'status': 'insufficient_data'}

        # T-test
        t_stat, p_value = stats.ttest_ind(treatment_values, control_values)

        # Effect size (Cohen's d)
        cohens_d = self._cohens_d(treatment_values, control_values)

        # Confidence intervals (95%)
        control_ci = self._confidence_interval(control_values, confidence=0.95)
        treatment_ci = self._confidence_interval(treatment_values, confidence=0.95)

        # Relative improvement
        control_mean = control_values.mean()
        treatment_mean = treatment_values.mean()
        improvement_percentage = ((treatment_mean - control_mean) / control_mean) * 100

        results = {
            'experiment_id': experiment_id,
            'control_mean': float(control_mean),
            'treatment_mean': float(treatment_mean),
            'control_std': float(control_values.std()),
            'treatment_std': float(treatment_values.std()),
            'difference': float(treatment_mean - control_mean),
            'improvement_percentage': float(improvement_percentage),
            'control_ci': [float(x) for x in control_ci],
            'treatment_ci': [float(x) for x in treatment_ci],
            't_statistic': float(t_stat),
            'p_value': float(p_value),
            'cohens_d': float(cohens_d),
            'is_significant': p_value < 0.05,
            'control_samples': len(control_values),
            'treatment_samples': len(treatment_values),
            'total_samples': len(control_values) + len(treatment_values),
            'power': self._calculate_achieved_power(len(control_values), cohens_d)
        }

        return results

    def recommend_action(self, stats: Dict) -> str:
        """Recommend whether to deploy treatment model"""
        if stats.get('status') == 'insufficient_data':
            return 'CONTINUE: Collect more data'

        p_value = stats.get('p_value', 1.0)
        improvement = stats.get('improvement_percentage', 0)

        if p_value >= 0.05:
            return f'INCONCLUSIVE: p={p_value:.3f} (need p<0.05). Continue experiment.'
        elif improvement < 0:
            return f'REJECT: Treatment {abs(improvement):.2f}% worse than control'
        elif improvement < 2:
            return f'INCONCLUSIVE: Only {improvement:.2f}% improvement (effect too small)'
        else:
            return f'DEPLOY: Treatment {improvement:.2f}% better (p={p_value:.3f})'

    def is_experiment_complete(self, experiment_id: str) -> bool:
        """Check if experiment has enough data for decision"""
        if experiment_id not in self.experiments:
            return False

        experiment = self.experiments[experiment_id]
        config = experiment['config']

        # Check sample size
        control_n = experiment['variants']['control']['samples']
        treatment_n = experiment['variants']['treatment']['samples']
        total_n = control_n + treatment_n

        if total_n < config['sample_size']:
            return False

        # Check duration
        started = experiment.get('started_at')
        if started:
            duration = (datetime.utcnow() - started).days
            if duration < config['runtime_days']:
                return False

        return True

    def end_experiment(self, experiment_id: str) -> Dict:
        """End experiment and generate results"""
        if experiment_id not in self.experiments:
            return {'status': 'error', 'message': 'Experiment not found'}

        experiment = self.experiments[experiment_id]

        # Calculate statistics
        stats_result = self.calculate_statistics(experiment_id)

        # Generate recommendation
        recommendation = self.recommend_action(stats_result)

        # Update experiment
        experiment['status'] = ExperimentStatus.COMPLETED.value
        experiment['ended_at'] = datetime.utcnow()
        experiment['results'] = stats_result
        experiment['recommendation'] = recommendation

        logger.info(f"Experiment {experiment_id} completed: {recommendation}")

        return {
            'experiment_id': experiment_id,
            'statistics': stats_result,
            'recommendation': recommendation,
            'status': 'completed'
        }

    def get_experiment_summary(self, experiment_id: str) -> Dict:
        """Get experiment summary"""
        if experiment_id not in self.experiments:
            return {}

        experiment = self.experiments[experiment_id]
        control_values = np.array(experiment['variants']['control']['metric_values'])
        treatment_values = np.array(experiment['variants']['treatment']['metric_values'])

        return {
            'experiment_id': experiment_id,
            'status': experiment['status'],
            'control_samples': len(control_values),
            'treatment_samples': len(treatment_values),
            'control_mean': float(control_values.mean()) if len(control_values) > 0 else None,
            'treatment_mean': float(treatment_values.mean()) if len(treatment_values) > 0 else None,
            'is_complete': self.is_experiment_complete(experiment_id),
            'recommendation': experiment.get('recommendation', 'Pending')
        }

    # Helper methods
    @staticmethod
    def _cohens_d(group1: np.ndarray, group2: np.ndarray) -> float:
        """Calculate Cohen's d effect size"""
        n1, n2 = len(group1), len(group2)
        var1, var2 = group1.var(), group2.var()
        pooled_std = np.sqrt(((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2))
        return (group1.mean() - group2.mean()) / pooled_std if pooled_std > 0 else 0

    @staticmethod
    def _confidence_interval(data: np.ndarray, confidence: float = 0.95) -> Tuple[float, float]:
        """Calculate confidence interval"""
        mean = data.mean()
        sem = stats.sem(data)
        ci = sem * stats.t.ppf((1 + confidence) / 2, len(data) - 1)
        return mean - ci, mean + ci

    @staticmethod
    def _calculate_power(config: ExperimentConfig) -> Dict:
        """Calculate statistical power"""
        from statsmodels.stats.power import tt_solve_power

        try:
            power = tt_solve_power(
                effect_size=config.minimum_detectable_effect,
                nobs=config.sample_size / 2,
                alpha=config.significance_level,
                alternative='two-sided'
            )
            return {'power': power, 'effect_size': config.minimum_detectable_effect}
        except:
            return {'power': None, 'error': 'Could not calculate power'}

    @staticmethod
    def _calculate_achieved_power(sample_size: int, effect_size: float) -> float:
        """Calculate achieved statistical power"""
        from statsmodels.stats.power import tt_solve_power

        try:
            power = tt_solve_power(
                effect_size=effect_size,
                nobs=sample_size / 2,
                alpha=0.05,
                alternative='two-sided'
            )
            return float(power)
        except:
            return 0.0


class ModelEvaluator:
    """Comprehensive model evaluation metrics"""

    @staticmethod
    def evaluate_classification(y_true: np.ndarray, y_pred: np.ndarray,
                               y_pred_proba: np.ndarray = None) -> Dict:
        """Evaluate classification model"""
        from sklearn.metrics import (
            accuracy_score, precision_score, recall_score, f1_score,
            roc_auc_score, confusion_matrix, classification_report
        )

        results = {
            'accuracy': float(accuracy_score(y_true, y_pred)),
            'precision': float(precision_score(y_true, y_pred, average='weighted', zero_division=0)),
            'recall': float(recall_score(y_true, y_pred, average='weighted', zero_division=0)),
            'f1_score': float(f1_score(y_true, y_pred, average='weighted', zero_division=0)),
        }

        if y_pred_proba is not None:
            results['auc'] = float(roc_auc_score(y_true, y_pred_proba[:, 1]))

        cm = confusion_matrix(y_true, y_pred)
        results['confusion_matrix'] = cm.tolist()

        return results

    @staticmethod
    def evaluate_anomaly_detection(y_true: np.ndarray, y_pred: np.ndarray) -> Dict:
        """Evaluate anomaly detection model"""
        from sklearn.metrics import (
            precision_recall_curve, f1_score, roc_auc_score
        )

        # Assuming 1 = anomaly, 0 = normal
        results = {
            'precision': float(np.sum((y_pred == 1) & (y_true == 1)) / np.sum(y_pred == 1) + 1e-10),
            'recall': float(np.sum((y_pred == 1) & (y_true == 1)) / np.sum(y_true == 1) + 1e-10),
        }

        results['f1_score'] = 2 * (results['precision'] * results['recall']) / (results['precision'] + results['recall'] + 1e-10)

        return results

    @staticmethod
    def compare_models(model_results: Dict[str, Dict]) -> Dict:
        """Compare multiple models"""
        comparison = {}
        for model_name, metrics in model_results.items():
            comparison[model_name] = {
                'accuracy': metrics.get('accuracy', 0),
                'f1_score': metrics.get('f1_score', 0),
                'auc': metrics.get('auc', 0)
            }
        return comparison


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    # Example usage
    framework = ABTestingFramework()

    # Create experiment
    config = ExperimentConfig(
        experiment_id='test-001',
        control_model_id='model-v1',
        treatment_model_id='model-v2',
        target_metric='accuracy',
        sample_size=1000,
        runtime_days=7
    )

    exp_id = framework.create_experiment(config)
    framework.start_experiment(exp_id)

    # Simulate data collection
    np.random.seed(42)
    for i in range(500):
        variant = framework.assign_user_to_variant(f'user_{i}', exp_id)
        if variant == 'control':
            metric_value = np.random.normal(0.85, 0.05)
        else:
            metric_value = np.random.normal(0.88, 0.05)

        framework.collect_metric(exp_id, variant, f'user_{i}', metric_value)

    # Get results
    summary = framework.get_experiment_summary(exp_id)
    print(json.dumps(summary, indent=2, default=str))
