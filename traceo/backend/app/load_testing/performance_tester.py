#!/usr/bin/env python3
"""
Advanced Load Testing & Performance Framework
K6 integration with continuous CI/CD performance gates
Date: November 21, 2024
"""

import logging
import json
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import statistics

logger = logging.getLogger(__name__)


class TestPhase(Enum):
    """Load testing phases"""
    RAMP_UP = 'ramp_up'
    STEADY_STATE = 'steady_state'
    SPIKE = 'spike'
    RAMP_DOWN = 'ramp_down'


class MetricType(Enum):
    """Performance metric types"""
    RESPONSE_TIME = 'response_time'
    THROUGHPUT = 'throughput'
    ERROR_RATE = 'error_rate'
    RESOURCE_USAGE = 'resource_usage'
    AVAILABILITY = 'availability'


@dataclass
class PerformanceThreshold:
    """Performance threshold for gating"""
    metric: MetricType
    percentile: int  # 50, 95, 99
    threshold_value: float
    unit: str  # ms, req/s, %, bytes
    direction: str  # above, below


@dataclass
class LoadTestConfig:
    """Load test configuration"""
    test_name: str
    target_url: str
    duration_seconds: int
    ramp_up_duration: int
    num_users: int
    thresholds: List[PerformanceThreshold] = field(default_factory=list)
    custom_headers: Dict[str, str] = field(default_factory=dict)
    timeout_seconds: int = 30
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class MetricPoint:
    """Single metric data point"""
    timestamp: datetime
    phase: TestPhase
    metric_type: MetricType
    value: float
    percentile: Optional[int] = None
    sample_size: int = 0


@dataclass
class LoadTestResult:
    """Result of load test"""
    test_name: str
    status: str  # passed, failed, error
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: int = 0

    # Metrics
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    error_rate: float = 0.0

    # Latency
    latency_p50: float = 0.0
    latency_p95: float = 0.0
    latency_p99: float = 0.0
    latency_mean: float = 0.0

    # Throughput
    throughput_rps: float = 0.0

    # Thresholds
    threshold_breaches: List[str] = field(default_factory=list)

    # Details
    metric_history: List[MetricPoint] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


class K6TestScriptBuilder:
    """Build K6 load test scripts"""

    @staticmethod
    def generate_test_script(config: LoadTestConfig) -> str:
        """Generate K6 JavaScript test script"""

        script = f'''
import http from 'k6/http';
import {{ check, sleep, group }} from 'k6';
import {{ Trend, Counter, Gauge, Rate }} from 'k6/metrics';

// Custom metrics
const responseTime = new Trend('response_time');
const errorRate = new Rate('error_rate');
const throughput = new Counter('http_requests_total');
const activeUsers = new Gauge('active_users');

export const options = {{
  stages: [
    {{ duration: '{config.ramp_up_duration}s', target: {config.num_users} }},
    {{ duration: '{config.duration_seconds - config.ramp_up_duration - 60}s', target: {config.num_users} }},
    {{ duration: '60s', target: 0 }}
  ],
  thresholds: {{
    'http_req_duration': ['p(95)<{self._get_latency_threshold(config)}', 'p(99)<{self._get_latency_threshold(config) * 1.5}'],
    'error_rate': ['rate<0.05'],
    'http_req_failed': ['rate<0.1']
  }},
  vus: {config.num_users},
  duration: '{config.duration_seconds}s',
  tags: {{
    test: '{config.test_name}',
    timestamp: new Date().toISOString()
  }}
}};

export default function() {{
  const url = '{config.target_url}';
  const headers = {{
    'Content-Type': 'application/json',
{self._format_headers(config)}
  }};

  activeUsers.set(__VU);

  group('API Request', function() {{
    const response = http.get(url, {{ headers, timeout: '{config.timeout_seconds}s' }});

    responseTime.add(response.timings.duration);
    throughput.add(1);

    const isSuccess = response.status === 200;
    errorRate.add(!isSuccess);

    check(response, {{
      'status is 200': (r) => r.status === 200,
      'response time < {self._get_latency_threshold(config)}ms': (r) => r.timings.duration < {self._get_latency_threshold(config)},
      'body not empty': (r) => r.body.length > 0
    }});
  }});

  sleep(1);
}}
'''
        return script

    @staticmethod
    def _get_latency_threshold(config: LoadTestConfig) -> int:
        """Get latency threshold from config"""
        for threshold in config.thresholds:
            if threshold.metric == MetricType.RESPONSE_TIME:
                return int(threshold.threshold_value)
        return 500  # Default 500ms

    @staticmethod
    def _format_headers(config: LoadTestConfig) -> str:
        """Format custom headers for script"""
        if not config.custom_headers:
            return ""

        lines = []
        for key, value in config.custom_headers.items():
            lines.append(f"    '{key}': '{value}'")
        return ",\n".join(lines)


