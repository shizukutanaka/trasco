#!/usr/bin/env python3
"""
SLO Management & Error Budget Tracking
Implements Google SRE MWMB (Multi-Window Multi-Burn-Rate) alerts
Date: November 21, 2024
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class SLOStatus(Enum):
    """SLO status enumeration"""
    HEALTHY = 'healthy'
    WARNING = 'warning'
    CRITICAL = 'critical'
    VIOLATED = 'violated'


@dataclass
class SLODefinition:
    """SLO definition"""
    name: str
    service: str
    objective: float  # e.g., 0.999 for 99.9%
    window_days: int = 30
    indicator_type: str = 'http_check'  # http_check, latency, error_rate
    threshold: Dict = None  # Indicator-specific thresholds


@dataclass
class ErrorBudget:
    """Error budget tracking"""
    slo_definition: SLODefinition
    period_start: datetime
    period_end: datetime
    total_budget_seconds: float
    consumed_seconds: float
    remaining_seconds: float


class SLOCalculator:
    """Calculate SLO metrics and error budgets"""

    @staticmethod
    def calculate_error_budget(slo_percentage: float, days: int) -> float:
        """
        Calculate total error budget in seconds for a time period.

        Args:
            slo_percentage: SLO target (e.g., 99.9)
            days: Time period in days

        Returns:
            Total allowed downtime in seconds
        """
        slo_decimal = slo_percentage / 100
        allowed_downtime_ratio = 1 - slo_decimal
        total_seconds = days * 24 * 3600
        error_budget_seconds = total_seconds * allowed_downtime_ratio

        logger.info(
            f"Error budget for {slo_percentage}% SLO over {days} days: "
            f"{error_budget_seconds:.0f} seconds ({error_budget_seconds/60:.1f} minutes)"
        )

        return error_budget_seconds

    @staticmethod
    def calculate_burn_rate(errors: int, total_requests: int,
                           window_seconds: int) -> float:
        """
        Calculate burn rate (% of error budget consumed per unit time).

        Args:
            errors: Number of errors in window
            total_requests: Total requests in window
            window_seconds: Window duration in seconds

        Returns:
            Burn rate (multiple of error budget)
        """
        if total_requests == 0:
            return 0

        error_rate = errors / total_requests

        # Error budget burn rate
        # If SLO is 99.9%, error budget is 0.1%
        # If current error rate is 1%, burn rate = 1% / 0.1% = 10x
        # (burning 10x faster than allowed)

        slo_error_rate = 0.001  # 99.9% SLO
        burn_rate = error_rate / slo_error_rate

        return burn_rate

    @staticmethod
    def track_error_budget(
        errors_30d: int,
        total_requests_30d: int,
        slo_percentage: float = 99.9
    ) -> ErrorBudget:
        """
        Track error budget consumption over time period.
        """
        error_budget_total = SLOCalculator.calculate_error_budget(slo_percentage, 30)
        error_rate_30d = errors_30d / total_requests_30d if total_requests_30d > 0 else 0

        # In a 30-day period, if SLO is 99.9%, we can have max 0.1% errors
        # Calculate actual error budget consumed
        allowed_error_requests = int(total_requests_30d * (1 - slo_percentage / 100))
        consumed_budget_ratio = errors_30d / max(allowed_error_requests, 1)

        consumed_seconds = error_budget_total * consumed_budget_ratio
        remaining_seconds = error_budget_total - consumed_seconds

        return {
            'total_budget_seconds': error_budget_total,
            'consumed_seconds': consumed_seconds,
            'remaining_seconds': remaining_seconds,
            'consumed_percentage': (consumed_seconds / error_budget_total) * 100,
            'remaining_percentage': (remaining_seconds / error_budget_total) * 100,
            'error_rate': error_rate_30d,
            'status': 'healthy' if remaining_seconds > 0 else 'violated'
        }


class MWMBAlertingFramework:
    """
    Multi-Window Multi-Burn-Rate (MWMB) Alert Framework
    Based on Google SRE best practices
    """

    @staticmethod
    def get_alert_rules(slo_percentage: float = 99.9) -> List[Dict]:
        """
        Get MWMB alert rules for given SLO.

        SLO 99.9% means:
        - Error budget: 0.1% per day, 1.2% per week, 3.09% per month
        - Short window alerts catch fast-burning issues
        - Long window alerts catch slow-burning issues
        """

        # Error budget percentages
        daily_budget = (1 - slo_percentage / 100) * 100  # 0.1%
        weekly_budget = daily_budget * 7  # 0.7%
        monthly_budget = daily_budget * 30  # 3%

        rules = [
            {
                'name': 'fast_burn_1h',
                'window_minutes': 60,
                'burn_rate_threshold': 10,  # Burn 10x normal speed
                'severity': 'CRITICAL',
                'description': 'Burning 10x normal error budget in 1 hour',
                'action': 'Page immediately',
                'tolerance': 'Low - issue is happening NOW'
            },
            {
                'name': 'fast_burn_6h',
                'window_minutes': 360,
                'burn_rate_threshold': 6,
                'severity': 'CRITICAL',
                'description': 'Burning 6x normal error budget in 6 hours',
                'action': 'Page immediately',
                'tolerance': 'Low - issue is still happening'
            },
            {
                'name': 'medium_burn_30m',
                'window_minutes': 30,
                'burn_rate_threshold': 30,
                'severity': 'CRITICAL',
                'description': 'Burning 30x normal error budget in 30 minutes',
                'action': 'Page immediately - critical burn rate',
                'tolerance': 'Very low'
            },
            {
                'name': 'slow_burn_24h',
                'window_minutes': 1440,
                'burn_rate_threshold': 2,
                'severity': 'WARNING',
                'description': 'Burning 2x normal error budget over 24 hours',
                'action': 'Page within 1 hour',
                'tolerance': 'Medium - issue persisting'
            },
            {
                'name': 'very_slow_burn_7d',
                'window_minutes': 10080,  # 7 days
                'burn_rate_threshold': 1,
                'severity': 'WARNING',
                'description': 'Approaching 1x normal error budget over 7 days',
                'action': 'Planning alert - investigate trends',
                'tolerance': 'High - needs investigation but not urgent'
            }
        ]

        return rules

    @staticmethod
    def evaluate_mwmb_alerts(
        metrics_data: pd.DataFrame,
        slo_percentage: float = 99.9,
        service_name: str = 'unknown'
    ) -> Dict:
        """
        Evaluate MWMB rules against metrics data.

        Args:
            metrics_data: DataFrame with columns: timestamp, errors, total_requests
            slo_percentage: SLO target percentage
            service_name: Service being monitored

        Returns:
            Dictionary of alert evaluations
        """
        logger.info(f"Evaluating MWMB alerts for {service_name} (SLO {slo_percentage}%)")

        alert_results = {
            'service': service_name,
            'slo': slo_percentage,
            'evaluated_at': datetime.utcnow(),
            'alerts': [],
            'overall_status': SLOStatus.HEALTHY.value
        }

        rules = MWMBAlertingFramework.get_alert_rules(slo_percentage)

        for rule in rules:
            window_minutes = rule['window_minutes']

            # Filter data for window
            cutoff_time = datetime.utcnow() - timedelta(minutes=window_minutes)
            window_data = metrics_data[metrics_data['timestamp'] >= cutoff_time]

            if len(window_data) == 0:
                logger.warning(f"No data for {rule['name']} window")
                continue

            # Calculate error rate and burn rate
            total_errors = window_data['errors'].sum()
            total_requests = window_data['total_requests'].sum()

            if total_requests == 0:
                continue

            error_rate = total_errors / total_requests
            burn_rate = SLOCalculator.calculate_burn_rate(
                total_errors,
                total_requests,
                window_minutes * 60
            )

            # Check if alert should fire
            alert_fired = burn_rate >= rule['burn_rate_threshold']

            alert_result = {
                'rule': rule['name'],
                'window_minutes': window_minutes,
                'error_rate': f"{error_rate*100:.2f}%",
                'burn_rate': f"{burn_rate:.1f}x",
                'threshold': f"{rule['burn_rate_threshold']:.1f}x",
                'fired': alert_fired,
                'severity': rule['severity'],
                'action': rule['action']
            }

            alert_results['alerts'].append(alert_result)

            # Update overall status
            if alert_fired:
                if rule['severity'] == 'CRITICAL':
                    alert_results['overall_status'] = SLOStatus.VIOLATED.value
                elif alert_results['overall_status'] != SLOStatus.VIOLATED.value:
                    alert_results['overall_status'] = SLOStatus.WARNING.value

            logger.info(f"  {rule['name']}: Burn rate {burn_rate:.1f}x "
                       f"(threshold {rule['burn_rate_threshold']:.1f}x) - "
                       f"{'FIRED' if alert_fired else 'OK'}")

        return alert_results


class ErrorBudgetTracker:
    """Track error budget consumption over time"""

    def __init__(self, db_connection=None):
        self.db = db_connection
        self.budgets = {}

    def track_error_budget(self, service_name: str, slo_def: SLODefinition,
                          errors: int, total_requests: int):
        """Track error budget for a service"""

        error_budget = SLOCalculator.track_error_budget(
            errors,
            total_requests,
            slo_def.objective * 100
        )

        key = f"{service_name}:{slo_def.name}"
        self.budgets[key] = {
            'service': service_name,
            'slo': slo_def.name,
            'timestamp': datetime.utcnow(),
            **error_budget
        }

        # Log warning if budget getting low
        if error_budget['remaining_percentage'] < 25:
            logger.warning(
                f"Low error budget for {service_name}: "
                f"{error_budget['remaining_percentage']:.1f}% remaining"
            )

    def get_error_budget_report(self, service_name: Optional[str] = None) -> List[Dict]:
        """Get error budget report for service(s)"""

        report = []
        for key, budget in self.budgets.items():
            if service_name is None or budget['service'] == service_name:
                report.append(budget)

        # Sort by remaining percentage
        report.sort(key=lambda x: x['remaining_percentage'])

        return report

    def get_critical_services(self, threshold: float = 25.0) -> List[Dict]:
        """Get services with error budget below threshold"""

        critical = []
        for budget in self.budgets.values():
            if budget['remaining_percentage'] < threshold:
                critical.append({
                    'service': budget['service'],
                    'slo': budget['slo'],
                    'remaining_percentage': budget['remaining_percentage'],
                    'status': 'CRITICAL' if budget['remaining_percentage'] < 10 else 'WARNING'
                })

        return sorted(critical, key=lambda x: x['remaining_percentage'])


# Example usage
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    # Create sample metrics data
    timestamps = pd.date_range('2024-11-21', periods=1440, freq='1min')
    errors = np.random.poisson(lam=0.1, size=1440)  # ~10% error rate
    total_requests = np.random.poisson(lam=100, size=1440)

    metrics_df = pd.DataFrame({
        'timestamp': timestamps,
        'errors': errors,
        'total_requests': total_requests
    })

    # Evaluate MWMB alerts
    results = MWMBAlertingFramework.evaluate_mwmb_alerts(
        metrics_df,
        slo_percentage=99.9,
        service_name='api-server'
    )

    print(f"\n=== SLO Status: {results['overall_status']} ===")
    for alert in results['alerts']:
        status = '🔴 FIRED' if alert['fired'] else '🟢 OK'
        print(f"{status} {alert['rule']}: {alert['error_rate']} "
              f"(burn rate: {alert['burn_rate']} vs threshold {alert['threshold']})")

    # Track error budget
    tracker = ErrorBudgetTracker()
    slo_def = SLODefinition(
        name='availability',
        service='api-server',
        objective=0.999
    )

    tracker.track_error_budget('api-server', slo_def, errors.sum(), total_requests.sum())

    # Report
    report = tracker.get_error_budget_report('api-server')
    for budget in report:
        print(f"\n{budget['service']}: "
              f"{budget['remaining_percentage']:.1f}% budget remaining")

    # Critical services
    critical = tracker.get_critical_services(threshold=25)
    if critical:
        print("\n⚠️ CRITICAL SERVICES:")
        for svc in critical:
            print(f"  {svc['service']}: {svc['remaining_percentage']:.1f}%")
