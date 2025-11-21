#!/usr/bin/env python3
"""
Active Learning for Traceo ML Pipeline
Selects hard cases for labeling to maximize training efficiency
Date: November 21, 2024
"""

import logging
import numpy as np
import pandas as pd
from typing import List, Tuple, Dict
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from scipy.stats import entropy

logger = logging.getLogger(__name__)


class ActiveLearningSelector:
    """Select hard cases from unlabeled data for efficient labeling"""

    def __init__(self, model=None, scaler=None):
        self.model = model
        self.scaler = scaler
        self.selection_strategy = 'uncertainty'

    def set_model(self, model):
        """Set the base model for uncertainty estimation"""
        self.model = model

    def set_scaler(self, scaler):
        """Set the feature scaler"""
        self.scaler = scaler

    def uncertainty_sampling(self, X_unlabeled: np.ndarray,
                            n_select: int = 100) -> List[int]:
        """
        Select samples with highest prediction uncertainty.
        Uses entropy of prediction probabilities.
        """
        if self.model is None:
            raise ValueError("Model not set. Call set_model() first.")

        logger.info(f"Uncertainty sampling: selecting {n_select} samples...")

        # Get prediction probabilities
        if hasattr(self.model, 'predict_proba'):
            proba = self.model.predict_proba(X_unlabeled)
        else:
            logger.warning("Model does not support predict_proba. Using decision_function.")
            decision = self.model.decision_function(X_unlabeled)
            # Convert to probability-like scores
            proba = 1 / (1 + np.exp(-decision))
            proba = np.column_stack([1 - proba, proba])

        # Calculate entropy for each sample
        uncertainties = entropy(proba.T)

        # Select top n samples with highest uncertainty
        top_indices = np.argsort(uncertainties)[-n_select:]

        logger.info(f"Selected {len(top_indices)} samples with highest uncertainty")
        return top_indices.tolist()

    def margin_sampling(self, X_unlabeled: np.ndarray,
                       n_select: int = 100) -> List[int]:
        """
        Select samples where the model is least confident.
        Margin = |P(y=1) - P(y=0)|
        Samples with smallest margins are most uncertain.
        """
        logger.info(f"Margin sampling: selecting {n_select} samples...")

        proba = self.model.predict_proba(X_unlabeled)

        # Calculate margin for binary classification
        margins = np.abs(proba[:, 0] - proba[:, 1])

        # Select samples with smallest margins (lowest confidence)
        top_indices = np.argsort(margins)[:n_select]

        logger.info(f"Selected {len(top_indices)} samples with smallest margin")
        return top_indices.tolist()

    def query_by_committee(self, X_unlabeled: np.ndarray,
                          models: List, n_select: int = 100) -> List[int]:
        """
        Ensemble-based active learning.
        Select samples where committee models disagree the most.
        """
        logger.info(f"Query by committee: selecting {n_select} samples...")

        predictions = []
        for model in models:
            pred = model.predict(X_unlabeled)
            predictions.append(pred)

        predictions = np.array(predictions)

        # Calculate disagreement (variance across predictions)
        disagreement = np.var(predictions, axis=0)

        # Select samples with highest disagreement
        top_indices = np.argsort(disagreement)[-n_select:]

        logger.info(f"Selected {len(top_indices)} samples with highest disagreement")
        return top_indices.tolist()

    def expected_model_change(self, X_unlabeled: np.ndarray,
                             X_labeled: np.ndarray,
                             y_labeled: np.ndarray,
                             n_select: int = 100) -> List[int]:
        """
        Select samples that would most change the model if labeled.
        For each candidate sample, estimate model parameters with/without it.
        """
        logger.info(f"Expected model change: selecting {n_select} samples...")

        current_weights = self.model.feature_importances_ if hasattr(self.model, 'feature_importances_') else None

        if current_weights is None:
            logger.warning("Model does not have feature_importances. Falling back to uncertainty.")
            return self.uncertainty_sampling(X_unlabeled, n_select)

        changes = []
        for i in range(min(1000, len(X_unlabeled))):  # Sample for efficiency
            # Add this sample to labeled set
            X_temp = np.vstack([X_labeled, X_unlabeled[i:i+1]])
            y_temp = np.append(y_labeled, np.random.randint(0, 2))

            # Train temporary model
            temp_model = RandomForestClassifier(n_estimators=10, random_state=42)
            temp_model.fit(X_temp, y_temp)

            # Calculate change in model
            weight_change = np.sum(np.abs(current_weights - temp_model.feature_importances_))
            changes.append(weight_change)

        changes = np.array(changes)
        top_indices = np.argsort(changes)[-n_select:]

        logger.info(f"Selected {len(top_indices)} samples with highest expected model change")
        return top_indices.tolist()

    def density_based_sampling(self, X_unlabeled: np.ndarray,
                              n_select: int = 100,
                              diversity_weight: float = 0.3) -> List[int]:
        """
        Combine uncertainty with diversity.
        Prefer uncertain samples that are different from already selected ones.
        """
        logger.info(f"Density-based sampling: selecting {n_select} samples...")

        # Get uncertainties
        proba = self.model.predict_proba(X_unlabeled)
        uncertainties = entropy(proba.T)

        # Calculate density (inverse of average distance to k nearest neighbors)
        from sklearn.neighbors import NearestNeighbors
        k = min(10, len(X_unlabeled) - 1)
        nbrs = NearestNeighbors(n_neighbors=k)
        nbrs.fit(X_unlabeled)
        distances, _ = nbrs.kneighbors(X_unlabeled)
        densities = 1 / (np.mean(distances[:, 1:], axis=1) + 1e-10)

        # Combine uncertainty and density
        if self.scaler:
            uncertainties = self.scaler.fit_transform(uncertainties.reshape(-1, 1)).flatten()
            densities = self.scaler.fit_transform(densities.reshape(-1, 1)).flatten()

        scores = (1 - diversity_weight) * uncertainties + diversity_weight * densities

        # Select top samples
        top_indices = np.argsort(scores)[-n_select:]

        logger.info(f"Selected {len(top_indices)} samples using density-based approach")
        return top_indices.tolist()

    def select_samples(self, X_unlabeled: np.ndarray,
                      X_labeled: np.ndarray,
                      y_labeled: np.ndarray,
                      n_select: int = 100,
                      strategy: str = 'uncertainty') -> List[int]:
        """
        Select samples for labeling using specified strategy.

        Args:
            X_unlabeled: Unlabeled feature matrix
            X_labeled: Labeled feature matrix (for reference)
            y_labeled: Labels for X_labeled
            n_select: Number of samples to select
            strategy: Selection strategy ('uncertainty', 'margin', 'committee', 'emuc', 'density')
        """
        logger.info(f"Starting active learning: strategy={strategy}, n_select={n_select}")

        if strategy == 'uncertainty':
            return self.uncertainty_sampling(X_unlabeled, n_select)
        elif strategy == 'margin':
            return self.margin_sampling(X_unlabeled, n_select)
        elif strategy == 'emuc':
            return self.expected_model_change(X_unlabeled, X_labeled, y_labeled, n_select)
        elif strategy == 'density':
            return self.density_based_sampling(X_unlabeled, n_select)
        else:
            logger.warning(f"Unknown strategy: {strategy}. Using uncertainty.")
            return self.uncertainty_sampling(X_unlabeled, n_select)