class LoadTestRunner:
    """Run load tests using K6"""

    def __init__(self, k6_binary: str = "k6"):
        self.k6_binary = k6_binary
        self.results: Dict[str, LoadTestResult] = {}

    def run_test(self, config: LoadTestConfig) -> LoadTestResult:
        """Run load test and return results"""

        logger.info(f"Starting load test: {config.test_name}")
        logger.info(f"Configuration: {config.num_users} users, {config.duration_seconds}s duration")

        start_time = datetime.utcnow()

        try:
            # Generate test script
            script = K6TestScriptBuilder.generate_test_script(config)
            script_file = f"/tmp/k6_test_{config.test_name}.js"

            with open(script_file, 'w') as f:
                f.write(script)

            # Run K6 test
            result = self._execute_k6_test(script_file, config)

            # Parse results
            test_result = self._parse_k6_output(result, config, start_time)

            # Generate recommendations
            test_result.recommendations = self._generate_recommendations(test_result, config)

            self.results[config.test_name] = test_result

            logger.info(f"Test completed: {config.test_name} - Status: {test_result.status}")

            return test_result

        except Exception as e:
            logger.error(f"Test execution failed: {e}")
            return LoadTestResult(
                test_name=config.test_name,
                status="error",
                start_time=start_time,
                recommendations=[f"Error: {str(e)}"]
            )

    def _execute_k6_test(self, script_file: str, config: LoadTestConfig) -> Dict:
        """Execute K6 test and capture output"""

        cmd = [
            self.k6_binary,
            "run",
            script_file,
            "--out", "json=/tmp/k6_results.json",
            "-e", f"TARGET_URL={config.target_url}",
            "-e", f"TEST_NAME={config.test_name}"
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=config.duration_seconds + 300
            )

            # Parse JSON results
            with open('/tmp/k6_results.json', 'r') as f:
                return json.load(f)

        except subprocess.TimeoutExpired:
            logger.error("K6 test execution timeout")
            raise

    def _parse_k6_output(self, k6_output: Dict, config: LoadTestConfig,
                        start_time: datetime) -> LoadTestResult:
        """Parse K6 JSON output"""

        metrics = k6_output.get('metrics', {})

        # Extract key metrics
        http_duration = metrics.get('http_req_duration', {})
        http_requests = metrics.get('http_reqs', {})
        errors = metrics.get('http_req_failed', {})

        result = LoadTestResult(
            test_name=config.test_name,
            start_time=start_time,
            end_time=datetime.utcnow(),
            duration_seconds=config.duration_seconds,
            total_requests=int(http_requests.get('value', 0)),
            successful_requests=int(http_requests.get('value', 0)) - int(errors.get('value', 0)),
            failed_requests=int(errors.get('value', 0)),
            error_rate=float(errors.get('rate', 0)),
            latency_p50=float(http_duration.get('values', {}).get('p(50)', 0)),
            latency_p95=float(http_duration.get('values', {}).get('p(95)', 0)),
            latency_p99=float(http_duration.get('values', {}).get('p(99)', 0)),
            latency_mean=float(http_duration.get('value', 0)),
            throughput_rps=float(http_requests.get('rate', 0))
        )

        # Check threshold breaches
        result.threshold_breaches = self._check_thresholds(result, config)
        result.status = "passed" if not result.threshold_breaches else "failed"

        return result

    def _check_thresholds(self, result: LoadTestResult,
                         config: LoadTestConfig) -> List[str]:
        """Check if thresholds were breached"""

        breaches = []

        for threshold in config.thresholds:
            current_value = None

            if threshold.metric == MetricType.RESPONSE_TIME:
                if threshold.percentile == 50:
                    current_value = result.latency_p50
                elif threshold.percentile == 95:
                    current_value = result.latency_p95
                elif threshold.percentile == 99:
                    current_value = result.latency_p99
                elif threshold.percentile == 0:
                    current_value = result.latency_mean

            elif threshold.metric == MetricType.ERROR_RATE:
                current_value = result.error_rate * 100

            elif threshold.metric == MetricType.THROUGHPUT:
                current_value = result.throughput_rps

            if current_value is not None:
                if threshold.direction == "below" and current_value > threshold.threshold_value:
                    breaches.append(
                        f"{threshold.metric.value}[p{threshold.percentile}]: "
                        f"{current_value:.2f} {threshold.unit} exceeds {threshold.threshold_value}"
                    )
                elif threshold.direction == "above" and current_value < threshold.threshold_value:
                    breaches.append(
                        f"{threshold.metric.value}[p{threshold.percentile}]: "
                        f"{current_value:.2f} {threshold.unit} below {threshold.threshold_value}"
                    )

        return breaches

    def _generate_recommendations(self, result: LoadTestResult,
                                 config: LoadTestConfig) -> List[str]:
        """Generate recommendations based on test results"""

        recommendations = []

        # Latency recommendations
        if result.latency_p95 > 500:
            recommendations.append(
                f"p95 latency is {result.latency_p95:.0f}ms. Consider caching, "
                "database optimization, or horizontal scaling."
            )

        if result.latency_p99 > 1000:
            recommendations.append(
                f"p99 latency is {result.latency_p99:.0f}ms (very high tail latency). "
                "Investigate slow queries, GC pauses, or network issues."
            )

        # Error rate recommendations
        if result.error_rate > 0.01:
            recommendations.append(
                f"Error rate is {result.error_rate * 100:.2f}%. "
                "Review logs for error patterns and investigate root causes."
            )

        # Throughput recommendations
        if result.throughput_rps < 100:
            recommendations.append(
                f"Throughput is only {result.throughput_rps:.1f} req/s. "
                "This may indicate performance bottlenecks or resource limits."
            )

        # Success recommendations
        if result.status == "passed":
            recommendations.append(
                f"✅ All performance thresholds met. System maintains {result.throughput_rps:.1f} req/s "
                f"with p95 latency of {result.latency_p95:.0f}ms."
            )

        return recommendations

    def get_test_report(self, test_name: str) -> Dict:
        """Get detailed test report"""

        if test_name not in self.results:
            return {}

        result = self.results[test_name]

        return {
            'test_name': result.test_name,
            'status': result.status,
            'start_time': result.start_time.isoformat(),
            'end_time': result.end_time.isoformat() if result.end_time else None,
            'duration_seconds': result.duration_seconds,
            'requests': {
                'total': result.total_requests,
                'successful': result.successful_requests,
                'failed': result.failed_requests,
                'error_rate': f"{result.error_rate * 100:.2f}%"
            },
            'latency_ms': {
                'p50': f"{result.latency_p50:.1f}",
                'p95': f"{result.latency_p95:.1f}",
                'p99': f"{result.latency_p99:.1f}",
                'mean': f"{result.latency_mean:.1f}"
            },
            'throughput': {
                'rps': f"{result.throughput_rps:.1f}"
            },
            'threshold_breaches': result.threshold_breaches,
            'recommendations': result.recommendations
        }


