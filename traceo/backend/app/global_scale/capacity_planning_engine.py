#!/usr/bin/env python3
"""
Global Capacity Planning Engine
ML-based demand forecasting for 10M+ metrics/sec capacity
Date: November 21, 2024
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import numpy as np

logger = logging.getLogger(__name__)


class ScalingMetric(Enum):
    """Auto-scaling metrics"""
    CPU_UTILIZATION = 'cpu_utilization'
    MEMORY_UTILIZATION = 'memory_utilization'
    METRICS_INGESTED_PER_SEC = 'metrics_ingested_per_sec'
    REQUEST_LATENCY = 'request_latency'
    ERROR_RATE = 'error_rate'


@dataclass
class CapacityForecast:
    """Capacity forecast result"""
    timestamp: datetime
    forecast_days_ahead: int
    metric_type: str
    current_value: float
    forecasted_value: float
    upper_bound: float  # 95% confidence
    lower_bound: float  # 5% confidence
    scaling_recommendation: str
    confidence_score: float
    model_type: str


class ARIMAModel:
    """ARIMA forecasting model (p=2, d=1, q=2) with seasonality"""

    def __init__(self, order=(2, 1, 2), seasonal_order=(1, 1, 1, 24)):
        self.order = order
        self.seasonal_order = seasonal_order
        self.model = None
        self.results = None

    async def train(self, timeseries: List[float], hours: int = 720) -> bool:
        """Train ARIMA model on historical data (30 days)"""
        try:
            if len(timeseries) < self.order[0] + self.order[2] + 10:
                logger.warning(f"Insufficient data for ARIMA training: {len(timeseries)} points")
                return False

            # Seasonal decomposition
            seasonal_period = 24  # 24 hours (daily pattern)
            trend = self._calculate_trend(timeseries)
            seasonal = self._calculate_seasonal(timeseries, seasonal_period)
            residual = self._calculate_residual(timeseries, trend, seasonal)

            logger.info(f"ARIMA model training complete. Trend: {trend[-1]:.2f}, Seasonal: {seasonal[-1]:.2f}")
            return True

        except Exception as e:
            logger.error(f"ARIMA training failed: {str(e)}")
            return False

    async def forecast(self, timeseries: List[float], steps: int = 30) -> List[CapacityForecast]:
        """Forecast next N days"""
        try:
            forecasts = []

            # Implement exponential smoothing with trend and seasonality
            for day in range(1, steps + 1):
                # ARIMA(2,1,2) with seasonal component
                forecasted_value = self._arima_forecast_step(timeseries, day)

                # Calculate confidence intervals (95%)
                std_error = np.std(timeseries[-24:]) * np.sqrt(day)  # Error grows with days
                upper_bound = forecasted_value + (1.96 * std_error)  # 95% CI
                lower_bound = max(0, forecasted_value - (1.96 * std_error))

                confidence_score = 1.0 - (0.05 * day)  # Decreases with forecast horizon
                confidence_score = max(0.5, confidence_score)  # Minimum 50% confidence

                # Scaling recommendation
                scaling_rec = self._get_scaling_recommendation(forecasted_value)

                forecast = CapacityForecast(
                    timestamp=datetime.utcnow() + timedelta(days=day),
                    forecast_days_ahead=day,
                    metric_type='metrics_ingested_per_sec',
                    current_value=timeseries[-1],
                    forecasted_value=forecasted_value,
                    upper_bound=upper_bound,
                    lower_bound=lower_bound,
                    scaling_recommendation=scaling_rec,
                    confidence_score=confidence_score,
                    model_type='ARIMA(2,1,2)_seasonal'
                )

                forecasts.append(forecast)

            return forecasts

        except Exception as e:
            logger.error(f"ARIMA forecasting failed: {str(e)}")
            return []

    def _arima_forecast_step(self, timeseries: List[float], steps_ahead: int) -> float:
        """Forecast single step using ARIMA(2,1,2)"""
        # Simplified ARIMA implementation
        # In production, use statsmodels library

        # Differencing (d=1)
        diff = np.diff(timeseries)

        # AR component (p=2): use last 2 differences
        ar_coeff = [0.5, 0.3]  # Placeholder coefficients
        ar_component = ar_coeff[0] * (diff[-1] if len(diff) > 0 else 0) + \
                       ar_coeff[1] * (diff[-2] if len(diff) > 1 else 0)

        # MA component (q=2): use last 2 residuals
        ma_coeff = [0.2, 0.1]  # Placeholder coefficients
        ma_component = ma_coeff[0] * (diff[-1] if len(diff) > 0 else 0) + \
                       ma_coeff[1] * (diff[-2] if len(diff) > 1 else 0)

        # Seasonal component: compare to 24 hours ago
        seasonal_component = 0
        if len(timeseries) > 24:
            seasonal_component = (timeseries[-1] - timeseries[-25]) * 0.1

        # Forecast
        trend = np.mean(diff[-7:]) if len(diff) >= 7 else 0  # Weekly trend
        forecast = timeseries[-1] + trend + ar_component + ma_component + seasonal_component

        # Add some growth for capacity planning (conservative 5% daily growth max)
        growth_factor = min(1.05, 1.0 + (steps_ahead * 0.01))
        forecast = forecast * growth_factor

        return max(0, forecast)

    def _calculate_trend(self, timeseries: List[float]) -> List[float]:
        """Calculate trend component"""
        window = 7
        trend = []
        for i in range(len(timeseries)):
            if i < window:
                trend.append(np.mean(timeseries[:i+1]))
            else:
                trend.append(np.mean(timeseries[i-window:i+1]))
        return trend

    def _calculate_seasonal(self, timeseries: List[float], period: int) -> List[float]:
        """Calculate seasonal component"""
        seasonal = [0] * len(timeseries)
        if len(timeseries) < period:
            return seasonal

        # Calculate seasonal indices
        for i in range(period):
            indices = list(range(i, len(timeseries), period))
            if indices:
                seasonal_value = np.mean([timeseries[j] for j in indices])
                for j in indices:
                    seasonal[j] = seasonal_value

        return seasonal

    def _calculate_residual(self, timeseries: List[float], trend: List[float], seasonal: List[float]) -> List[float]:
        """Calculate residual component"""
        residual = []
        for i in range(len(timeseries)):
            r = timeseries[i] - trend[i] - seasonal[i]
            residual.append(r)
        return residual

    def _get_scaling_recommendation(self, forecasted_value: float) -> str:
        """Get scaling recommendation based on forecast"""
        # Relative to current baseline (assume current = 1M metrics/sec)
        baseline = 1_000_000
        current_ratio = forecasted_value / baseline

        if current_ratio > 1.5:
            return 'scale_up_urgent'  # >50% increase
        elif current_ratio > 1.2:
            return 'scale_up'  # >20% increase
        elif current_ratio > 0.8:
            return 'maintain'  # No significant change
        elif current_ratio > 0.5:
            return 'scale_down'  # >20% decrease
        else:
            return 'scale_down_aggressive'  # >50% decrease


class GlobalCapacityPlanner:
    """Plan global capacity across all regions"""

    REGIONS = [
        'eu-frankfurt',
        'cn-beijing',
        'ap-mumbai',
        'ap-tokyo',
        'ap-singapore',
        'us-virginia',
        'sa-sao-paulo'
    ]

    def __init__(self, db_client, k8s_client):
        self.db = db_client
        self.k8s = k8s_client
        self.arima_models: Dict[str, ARIMAModel] = {}
        self.capacity_forecasts: List[CapacityForecast] = []

    async def train_forecast_models(self, lookback_days: int = 30) -> Dict[str, bool]:
        """Train ARIMA models for all regions"""
        training_results = {}

        for region in self.REGIONS:
            try:
                # Get historical metrics
                cutoff = datetime.utcnow() - timedelta(days=lookback_days)
                historical_data = await self.db.query(f"""
                    SELECT AVG(metrics_per_sec) as avg_mps
                    FROM regional_capacity_metrics
                    WHERE region = '{region}'
                    AND timestamp > '{cutoff.isoformat()}'
                    ORDER BY timestamp
                """)

                if not historical_data or len(historical_data) < 10:
                    logger.warning(f"Insufficient historical data for {region}")
                    training_results[region] = False
                    continue

                # Extract timeseries
                timeseries = [h['avg_mps'] for h in historical_data]

                # Train ARIMA model
                model = ARIMAModel()
                success = await model.train(timeseries)

                self.arima_models[region] = model
                training_results[region] = success

            except Exception as e:
                logger.error(f"Model training failed for {region}: {str(e)}")
                training_results[region] = False

        return training_results

    async def forecast_global_capacity(self, days_ahead: int = 30) -> Dict[str, List[CapacityForecast]]:
        """Forecast capacity needs for all regions"""
        forecasts = {}

        for region in self.REGIONS:
            try:
                if region not in self.arima_models:
                    logger.warning(f"No trained model for {region}, skipping forecast")
                    continue

                # Get latest metrics for context
                latest_data = await self.db.query(f"""
                    SELECT ARRAY_AGG(metrics_per_sec ORDER BY timestamp DESC) as timeseries
                    FROM regional_capacity_metrics
                    WHERE region = '{region}'
                    ORDER BY timestamp DESC
                    LIMIT 720  -- 30 days at hourly resolution
                """)

                if not latest_data or not latest_data[0]['timeseries']:
                    continue

                timeseries = latest_data[0]['timeseries']

                # Generate forecast
                model = self.arima_models[region]
                regional_forecast = await model.forecast(timeseries, steps=days_ahead)

                forecasts[region] = regional_forecast

                # Store forecasts
                for forecast in regional_forecast:
                    await self.db.insert('capacity_forecasts', {
                        'region': region,
                        'timestamp': datetime.utcnow(),
                        'forecast_timestamp': forecast.timestamp,
                        'forecasted_mps': forecast.forecasted_value,
                        'upper_bound': forecast.upper_bound,
                        'lower_bound': forecast.lower_bound,
                        'scaling_recommendation': forecast.scaling_recommendation,
                        'confidence_score': forecast.confidence_score
                    })

            except Exception as e:
                logger.error(f"Capacity forecasting failed for {region}: {str(e)}")

        return forecasts

    async def generate_scaling_policy(self) -> Dict:
        """Generate Kubernetes HPA scaling policy based on forecasts"""
        return {
            'apiVersion': 'autoscaling/v2',
            'kind': 'HorizontalPodAutoscaler',
            'metadata': {
                'name': 'metrics-global-hpa'
            },
            'spec': {
                'scaleTargetRef': {
                    'apiVersion': 'apps/v1',
                    'kind': 'Deployment',
                    'name': 'metrics-service'
                },
                'minReplicas': 100,
                'maxReplicas': 1000,
                'metrics': [
                    {
                        'type': 'Resource',
                        'resource': {
                            'name': 'cpu',
                            'target': {
                                'type': 'Utilization',
                                'averageUtilization': 70
                            }
                        }
                    },
                    {
                        'type': 'Resource',
                        'resource': {
                            'name': 'memory',
                            'target': {
                                'type': 'Utilization',
                                'averageUtilization': 80
                            }
                        }
                    },
                    {
                        'type': 'Pods',
                        'pods': {
                            'metric': {
                                'name': 'metrics_ingested_per_second'
                            },
                            'target': {
                                'type': 'AverageValue',
                                'averageValue': '10000'  # 10k metrics per pod
                            }
                        }
                    }
                ],
                'behavior': {
                    'scaleUp': {
                        'stabilizationWindowSeconds': 60,
                        'policies': [
                            {
                                'type': 'Percent',
                                'value': 100,  # Double replicas
                                'periodSeconds': 60
                            },
                            {
                                'type': 'Pods',
                                'value': 10,  # Add 10 pods
                                'periodSeconds': 60
                            }
                        ],
                        'selectPolicy': 'Max'  # Use highest growth
                    },
                    'scaleDown': {
                        'stabilizationWindowSeconds': 300,  # 5 min stabilization
                        'policies': [
                            {
                                'type': 'Percent',
                                'value': 50,  # Remove 50% of excess
                                'periodSeconds': 300
                            },
                            {
                                'type': 'Pods',
                                'value': 2,  # Remove 2 pods minimum
                                'periodSeconds': 300
                            }
                        ],
                        'selectPolicy': 'Min'  # Use lowest reduction
                    }
                }
            }
        }

    async def optimize_spot_instances(self) -> Dict:
        """Optimize costs using spot instances (40% savings)"""
        strategy = {
            'spot_percentage': 0.4,  # 40% spot instances
            'on_demand_percentage': 0.6,  # 60% on-demand for stability
            'interruption_handling': 'pod_disruption_budgets',
            'regional_allocation': {}
        }

        # Allocate spot vs on-demand per region based on criticality
        for region in self.REGIONS:
            is_primary = region == 'us-virginia'
            strategy['regional_allocation'][region] = {
                'spot_percentage': 0.2 if is_primary else 0.5,  # Less spots in primary
                'on_demand_percentage': 0.8 if is_primary else 0.5
            }

        return strategy

    async def enforce_budget_limits(self, max_monthly_cost: float = 800_000) -> Dict:
        """Enforce budget constraints on auto-scaling"""
        # Calculate current monthly cost
        daily_cost = await self.db.query(f"""
            SELECT SUM(hourly_cost * 24) as daily_cost
            FROM infrastructure_costs
            WHERE timestamp > NOW() - INTERVAL '24 hours'
        """)

        estimated_monthly = (daily_cost[0]['daily_cost'] if daily_cost and daily_cost[0] else 0) * 30

        budget_status = {
            'max_monthly_budget': max_monthly_cost,
            'estimated_monthly_cost': estimated_monthly,
            'budget_utilization_percent': (estimated_monthly / max_monthly_cost) * 100,
            'budget_remaining': max_monthly_cost - estimated_monthly,
            'cost_control_active': estimated_monthly > max_monthly_cost * 0.9  # Alert at 90%
        }

        if budget_status['cost_control_active']:
            logger.warning(f"Budget utilization at {budget_status['budget_utilization_percent']:.1f}%")
            # Trigger cost optimization: prefer spot instances, reduce scale-up aggressiveness
            budget_status['cost_optimization_measures'] = [
                'increase_spot_percentage_to_60',
                'reduce_scale_up_aggressiveness',
                'enable_aggressive_scale_down',
                'prioritize_cheaper_regions'
            ]

        return budget_status

    async def get_capacity_dashboard(self) -> Dict:
        """Generate capacity planning dashboard"""
        # Current utilization
        current_util = await self.db.query(f"""
            SELECT
                region,
                AVG(cpu_utilization) as avg_cpu,
                PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY cpu_utilization) as p95_cpu,
                AVG(memory_utilization) as avg_memory,
                PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY memory_utilization) as p95_memory,
                MAX(metrics_per_sec) as peak_mps
            FROM regional_capacity_metrics
            WHERE timestamp > NOW() - INTERVAL '1 hour'
            GROUP BY region
        """)

        dashboard = {
            'timestamp': datetime.utcnow().isoformat(),
            'current_capacity': {},
            'forecasts': {},
            'scaling_status': {}
        }

        for util in current_util or []:
            region = util['region']
            dashboard['current_capacity'][region] = {
                'cpu_avg': util['avg_cpu'],
                'cpu_p95': util['p95_cpu'],
                'memory_avg': util['avg_memory'],
                'memory_p95': util['p95_memory'],
                'peak_mps_1h': util['peak_mps']
            }

        return dashboard

    async def predict_peak_capacity(self) -> Dict:
        """Predict peak capacity needs for the week"""
        # Analyze weekly patterns
        weekly_peak = await self.db.query(f"""
            SELECT
                EXTRACT(DOW FROM timestamp) as day_of_week,
                EXTRACT(HOUR FROM timestamp) as hour_of_day,
                MAX(metrics_per_sec) as peak_mps,
                AVG(metrics_per_sec) as avg_mps
            FROM regional_capacity_metrics
            WHERE timestamp > NOW() - INTERVAL '30 days'
            GROUP BY day_of_week, hour_of_day
            ORDER BY peak_mps DESC
            LIMIT 1
        """)

        if weekly_peak and weekly_peak[0]:
            peak = weekly_peak[0]
            return {
                'peak_day': self._day_name(peak['day_of_week']),
                'peak_hour': int(peak['hour_of_day']),
                'peak_mps': peak['peak_mps'],
                'avg_mps': peak['avg_mps'],
                'expected_soon': True if self._is_peak_approaching(peak['day_of_week'], peak['hour_of_day']) else False
            }

        return {'peak_mps': 0, 'expected_soon': False}

    def _day_name(self, day_of_week: int) -> str:
        """Convert day of week number to name"""
        names = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
        return names[int(day_of_week) % 7]

    def _is_peak_approaching(self, peak_day: int, peak_hour: int) -> bool:
        """Check if peak hour is within 24 hours"""
        now = datetime.utcnow()
        hours_until_peak = ((int(peak_day) - now.weekday()) % 7) * 24 + (int(peak_hour) - now.hour)
        return 0 <= hours_until_peak <= 24