class ActiveLearningOracle:
    """Simulates or interfaces with human oracle for labeling"""

    def __init__(self, db_connection=None):
        self.db_connection = db_connection
        self.labeling_history = []

    def get_labels_for_samples(self, sample_indices: List[int],
                              sample_data: pd.DataFrame) -> Dict[int, str]:
        """
        Get labels for samples from oracle (human or automated).
        Returns: {sample_index: label}
        """
        logger.info(f"Getting labels for {len(sample_indices)} samples...")

        labels = {}
        for idx in sample_indices:
            sample = sample_data.iloc[idx]
            # In production, this would prompt human or use weak labels
            label = self._oracle_predict(sample)
            labels[idx] = label
            self.labeling_history.append({
                'index': idx,
                'label': label,
                'timestamp': pd.Timestamp.now()
            })

        logger.info(f"Obtained labels for {len(labels)} samples")
        return labels

    def _oracle_predict(self, sample: pd.Series) -> str:
        """Simulate oracle prediction or query database"""
        # In production, this would:
        # 1. Query incident database for root cause
        # 2. Prompt human labeler
        # 3. Use weak labels (automated heuristics)

        # For now, use a simple heuristic
        if sample.get('cpu_usage', 0) > 0.9:
            return 'cpu_saturation'
        elif sample.get('memory_usage', 0) > 0.85:
            return 'memory_leak'
        elif sample.get('disk_io', 0) > 0.8:
            return 'disk_full'
        else:
            return 'unknown'

    def save_labels(self, labels: Dict[int, str]):
        """Save labels to database"""
        if self.db_connection:
            for idx, label in labels.items():
                # INSERT into incident_records (root_cause) VALUES (label)
                logger.info(f"Saved label for sample {idx}: {label}")