class ContinuousPerformanceGate:
    """CI/CD performance gating"""

    def __init__(self, baseline_metrics: Dict[str, float] = None):
        self.baseline_metrics = baseline_metrics or {}
        self.regression_threshold = 0.10  # 10% regression is failure

    def evaluate_gate(self, current_result: LoadTestResult,
                     baseline_name: str = "main") -> tuple[bool, List[str]]:
        """Evaluate if performance test passes gate"""

        failures = []

        # Check for regressions
        if baseline_name in self.baseline_metrics:
            baseline = self.baseline_metrics[baseline_name]

            # Latency regression
            if current_result.latency_p95 > baseline['latency_p95'] * (1 + self.regression_threshold):
                failures.append(
                    f"p95 latency regressed: {current_result.latency_p95:.0f}ms "
                    f"(baseline: {baseline['latency_p95']:.0f}ms)"
                )

            # Error rate regression
            if current_result.error_rate > baseline['error_rate'] * (1 + self.regression_threshold):
                failures.append(
                    f"Error rate regressed: {current_result.error_rate * 100:.2f}% "
                    f"(baseline: {baseline['error_rate'] * 100:.2f}%)"
                )

            # Throughput regression
            if current_result.throughput_rps < baseline['throughput_rps'] * (1 - self.regression_threshold):
                failures.append(
                    f"Throughput degraded: {current_result.throughput_rps:.1f} req/s "
                    f"(baseline: {baseline['throughput_rps']:.1f} req/s)"
                )

        passed = len(failures) == 0
        return passed, failures

    def set_baseline(self, test_name: str, result: LoadTestResult):
        """Set baseline metrics for future comparisons"""

        self.baseline_metrics[test_name] = {
            'latency_p95': result.latency_p95,
            'latency_p99': result.latency_p99,
            'error_rate': result.error_rate,
            'throughput_rps': result.throughput_rps,
            'timestamp': datetime.utcnow().isoformat()
        }

        logger.info(f"Baseline set for {test_name}")


# Example usage
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    # Create test configuration
    config = LoadTestConfig(
        test_name='api-server-health',
        target_url='http://localhost:8000/health',
        duration_seconds=300,
        ramp_up_duration=30,
        num_users=50,
        thresholds=[
            PerformanceThreshold(
                metric=MetricType.RESPONSE_TIME,
                percentile=95,
                threshold_value=500,
                unit='ms',
                direction='below'
            ),
            PerformanceThreshold(
                metric=MetricType.ERROR_RATE,
                percentile=0,
                threshold_value=0.05,
                unit='%',
                direction='below'
            )
        ],
        custom_headers={'Authorization': 'Bearer test-token'}
    )

    # Run test
    runner = LoadTestRunner()
    result = runner.run_test(config)

    # Get report
    report = runner.get_test_report('api-server-health')
    print("\n=== Load Test Report ===")
    print(json.dumps(report, indent=2))

    # Evaluate gate
    gate = ContinuousPerformanceGate()
    gate.set_baseline('main', result)

    passed, failures = gate.evaluate_gate(result, 'main')
    print(f"\n=== Gate Evaluation ===")
    print(f"Status: {'✅ PASSED' if passed else '❌ FAILED'}")
    if failures:
        for failure in failures:
            print(f"  • {failure}")
