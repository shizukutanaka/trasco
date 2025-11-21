#!/usr/bin/env python3
"""
Synthetic Monitoring for Traceo
Proactive monitoring via simulated end-to-end transactions
Date: November 21, 2024
"""

import logging
import asyncio
import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import aiohttp
import random

logger = logging.getLogger(__name__)


class CheckType(Enum):
    """Types of synthetic checks"""
    HTTP = 'http'
    GRPC = 'grpc'
    DATABASE = 'database'
    API_TRANSACTION = 'api_transaction'
    USER_FLOW = 'user_flow'


@dataclass
class CheckResult:
    """Result of synthetic check"""
    check_name: str
    check_type: CheckType
    status: str  # success, failure, timeout
    response_time_ms: float
    timestamp: datetime
    error_message: Optional[str] = None
    location: str = 'primary'  # For multi-region checks


class HTTPCheck:
    """HTTP endpoint synthetic check"""

    def __init__(self, name: str, url: str, method: str = 'GET',
                 timeout: int = 30, expected_status: int = 200):
        self.name = name
        self.url = url
        self.method = method
        self.timeout = timeout
        self.expected_status = expected_status

    async def run(self) -> CheckResult:
        """Execute HTTP check"""
        start_time = time.time()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    self.method, self.url,
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    response_time = (time.time() - start_time) * 1000

                    if response.status == self.expected_status:
                        return CheckResult(
                            check_name=self.name,
                            check_type=CheckType.HTTP,
                            status='success',
                            response_time_ms=response_time,
                            timestamp=datetime.utcnow()
                        )
                    else:
                        return CheckResult(
                            check_name=self.name,
                            check_type=CheckType.HTTP,
                            status='failure',
                            response_time_ms=response_time,
                            timestamp=datetime.utcnow(),
                            error_message=f"Expected {self.expected_status}, got {response.status}"
                        )

        except asyncio.TimeoutError:
            response_time = (time.time() - start_time) * 1000
            return CheckResult(
                check_name=self.name,
                check_type=CheckType.HTTP,
                status='timeout',
                response_time_ms=response_time,
                timestamp=datetime.utcnow(),
                error_message=f"Request timeout after {self.timeout}s"
            )

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return CheckResult(
                check_name=self.name,
                check_type=CheckType.HTTP,
                status='failure',
                response_time_ms=response_time,
                timestamp=datetime.utcnow(),
                error_message=str(e)
            )


class APITransactionCheck:
    """End-to-end API transaction synthetic check"""

    def __init__(self, name: str, base_url: str, steps: List[Dict]):
        self.name = name
        self.base_url = base_url
        self.steps = steps  # List of {method, path, payload, expected_response}

    async def run(self) -> CheckResult:
        """Execute multi-step API transaction"""
        start_time = time.time()
        try:
            async with aiohttp.ClientSession() as session:
                for i, step in enumerate(self.steps):
                    url = f"{self.base_url}{step['path']}"
                    method = step.get('method', 'GET')
                    payload = step.get('payload')

                    async with session.request(
                        method, url, json=payload,
                        timeout=aiohttp.ClientTimeout(total=30)
                    ) as response:
                        if response.status not in [200, 201, 204]:
                            response_time = (time.time() - start_time) * 1000
                            return CheckResult(
                                check_name=self.name,
                                check_type=CheckType.API_TRANSACTION,
                                status='failure',
                                response_time_ms=response_time,
                                timestamp=datetime.utcnow(),
                                error_message=f"Step {i} failed with {response.status}"
                            )

                response_time = (time.time() - start_time) * 1000
                return CheckResult(
                    check_name=self.name,
                    check_type=CheckType.API_TRANSACTION,
                    status='success',
                    response_time_ms=response_time,
                    timestamp=datetime.utcnow()
                )

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return CheckResult(
                check_name=self.name,
                check_type=CheckType.API_TRANSACTION,
                status='failure',
                response_time_ms=response_time,
                timestamp=datetime.utcnow(),
                error_message=str(e)
            )


class UserFlowCheck:
    """Simulated user flow synthetic check"""

    def __init__(self, name: str, base_url: str):
        self.name = name
        self.base_url = base_url

    async def run(self) -> CheckResult:
        """Execute simulated user flow"""
        start_time = time.time()
        try:
            async with aiohttp.ClientSession() as session:
                # Step 1: Login
                async with session.post(
                    f"{self.base_url}/api/auth/login",
                    json={'email': 'test@example.com', 'password': 'test123'}
                ) as response:
                    if response.status != 200:
                        raise Exception(f"Login failed: {response.status}")
                    data = await response.json()
                    token = data.get('token')

                # Step 2: Get dashboard
                headers = {'Authorization': f'Bearer {token}'}
                async with session.get(
                    f"{self.base_url}/api/dashboard",
                    headers=headers
                ) as response:
                    if response.status != 200:
                        raise Exception(f"Dashboard failed: {response.status}")

                # Step 3: Create alert
                async with session.post(
                    f"{self.base_url}/api/alerts",
                    json={'title': 'Test Alert', 'severity': 'warning'},
                    headers=headers
                ) as response:
                    if response.status not in [200, 201]:
                        raise Exception(f"Alert creation failed: {response.status}")

                # Step 4: Logout
                async with session.post(
                    f"{self.base_url}/api/auth/logout",
                    headers=headers
                ) as response:
                    if response.status != 200:
                        raise Exception(f"Logout failed: {response.status}")

                response_time = (time.time() - start_time) * 1000
                return CheckResult(
                    check_name=self.name,
                    check_type=CheckType.USER_FLOW,
                    status='success',
                    response_time_ms=response_time,
                    timestamp=datetime.utcnow()
                )

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return CheckResult(
                check_name=self.name,
                check_type=CheckType.USER_FLOW,
                status='failure',
                response_time_ms=response_time,
                timestamp=datetime.utcnow(),
                error_message=str(e)
            )