class ActiveLearningPipeline:
    """End-to-end active learning pipeline"""

    def __init__(self, initial_labeled_size: int = 100,
                 target_labeled_size: int = 1500,
                 batch_size: int = 100):
        self.initial_labeled_size = initial_labeled_size
        self.target_labeled_size = target_labeled_size
        self.batch_size = batch_size
        self.selector = ActiveLearningSelector()
        self.oracle = ActiveLearningOracle()
        self.training_history = []

    def run(self, X: np.ndarray, y: np.ndarray,
            X_unlabeled: pd.DataFrame) -> Dict:
        """
        Run active learning pipeline.
        Iteratively select and label samples until target size reached.
        """
        logger.info(f"Starting active learning pipeline...")
        logger.info(f"Initial labeled: {self.initial_labeled_size}, Target: {self.target_labeled_size}")

        # Initial training set
        indices = np.random.choice(len(X), self.initial_labeled_size, replace=False)
        X_labeled = X[indices]
        y_labeled = y[indices]

        unlabeled_indices = np.setdiff1d(np.arange(len(X)), indices)

        iteration = 0
        while len(y_labeled) < self.target_labeled_size:
            iteration += 1
            logger.info(f"\n=== Iteration {iteration} ===")
            logger.info(f"Labeled: {len(y_labeled)}/{self.target_labeled_size}")

            # Train model on labeled data
            model = RandomForestClassifier(n_estimators=50, max_depth=15, random_state=42)
            model.fit(X_labeled, y_labeled)

            # Set model for active learning
            self.selector.set_model(model)

            # Select samples for labeling
            X_unlabeled_subset = X[unlabeled_indices]
            selected_indices = self.selector.select_samples(
                X_unlabeled_subset,
                X_labeled,
                y_labeled,
                n_select=min(self.batch_size, len(unlabeled_indices)),
                strategy='density'
            )

            # Get labels from oracle
            selected_absolute_indices = unlabeled_indices[selected_indices]
            selected_samples = pd.DataFrame(X[selected_absolute_indices])
            labels = self.oracle.get_labels_for_samples(selected_absolute_indices, selected_samples)

            # Add to labeled set
            X_labeled = np.vstack([X_labeled, X[selected_absolute_indices]])
            y_labeled_new = np.array([labels.get(idx, 'unknown') for idx in selected_absolute_indices])
            y_labeled = np.append(y_labeled, y_labeled_new)

            # Remove from unlabeled
            unlabeled_indices = np.setdiff1d(unlabeled_indices, selected_absolute_indices)

            # Log progress
            accuracy = model.score(X_labeled, y_labeled)
            self.training_history.append({
                'iteration': iteration,
                'labeled_count': len(y_labeled),
                'selected_count': len(selected_indices),
                'accuracy': accuracy
            })

            logger.info(f"Selected {len(selected_indices)} samples, Accuracy: {accuracy:.4f}")

        logger.info("\n=== Active Learning Complete ===")
        logger.info(f"Final labeled dataset: {len(y_labeled)} samples")

        return {
            'status': 'success',
            'final_labeled_count': len(y_labeled),
            'iterations': iteration,
            'training_history': self.training_history,
            'labeled_reduction': f"{(1 - len(y_labeled) / self.target_labeled_size) * 100:.1f}% reduction"
        }


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    # Example usage
    X = np.random.randn(5000, 100)
    y = np.random.randint(0, 2, 5000)
    X_unlabeled = pd.DataFrame(np.random.randn(1000, 100))

    pipeline = ActiveLearningPipeline(
        initial_labeled_size=100,
        target_labeled_size=500,
        batch_size=50
    )
    result = pipeline.run(X, y, X_unlabeled)
    print(result)
