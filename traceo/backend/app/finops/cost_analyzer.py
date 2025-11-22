#!/usr/bin/env python3
"""
FinOps Cost Analysis & Anomaly Detection
ML-based cloud cost optimization and anomaly detection
Uses unified anomaly detection engine for consistency
Date: November 21, 2024
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import numpy as np
import pandas as pd
from app.ml.anomaly_detection_engine import CostAnomalyDetector

logger = logging.getLogger(__name__)


class CostDataPoint:
    """Represent a single cost data point"""

    def __init__(self, timestamp: datetime, service: str, cost: float,
                 region: str, resource_type: str, metrics: Dict = None):
        self.timestamp = timestamp
        self.service = service
        self.cost = cost
        self.region = region
        self.resource_type = resource_type
        self.metrics = metrics or {}


class CloudCostAnalyzer:
    """Analyze cloud costs and identify optimization opportunities"""

    def __init__(self):
        self.scaler = StandardScaler()
        self.cost_history: List[CostDataPoint] = []
        self.anomalies: List[Dict] = []

    def add_cost_data(self, data_point: CostDataPoint):
        """Add cost data point"""
        self.cost_history.append(data_point)

    def calculate_daily_costs(self, days: int = 30) -> pd.DataFrame:
        """Calculate daily costs for last N days"""
        cutoff_time = datetime.utcnow() - timedelta(days=days)
        recent_data = [d for d in self.cost_history if d.timestamp >= cutoff_time]

        df = pd.DataFrame([
            {
                'date': d.timestamp.date(),
                'service': d.service,
                'region': d.region,
                'resource_type': d.resource_type,
                'cost': d.cost,
                'timestamp': d.timestamp
            }
            for d in recent_data
        ])

        return df.groupby(['date', 'service']).agg({'cost': 'sum'}).reset_index()

    def calculate_service_costs(self, days: int = 30) -> Dict[str, float]:
        """Calculate total costs by service"""
        cutoff_time = datetime.utcnow() - timedelta(days=days)
        recent_data = [d for d in self.cost_history if d.timestamp >= cutoff_time]

        service_costs = {}
        for data in recent_data:
            if data.service not in service_costs:
                service_costs[data.service] = 0
            service_costs[data.service] += data.cost

        return service_costs

    def calculate_regional_costs(self, days: int = 30) -> Dict[str, float]:
        """Calculate total costs by region"""
        cutoff_time = datetime.utcnow() - timedelta(days=days)
        recent_data = [d for d in self.cost_history if d.timestamp >= cutoff_time]

        regional_costs = {}
        for data in recent_data:
            if data.region not in regional_costs:
                regional_costs[data.region] = 0
            regional_costs[data.region] += data.cost

        return regional_costs

    def get_cost_breakdown(self, days: int = 30) -> Dict:
        """Get comprehensive cost breakdown"""
        total_cost = sum(d.cost for d in self.cost_history
                        if d.timestamp >= datetime.utcnow() - timedelta(days=days))

        service_costs = self.calculate_service_costs(days)
        regional_costs = self.calculate_regional_costs(days)

        breakdown = {
            'total_cost': total_cost,
            'daily_average': total_cost / days,
            'monthly_projection': (total_cost / days) * 30,
            'by_service': service_costs,
            'by_region': regional_costs,
            'period_days': days
        }

        return breakdown


class CostAnomalyAlert:
    """Alert when cost anomalies are detected"""

    def __init__(self, detector: CostAnomalyDetector,
                 threshold_percentage: float = 15.0):
        """
        Args:
            detector: CostAnomalyDetector instance
            threshold_percentage: Alert if cost deviates by this % from baseline
        """
        self.detector = detector
        self.threshold_percentage = threshold_percentage
        self.alerts = []

    def check_and_alert(self, current_cost: float) -> Optional[Dict]:
        """
        Check if current cost triggers an alert.

        Returns:
            Alert dict if triggered, None otherwise
        """
        if not self.detector.is_fitted:
            return None

        # Calculate deviation
        deviation = ((current_cost - self.detector.baseline_mean) /
                    self.detector.baseline_mean * 100)

        # Check if exceeds threshold
        if abs(deviation) >= self.threshold_percentage:
            anomaly_score = self.detector.calculate_anomaly_score(current_cost)

            alert = {
                'triggered': True,
                'timestamp': datetime.utcnow(),
                'current_cost': current_cost,
                'baseline_cost': self.detector.baseline_mean,
                'deviation_percentage': deviation,
                'anomaly_score': anomaly_score,
                'severity': 'CRITICAL' if abs(deviation) > 30 else 'WARNING',
                'message': f"Cost deviation: {deviation:+.1f}% "
                          f"(${current_cost:.2f} vs ${self.detector.baseline_mean:.2f})"
            }

            self.alerts.append(alert)
            return alert

        return None

    def get_recent_alerts(self, hours: int = 24) -> List[Dict]:
        """Get alerts from last N hours"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        return [a for a in self.alerts if a['timestamp'] >= cutoff_time]