class SyntheticMonitoringScheduler:
    """Schedule and execute synthetic checks"""

    def __init__(self, check_interval_seconds: int = 60):
        self.check_interval = check_interval_seconds
        self.checks: List = []
        self.results: List[CheckResult] = []
        self.running = False

    def add_check(self, check):
        """Add a synthetic check"""
        self.checks.append(check)
        logger.info(f"Added check: {check.name}")

    async def run_all_checks(self) -> List[CheckResult]:
        """Run all checks concurrently"""
        logger.info(f"Running {len(self.checks)} synthetic checks...")
        tasks = [check.run() for check in self.checks]
        results = await asyncio.gather(*tasks, return_exceptions=False)
        self.results.extend(results)
        return results

    async def start_scheduler(self):
        """Start continuous monitoring"""
        self.running = True
        logger.info(f"Starting synthetic monitoring scheduler (interval: {self.check_interval}s)")

        while self.running:
            try:
                results = await self.run_all_checks()
                self._log_results(results)
                self._update_metrics(results)
                await asyncio.sleep(self.check_interval)

            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                await asyncio.sleep(self.check_interval)

    def stop_scheduler(self):
        """Stop scheduler"""
        self.running = False
        logger.info("Synthetic monitoring scheduler stopped")

    def _log_results(self, results: List[CheckResult]):
        """Log check results"""
        success_count = sum(1 for r in results if r.status == 'success')
        failure_count = sum(1 for r in results if r.status == 'failure')
        timeout_count = sum(1 for r in results if r.status == 'timeout')

        logger.info(f"Check Results: Success={success_count}, Failure={failure_count}, Timeout={timeout_count}")

        for result in results:
            if result.status != 'success':
                logger.warning(
                    f"  {result.check_name}: {result.status} ({result.response_time_ms:.0f}ms) - {result.error_message}"
                )

    def _update_metrics(self, results: List[CheckResult]):
        """Update Prometheus metrics"""
        # In production, export to Prometheus
        for result in results:
            logger.debug(f"Metric: synthetic_check_duration_ms{{check='{result.check_name}'}} {result.response_time_ms}")

    def get_availability(self, time_window_hours: int = 24) -> Dict:
        """Calculate availability from synthetic checks"""
        cutoff_time = datetime.utcnow() - timedelta(hours=time_window_hours)
        recent_results = [r for r in self.results if r.timestamp >= cutoff_time]

        if not recent_results:
            return {'availability': 0, 'uptime_percentage': 0}

        success_count = sum(1 for r in recent_results if r.status == 'success')
        total_count = len(recent_results)

        availability = (success_count / total_count) * 100 if total_count > 0 else 0

        return {
            'availability': availability,
            'uptime_percentage': availability,
            'total_checks': total_count,
            'successful_checks': success_count,
            'failed_checks': total_count - success_count,
            'time_window_hours': time_window_hours
        }

    def get_slo_status(self, slo_target: float = 99.9) -> Dict:
        """Check if SLO target is met"""
        availability = self.get_availability()['availability']
        slo_met = availability >= slo_target

        return {
            'slo_target': slo_target,
            'actual_availability': availability,
            'slo_met': slo_met,
            'gap_percentage': max(0, slo_target - availability)
        }


class SyntheticMonitoringConfig:
    """Configuration for synthetic monitoring"""

    @staticmethod
    def get_default_checks(base_url: str) -> List:
        """Get default set of synthetic checks"""
        checks = [
            # Health checks
            HTTPCheck(
                name='api_health',
                url=f"{base_url}/health",
                expected_status=200
            ),
            HTTPCheck(
                name='dashboard_endpoint',
                url=f"{base_url}/api/dashboard",
                expected_status=200
            ),

            # API transaction check
            APITransactionCheck(
                name='alert_creation_flow',
                base_url=base_url,
                steps=[
                    {'method': 'POST', 'path': '/api/auth/login', 'payload': {'email': 'test@example.com', 'password': 'test'}},
                    {'method': 'POST', 'path': '/api/alerts', 'payload': {'title': 'Test', 'severity': 'warning'}},
                ]
            ),

            # User flow check
            UserFlowCheck(
                name='end_to_end_user_flow',
                base_url=base_url
            ),
        ]

        return checks

    @staticmethod
    def get_regional_checks(regions: Dict[str, str]) -> List:
        """Get checks for multiple regions"""
        all_checks = []
        for region_name, base_url in regions.items():
            checks = SyntheticMonitoringConfig.get_default_checks(base_url)
            for check in checks:
                if hasattr(check, 'location'):
                    check.location = region_name
            all_checks.extend(checks)

        return all_checks


# Example usage and async entry point
async def run_synthetic_monitoring():
    """Run synthetic monitoring"""
    logger.basicConfig(level=logging.INFO)

    scheduler = SyntheticMonitoringScheduler(check_interval_seconds=60)

    # Add checks
    base_url = 'http://traceo.example.com'
    checks = SyntheticMonitoringConfig.get_default_checks(base_url)
    for check in checks:
        scheduler.add_check(check)

    # Run for demonstration
    try:
        # Run once
        results = await scheduler.run_all_checks()

        # Get availability
        availability = scheduler.get_availability(time_window_hours=24)
        print(json.dumps(availability, indent=2, default=str))

        # Check SLO
        slo_status = scheduler.get_slo_status(slo_target=99.9)
        print(json.dumps(slo_status, indent=2, default=str))

    except KeyboardInterrupt:
        scheduler.stop_scheduler()


if __name__ == '__main__':
    # Run event loop
    asyncio.run(run_synthetic_monitoring())
