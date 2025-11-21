#!/usr/bin/env python3
"""
Chaos Engineering & Resilience Testing Integration
SLO validation through chaos experiments
Date: November 21, 2024
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import statistics

logger = logging.getLogger(__name__)


class ChaosExperimentType(Enum):
    """Types of chaos experiments"""
    CPU_STRESS = 'cpu_stress'
    MEMORY_STRESS = 'memory_stress'
    NETWORK_LATENCY = 'network_latency'
    NETWORK_PACKET_LOSS = 'packet_loss'
    POD_FAILURE = 'pod_failure'
    DISK_IO_STRESS = 'disk_io_stress'
    DNS_FAILURE = 'dns_failure'
    DATABASE_DELAY = 'database_delay'


class ExperimentStatus(Enum):
    """Experiment status"""
    PLANNING = 'planning'
    RUNNING = 'running'
    COMPLETED = 'completed'
    FAILED = 'failed'
    ROLLED_BACK = 'rolled_back'


@dataclass
class ChaosExperiment:
    """Chaos experiment definition"""
    experiment_id: str
    name: str
    description: str
    experiment_type: ChaosExperimentType
    target_service: str
    duration_seconds: int
    blast_radius: str  # pod, node, service
    parameters: Dict = field(default_factory=dict)
    expected_behavior: str = ""
    slo_target: Optional[float] = None  # Target SLO during chaos (e.g., 99.0%)
    created_at: datetime = field(default_factory=datetime.utcnow)
    status: ExperimentStatus = ExperimentStatus.PLANNING


@dataclass
class MetricPoint:
    """Single metric data point"""
    timestamp: datetime
    metric_name: str
    value: float
    tags: Dict = field(default_factory=dict)


@dataclass
class ExperimentResult:
    """Result of chaos experiment"""
    experiment_id: str
    status: ExperimentStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: int = 0
    metrics_collected: List[MetricPoint] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    slo_breached: bool = False
    slo_achieved: float = 0.0
    recommendations: List[str] = field(default_factory=list)


class ExperimentRunner:
    """Run chaos experiments"""

    def __init__(self):
        self.experiments: Dict[str, ChaosExperiment] = {}
        self.results: Dict[str, ExperimentResult] = {}

    def create_experiment(self, experiment: ChaosExperiment):
        """Create new experiment"""
        self.experiments[experiment.experiment_id] = experiment
        logger.info(f"Created experiment: {experiment.name}")

    def run_experiment(self, experiment_id: str,
                      metrics_collector: Callable) -> ExperimentResult:
        """
        Run chaos experiment.

        Args:
            experiment_id: ID of experiment to run
            metrics_collector: Function to collect metrics during experiment

        Returns:
            ExperimentResult with findings
        """

        if experiment_id not in self.experiments:
            logger.error(f"Experiment not found: {experiment_id}")
            return None

        experiment = self.experiments[experiment_id]
        experiment.status = ExperimentStatus.RUNNING

        logger.info(f"Starting experiment: {experiment.name}")
        logger.info(f"Target: {experiment.target_service}, "
                   f"Duration: {experiment.duration_seconds}s")

        start_time = datetime.utcnow()

        try:
            # Inject chaos (simulated)
            self._inject_chaos(experiment)

            # Collect metrics during experiment
            metrics = []
            end_time = start_time + timedelta(seconds=experiment.duration_seconds)

            while datetime.utcnow() < end_time:
                metric = metrics_collector()
                if metric:
                    metrics.append(metric)

            # Analyze results
            result = self._analyze_results(experiment, metrics, start_time)
            experiment.status = ExperimentStatus.COMPLETED

            self.results[experiment_id] = result
            logger.info(f"Experiment completed: {experiment.name}")

            return result

        except Exception as e:
            logger.error(f"Experiment failed: {e}")
            experiment.status = ExperimentStatus.FAILED
            return None

    @staticmethod
    def _inject_chaos(experiment: ChaosExperiment):
        """Inject chaos (simulated)"""

        chaos_config = {
            ChaosExperimentType.CPU_STRESS: {
                'description': 'High CPU utilization',
                'parameters': ['workers', 'load']
            },
            ChaosExperimentType.MEMORY_STRESS: {
                'description': 'High memory utilization',
                'parameters': ['size', 'duration']
            },
            ChaosExperimentType.NETWORK_LATENCY: {
                'description': 'Network latency injection',
                'parameters': ['latency_ms', 'jitter_ms']
            },
            ChaosExperimentType.NETWORK_PACKET_LOSS: {
                'description': 'Packet loss injection',
                'parameters': ['loss_percentage', 'correlation']
            }
        }

        config = chaos_config.get(experiment.experiment_type, {})
        logger.info(f"Injecting chaos: {config.get('description', 'Unknown')}")
        logger.info(f"Parameters: {experiment.parameters}")

    @staticmethod
    def _analyze_results(experiment: ChaosExperiment,
                        metrics: List[MetricPoint],
                        start_time: datetime) -> ExperimentResult:
        """Analyze experiment results"""

        result = ExperimentResult(
            experiment_id=experiment.experiment_id,
            status=ExperimentStatus.COMPLETED,
            start_time=start_time,
            end_time=datetime.utcnow(),
            duration_seconds=experiment.duration_seconds,
            metrics_collected=metrics
        )

        # Calculate SLO achievement
        if metrics and experiment.slo_target:
            # Extract success/failure metrics
            successes = [m.value for m in metrics if 'success' in m.metric_name]
            if successes:
                availability = statistics.mean(successes) * 100
                result.slo_achieved = availability
                result.slo_breached = availability < experiment.slo_target

                logger.info(f"SLO achievement: {availability:.1f}% "
                           f"(target: {experiment.slo_target}%)")

        # Generate recommendations
        result.recommendations = ExperimentRunner._generate_recommendations(experiment, result)

        return result

    @staticmethod
    def _generate_recommendations(experiment: ChaosExperiment,
                                 result: ExperimentResult) -> List[str]:
        """Generate recommendations based on results"""

        recommendations = []

        if result.slo_breached:
            recommendations.append(
                f"SLO target ({experiment.slo_target}%) not met. "
                f"Achieved {result.slo_achieved:.1f}%. "
                f"Review resilience mechanisms."
            )

        if experiment.experiment_type == ChaosExperimentType.CPU_STRESS:
            recommendations.append(
                "Consider implementing CPU throttling, "
                "load shedding, or auto-scaling."
            )

        if experiment.experiment_type == ChaosExperimentType.MEMORY_STRESS:
            recommendations.append(
                "Implement memory limits, circuit breakers, "
                "or graceful degradation."
            )

        if experiment.experiment_type == ChaosExperimentType.NETWORK_LATENCY:
            recommendations.append(
                "Add request timeouts, retries with exponential backoff, "
                "and bulkheads."
            )

        if experiment.experiment_type == ChaosExperimentType.POD_FAILURE:
            recommendations.append(
                "Ensure proper health checks, readiness probes, "
                "and replica distribution across nodes."
            )

        if not result.slo_breached:
            recommendations.append(
                "✅ Service maintained SLO during chaos. "
                "Resilience verified."
            )

        return recommendations

    def get_experiment_report(self, experiment_id: str) -> Dict:
        """Get detailed experiment report"""

        if experiment_id not in self.results:
            return {}

        result = self.results[experiment_id]
        experiment = self.experiments[experiment_id]

        return {
            'experiment_id': experiment_id,
            'name': experiment.name,
            'type': experiment.experiment_type.value,
            'target_service': experiment.target_service,
            'status': result.status.value,
            'duration_seconds': result.duration_seconds,
            'slo_target': experiment.slo_target,
            'slo_achieved': result.slo_achieved,
            'slo_breached': result.slo_breached,
            'metrics_collected': len(result.metrics_collected),
            'errors': result.errors,
            'recommendations': result.recommendations,
            'start_time': result.start_time.isoformat(),
            'end_time': result.end_time.isoformat() if result.end_time else None
        }


class ResilienceTester:
    """Comprehensive resilience testing suite"""

    def __init__(self):
        self.runner = ExperimentRunner()
        self.test_suite = []
        self.results = []

    def add_standard_experiments(self, service_name: str, slo_target: float = 99.9):
        """Add standard resilience test experiments"""

        standard_experiments = [
            ChaosExperiment(
                experiment_id=f'{service_name}-cpu-stress',
                name=f'{service_name} CPU Stress',
                description='Test service resilience under high CPU load',
                experiment_type=ChaosExperimentType.CPU_STRESS,
                target_service=service_name,
                duration_seconds=300,
                blast_radius='pod',
                parameters={'workers': 4, 'load': 80},
                slo_target=slo_target * 0.99  # Allow 1% SLO degradation
            ),
            ChaosExperiment(
                experiment_id=f'{service_name}-memory-stress',
                name=f'{service_name} Memory Stress',
                description='Test service resilience under memory pressure',
                experiment_type=ChaosExperimentType.MEMORY_STRESS,
                target_service=service_name,
                duration_seconds=300,
                blast_radius='pod',
                parameters={'size': '2Gi', 'duration': 300},
                slo_target=slo_target * 0.98
            ),
            ChaosExperiment(
                experiment_id=f'{service_name}-network-latency',
                name=f'{service_name} Network Latency',
                description='Test service resilience with network delays',
                experiment_type=ChaosExperimentType.NETWORK_LATENCY,
                target_service=service_name,
                duration_seconds=300,
                blast_radius='service',
                parameters={'latency_ms': 500, 'jitter_ms': 50},
                slo_target=slo_target * 0.97
            ),
            ChaosExperiment(
                experiment_id=f'{service_name}-packet-loss',
                name=f'{service_name} Packet Loss',
                description='Test service resilience with packet loss',
                experiment_type=ChaosExperimentType.NETWORK_PACKET_LOSS,
                target_service=service_name,
                duration_seconds=300,
                blast_radius='service',
                parameters={'loss_percentage': 5, 'correlation': 50},
                slo_target=slo_target * 0.95
            ),
            ChaosExperiment(
                experiment_id=f'{service_name}-pod-failure',
                name=f'{service_name} Pod Failure',
                description='Test service with pod failure',
                experiment_type=ChaosExperimentType.POD_FAILURE,
                target_service=service_name,
                duration_seconds=60,
                blast_radius='pod',
                parameters={'pods_to_kill': 1},
                slo_target=slo_target
            )
        ]

        for exp in standard_experiments:
            self.runner.create_experiment(exp)
            self.test_suite.append(exp.experiment_id)

    def run_test_suite(self, metrics_collector: Callable) -> List[Dict]:
        """Run all experiments in test suite"""

        logger.info(f"Starting resilience test suite with {len(self.test_suite)} experiments")

        for experiment_id in self.test_suite:
            result = self.runner.run_experiment(experiment_id, metrics_collector)
            if result:
                self.results.append(self.runner.get_experiment_report(experiment_id))

        return self.results

    def generate_resilience_report(self) -> Dict:
        """Generate comprehensive resilience report"""

        if not self.results:
            return {}

        total_experiments = len(self.results)
        passed_experiments = sum(1 for r in self.results if not r['slo_breached'])
        failed_experiments = total_experiments - passed_experiments

        avg_slo_achievement = statistics.mean(
            [r['slo_achieved'] for r in self.results if r['slo_achieved'] > 0]
        ) if self.results else 0

        all_recommendations = []
        for result in self.results:
            all_recommendations.extend(result.get('recommendations', []))

        return {
            'total_experiments': total_experiments,
            'passed_experiments': passed_experiments,
            'failed_experiments': failed_experiments,
            'pass_rate': (passed_experiments / total_experiments * 100) if total_experiments > 0 else 0,
            'average_slo_achievement': avg_slo_achievement,
            'all_recommendations': all_recommendations,
            'detailed_results': self.results,
            'timestamp': datetime.utcnow().isoformat()
        }


# Example usage
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    # Create tester
    tester = ResilienceTester()
    tester.add_standard_experiments('api-server', slo_target=99.9)

    # Mock metrics collector
    def mock_metrics_collector():
        import random
        return MetricPoint(
            timestamp=datetime.utcnow(),
            metric_name='availability',
            value=random.uniform(0.98, 0.999)
        )

    # Run test suite (simulated)
    logger.info("Running resilience test suite...")

    for exp_id in tester.test_suite[:1]:  # Run first experiment only for demo
        result = tester.runner.run_experiment(exp_id, mock_metrics_collector)
        if result:
            report = tester.runner.get_experiment_report(exp_id)
            print(f"\n=== {report['name']} ===")
            print(f"Status: {report['status']}")
            print(f"SLO: {report['slo_achieved']:.1f}% (target: {report['slo_target']:.1f}%)")
            print(f"Result: {'✅ PASSED' if not report['slo_breached'] else '❌ FAILED'}")
            print("Recommendations:")
            for rec in report['recommendations']:
                print(f"  • {rec}")

    # Generate report
    report = tester.generate_resilience_report()
    print(f"\n=== Resilience Test Suite Report ===")
    print(f"Total experiments: {report['total_experiments']}")
    print(f"Passed: {report['passed_experiments']}")
    print(f"Failed: {report['failed_experiments']}")
    print(f"Pass rate: {report['pass_rate']:.1f}%")
    print(f"Average SLO achievement: {report['average_slo_achievement']:.1f}%")