class CostOptimizationRecommender:
    """Generate cost optimization recommendations"""

    OPTIMIZATION_STRATEGIES = {
        'reserved_instances': {
            'savings_percentage': 25,
            'implementation_difficulty': 'easy',
            'payback_period_months': 3,
            'description': 'Purchase reserved instances for predictable workloads'
        },
        'spot_instances': {
            'savings_percentage': 60,
            'implementation_difficulty': 'hard',
            'payback_period_months': 1,
            'description': 'Use spot instances for fault-tolerant workloads'
        },
        'data_compression': {
            'savings_percentage': 50,
            'implementation_difficulty': 'medium',
            'payback_period_months': 2,
            'description': 'Compress stored data to reduce storage costs'
        },
        'right_sizing': {
            'savings_percentage': 20,
            'implementation_difficulty': 'medium',
            'payback_period_months': 1,
            'description': 'Resize instances to match actual resource usage'
        },
        'auto_scaling': {
            'savings_percentage': 25,
            'implementation_difficulty': 'hard',
            'payback_period_months': 2,
            'description': 'Scale down resources during off-peak hours'
        },
        'data_tiering': {
            'savings_percentage': 40,
            'implementation_difficulty': 'medium',
            'payback_period_months': 3,
            'description': 'Move old data to cheaper storage tiers'
        }
    }

    @staticmethod
    def get_recommendations(cost_by_service: Dict[str, float],
                          total_cost: float) -> List[Dict]:
        """
        Generate optimization recommendations based on cost analysis.

        Args:
            cost_by_service: Cost breakdown by service
            total_cost: Total monthly cost

        Returns:
            List of recommendations sorted by impact
        """
        recommendations = []

        # Identify high-cost services
        for service, cost in sorted(cost_by_service.items(),
                                    key=lambda x: x[1], reverse=True):
            service_percentage = (cost / total_cost) * 100

            if service_percentage > 20:
                # High-cost service - recommend multiple optimizations
                for strategy_name, strategy in CostOptimizationRecommender.OPTIMIZATION_STRATEGIES.items():
                    potential_savings = cost * (strategy['savings_percentage'] / 100)

                    recommendation = {
                        'service': service,
                        'strategy': strategy_name,
                        'description': strategy['description'],
                        'current_cost': cost,
                        'potential_savings': potential_savings,
                        'savings_percentage': strategy['savings_percentage'],
                        'implementation_difficulty': strategy['implementation_difficulty'],
                        'payback_period_months': strategy['payback_period_months'],
                        'priority': 'HIGH' if potential_savings > total_cost * 0.05 else 'MEDIUM'
                    }

                    recommendations.append(recommendation)

        # Sort by potential savings
        recommendations.sort(key=lambda x: x['potential_savings'], reverse=True)

        return recommendations

    @staticmethod
    def calculate_roi(recommendations: List[Dict],
                     implementation_cost: float = 10000) -> Dict:
        """
        Calculate ROI of implementing recommendations.

        Args:
            recommendations: List of recommendations
            implementation_cost: Cost to implement optimizations

        Returns:
            ROI analysis
        """
        total_potential_savings = sum(r['potential_savings'] for r in recommendations)
        annual_savings = total_potential_savings * 12
        payback_months = implementation_cost / (annual_savings / 12) if annual_savings > 0 else float('inf')

        return {
            'total_potential_savings_monthly': total_potential_savings,
            'total_potential_savings_annual': annual_savings,
            'implementation_cost': implementation_cost,
            'payback_period_months': payback_months,
            'roi_percentage': ((annual_savings - implementation_cost) / implementation_cost * 100) if implementation_cost > 0 else 0,
            'three_year_value': (annual_savings * 3) - implementation_cost
        }


# Example usage
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    # Create analyzer
    analyzer = CloudCostAnalyzer()
    detector = CostAnomalyDetector()

    # Simulate cost data (daily costs)
    np.random.seed(42)
    base_cost = 5000
    costs = []

    for i in range(60):
        # Normal variation
        daily_cost = base_cost + np.random.normal(0, 500)
        # Add anomaly on day 45
        if i == 45:
            daily_cost = base_cost * 2.5  # 150% spike

        costs.append(daily_cost)
        analyzer.add_cost_data(
            CostDataPoint(
                timestamp=datetime.utcnow() - timedelta(days=60-i),
                service='api-server' if i % 2 == 0 else 'database',
                cost=daily_cost,
                region='us-east-1',
                resource_type='compute'
            )
        )

    # Fit anomaly detector (using unified engine)
    detector.fit(costs)

    # Detect anomalies in batch
    costs_list = list(costs)
    anomalies = []  # Updated to use new detection method
    for idx, cost in enumerate(costs_list):
        result = detector.detect_anomaly(cost, costs_list)
        if result.is_anomaly:
            anomalies.append(idx)
    print(f"\n=== Anomaly Detection ===")
    print(f"Detected {len(anomalies)} anomalies:")
    for idx in anomalies:
        print(f"  Day {idx}: ${costs[idx]:.2f} (expected ${detector.baseline_mean:.2f})")

    # Cost analysis
    breakdown = analyzer.get_cost_breakdown(days=30)
    print(f"\n=== Cost Breakdown (30 days) ===")
    print(f"Total cost: ${breakdown['total_cost']:.2f}")
    print(f"Daily average: ${breakdown['daily_average']:.2f}")
    print(f"Monthly projection: ${breakdown['monthly_projection']:.2f}")

    # Recommendations
    print(f"\n=== Optimization Recommendations ===")
    recommendations = CostOptimizationRecommender.get_recommendations(
        breakdown['by_service'],
        breakdown['total_cost']
    )

    for rec in recommendations[:3]:  # Top 3
        print(f"  {rec['strategy']}: ${rec['potential_savings']:.2f}/month "
              f"({rec['savings_percentage']}%) - {rec['priority']}")

    # ROI
    roi = CostOptimizationRecommender.calculate_roi(recommendations)
    print(f"\n=== ROI Analysis ===")
    print(f"Annual savings potential: ${roi['total_potential_savings_annual']:.2f}")
    print(f"3-year value: ${roi['three_year_value']:.2f}")
    print(f"Payback period: {roi['payback_period_months']:.1f} months")
