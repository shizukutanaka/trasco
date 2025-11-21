#!/usr/bin/env python3
"""
Disaster Recovery Orchestrator
Automatic failover with <5 min RTO, <1 min RPO
Date: November 21, 2024
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class RecoveryTier(Enum):
    """Recovery tier SLOs"""
    HOT = 'hot'        # <5 min RTO, <1 min RPO, 3x cost
    WARM = 'warm'      # <30 min RTO, <5 min RPO, 2x cost
    COLD = 'cold'      # <4 hour RTO, <1 hour RPO, 0.1x cost


class FailoverState(Enum):
    """Failover process state"""
    HEALTHY = 'healthy'
    DETECTING = 'detecting'
    DETECTED = 'detected'
    PROMOTING = 'promoting'
    PROMOTED = 'promoted'
    RECOVERING = 'recovering'
    RECOVERED = 'recovered'
    FAILED = 'failed'


@dataclass
class RegionHealth:
    """Region health metrics"""
    region: str
    state: FailoverState
    last_heartbeat: datetime
    consecutive_failures: int = 0
    error_message: Optional[str] = None
    failover_triggered_at: Optional[datetime] = None
    promoted_at: Optional[datetime] = None


@dataclass
class FailoverLog:
    """Failover event log"""
    timestamp: datetime
    source_region: str
    target_region: str
    trigger_reason: str
    detection_time_ms: int
    promotion_time_ms: int
    total_failover_time_ms: int
    data_loss_estimate: int  # records
    status: str
    automation_type: str  # automatic, manual


class FailureDetectionSystem:
    """Detect region failures quickly"""

    DETECTION_THRESHOLD = 3        # 3 consecutive failures
    HEARTBEAT_INTERVAL = 10        # 10 seconds
    HEARTBEAT_TIMEOUT = 30         # 30 second timeout
    DETECTION_WINDOW = 30          # Detect in 30 seconds

    def __init__(self, db_client, monitoring_client):
        self.db = db_client
        self.monitoring = monitoring_client
        self.region_health: Dict[str, RegionHealth] = {}
        self.detection_history: List[Dict] = []

    async def monitor_region(self, region: str) -> bool:
        """Monitor region health with <30 sec detection time"""
        try:
            # Send heartbeat ping
            start_time = datetime.utcnow()

            # Check multiple health indicators
            checks = await asyncio.gather(
                self._check_api_health(region),
                self._check_database_health(region),
                self._check_replication_lag(region),
                return_exceptions=True
            )

            detection_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            # Any failure indicates region issue
            is_healthy = all(c is True for c in checks if not isinstance(c, Exception))

            if is_healthy:
                # Region is healthy, reset failure counter
                if region in self.region_health:
                    self.region_health[region].consecutive_failures = 0
                    self.region_health[region].state = FailoverState.HEALTHY
                    self.region_health[region].last_heartbeat = datetime.utcnow()
            else:
                # Region failed health check
                if region not in self.region_health:
                    self.region_health[region] = RegionHealth(
                        region=region,
                        state=FailoverState.DETECTING,
                        last_heartbeat=datetime.utcnow()
                    )

                self.region_health[region].consecutive_failures += 1
                self.region_health[region].state = FailoverState.DETECTING

                # Log failure
                await self.db.insert('failure_detection_log', {
                    'timestamp': datetime.utcnow(),
                    'region': region,
                    'check_results': {
                        'api_health': checks[0] if not isinstance(checks[0], Exception) else f"Exception: {str(checks[0])}",
                        'database_health': checks[1] if not isinstance(checks[1], Exception) else f"Exception: {str(checks[1])}",
                        'replication_lag': checks[2] if not isinstance(checks[2], Exception) else f"Exception: {str(checks[2])}"
                    },
                    'consecutive_failures': self.region_health[region].consecutive_failures,
                    'detection_time_ms': detection_time
                })

            # Check if failure threshold reached
            if (region in self.region_health and
                self.region_health[region].consecutive_failures >= self.DETECTION_THRESHOLD):
                self.region_health[region].state = FailoverState.DETECTED
                logger.warning(f"Region {region} failure DETECTED (threshold reached in {detection_time}ms)")
                return True

            return False

        except Exception as e:
            logger.error(f"Error monitoring region {region}: {str(e)}")
            return False

    async def _check_api_health(self, region: str) -> bool:
        """Check API endpoint health"""
        try:
            health_response = await asyncio.wait_for(
                self.monitoring.check_endpoint_health(region),
                timeout=self.HEARTBEAT_TIMEOUT / 1000
            )
            return health_response.get('status') == 'healthy'
        except asyncio.TimeoutError:
            logger.warning(f"API health check timeout for {region}")
            return False
        except Exception as e:
            logger.error(f"API health check failed for {region}: {str(e)}")
            return False

    async def _check_database_health(self, region: str) -> bool:
        """Check database connectivity"""
        try:
            db_result = await asyncio.wait_for(
                self.db.health_check(region),
                timeout=self.HEARTBEAT_TIMEOUT / 1000
            )
            return db_result.get('healthy', False)
        except asyncio.TimeoutError:
            logger.warning(f"Database health check timeout for {region}")
            return False
        except Exception as e:
            logger.error(f"Database health check failed for {region}: {str(e)}")
            return False

    async def _check_replication_lag(self, region: str) -> bool:
        """Check replication lag is within SLO"""
        try:
            lag = await self.db.get_replication_lag(region)
            lag_ms = lag.total_seconds() * 1000 if isinstance(lag, timedelta) else lag

            # SLO: <30 seconds (30000 ms)
            if lag_ms > 30000:
                logger.warning(f"Replication lag for {region}: {lag_ms}ms (exceeds SLO)")
                return False
            return True
        except Exception as e:
            logger.error(f"Replication lag check failed for {region}: {str(e)}")
            return False

    async def get_detection_status(self) -> Dict:
        """Get current detection status"""
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'regions': {
                region: {
                    'state': health.state.value,
                    'consecutive_failures': health.consecutive_failures,
                    'last_heartbeat': health.last_heartbeat.isoformat(),
                    'failure_status': 'detected' if health.state == FailoverState.DETECTED else 'healthy'
                }
                for region, health in self.region_health.items()
            }
        }


class AutomaticFailoverSystem:
    """Orchestrate automatic failover and recovery"""

    def __init__(self, db_client, k8s_client, failure_detector, monitoring_client):
        self.db = db_client
        self.k8s = k8s_client
        self.failure_detector = failure_detector
        self.monitoring = monitoring_client
        self.failover_in_progress = False
        self.active_primary = 'us-virginia'      # Default primary
        self.failover_logs: List[FailoverLog] = []

    async def execute_automatic_failover(self, failed_region: str) -> Dict:
        """Execute automatic failover (<30 sec detection + 5 min recovery)"""
        logger.critical(f"INITIATING AUTOMATIC FAILOVER: {failed_region}")

        failover_start = datetime.utcnow()
        failover_log = FailoverLog(
            timestamp=failover_start,
            source_region=failed_region,
            target_region=self._select_failover_target(failed_region),
            trigger_reason='automatic_region_failure_detection',
            detection_time_ms=0,
            promotion_time_ms=0,
            total_failover_time_ms=0,
            data_loss_estimate=0,
            status='in_progress',
            automation_type='automatic'
        )

        try:
            # Update primary region
            old_primary = self.active_primary
            new_primary = failover_log.target_region
            self.active_primary = new_primary

            # Phase 1: Promote secondary (0-2 min)
            await self._promote_secondary_to_primary(new_primary)
            promotion_time = (datetime.utcnow() - failover_start).total_seconds() * 1000

            # Phase 2: Update routing (2-3 min)
            await self._update_dns_routing(failed_region, new_primary)

            # Phase 3: Verify data consistency (3-4 min)
            data_loss = await self._verify_data_consistency(old_primary, new_primary)

            # Phase 4: Alert and notify (4-5 min)
            await self._notify_operations(failed_region, new_primary)

            # Calculate total failover time
            total_failover_time = (datetime.utcnow() - failover_start).total_seconds() * 1000

            failover_log.promotion_time_ms = int(promotion_time)
            failover_log.total_failover_time_ms = int(total_failover_time)
            failover_log.data_loss_estimate = data_loss
            failover_log.status = 'completed'

            logger.critical(f"FAILOVER COMPLETED: {failed_region} → {new_primary} in {total_failover_time/1000:.1f}s")

            # Log failover
            await self.db.insert('failover_logs', failover_log.__dict__)
            self.failover_logs.append(failover_log)

            return {
                'status': 'success',
                'old_primary': old_primary,
                'new_primary': new_primary,
                'failed_region': failed_region,
                'total_failover_time_seconds': total_failover_time / 1000,
                'data_loss_records': data_loss,
                'completed_at': datetime.utcnow().isoformat()
            }

        except Exception as e:
            failover_log.status = 'failed'
            failover_log.total_failover_time_ms = int((datetime.utcnow() - failover_start).total_seconds() * 1000)
            await self.db.insert('failover_logs', failover_log.__dict__)

            logger.critical(f"FAILOVER FAILED for {failed_region}: {str(e)}")
            raise

    async def _promote_secondary_to_primary(self, region: str) -> bool:
        """Promote secondary database to primary (1-2 min)"""
        try:
            logger.info(f"Promoting secondary in {region} to primary")

            # Get secondary database
            secondary = await self.db.get_secondary_instance(region)
            if not secondary:
                raise Exception(f"No secondary found for {region}")

            # Promote to primary
            await self.db.promote_replica(region)

            # Verify promotion
            is_primary = await self.db.verify_is_primary(region)
            if not is_primary:
                raise Exception(f"Failed to promote {region} to primary")

            logger.info(f"Region {region} successfully promoted to primary")
            return True

        except Exception as e:
            logger.error(f"Promotion failed for {region}: {str(e)}")
            raise

    async def _update_dns_routing(self, failed_region: str, new_primary: str) -> bool:
        """Update DNS routing to new primary (<1 min)"""
        try:
            logger.info(f"Updating DNS routing to {new_primary}")

            # Update Route53 weighted routing
            route53_updates = [
                {
                    'region': failed_region,
                    'weight': 0,  # Stop traffic to failed region
                    'set_identifier': f'{failed_region}-failed'
                },
                {
                    'region': new_primary,
                    'weight': 100,  # All traffic to new primary
                    'set_identifier': f'{new_primary}-primary'
                }
            ]

            for update in route53_updates:
                await self.monitoring.update_route53_weight(
                    region=update['region'],
                    weight=update['weight'],
                    set_identifier=update['set_identifier']
                )

            # DNS TTL: 60 seconds, so propagation within 1-2 min
            await asyncio.sleep(5)  # Wait for partial propagation

            # Verify routing
            is_routed = await self.monitoring.verify_routing(new_primary)
            if not is_routed:
                raise Exception(f"Failed to verify routing to {new_primary}")

            logger.info(f"DNS routing updated successfully")
            return True

        except Exception as e:
            logger.error(f"DNS routing update failed: {str(e)}")
            raise

    async def _verify_data_consistency(self, old_primary: str, new_primary: str) -> int:
        """Verify data consistency between old and new primary"""
        try:
            logger.info(f"Verifying data consistency: {old_primary} → {new_primary}")

            # Get record counts
            old_count = await self.db.get_record_count(old_primary)
            new_count = await self.db.get_record_count(new_primary)

            data_loss = max(0, old_count - new_count)

            if data_loss > 0:
                logger.warning(f"Data loss detected: {data_loss} records during failover")

                # Check if within RPO (1 minute = ~1000 records at typical ingestion rate)
                if data_loss > 5000:
                    logger.error(f"Data loss exceeds RPO: {data_loss} records")

            # Verify replication consistency
            consistency = await self.db.verify_replication_consistency(new_primary)
            if not consistency:
                logger.warning(f"Replication consistency check failed for {new_primary}")

            return data_loss

        except Exception as e:
            logger.error(f"Data consistency verification failed: {str(e)}")
            return -1

    async def _notify_operations(self, failed_region: str, new_primary: str) -> bool:
        """Notify operations team of failover"""
        try:
            notification = {
                'title': f'🚨 Automatic Failover Executed: {failed_region}',
                'severity': 'critical',
                'message': f'Region {failed_region} failed. Automatic failover to {new_primary} completed.',
                'timestamp': datetime.utcnow().isoformat(),
                'action_required': True,
                'runbook': 'https://wiki.internal.traceo.io/failover-response'
            }

            # Send to Slack/PagerDuty
            await self.monitoring.send_alert(notification)

            # Create incident
            await self.db.insert('incidents', {
                'timestamp': datetime.utcnow(),
                'type': 'failover',
                'severity': 'critical',
                'description': f'Automatic failover from {failed_region} to {new_primary}',
                'affected_region': failed_region,
                'new_primary': new_primary,
                'status': 'open'
            })

            return True

        except Exception as e:
            logger.error(f"Notification failed: {str(e)}")
            return False

    def _select_failover_target(self, failed_region: str) -> str:
        """Select best failover target region"""
        # Regions sorted by failover preference
        preference_map = {
            'us-virginia': 'eu-frankfurt',
            'eu-frankfurt': 'ap-singapore',
            'cn-beijing': 'ap-tokyo',
            'ap-mumbai': 'ap-singapore',
            'ap-tokyo': 'ap-singapore',
            'ap-singapore': 'us-virginia',
            'sa-sao-paulo': 'us-virginia'
        }
        return preference_map.get(failed_region, 'us-virginia')

    async def recover_failed_region(self, region: str) -> Dict:
        """Recover failed region (after it comes back online)"""
        try:
            logger.info(f"Recovering failed region: {region}")

            # Verify region is healthy
            health = await self.failure_detector.monitor_region(region)
            if not health:
                return {'status': 'region_still_unhealthy'}

            # Rebuild from current primary
            await self._rebuild_region(region)

            # Resume replication
            await self._resume_replication(region)

            # Verify recovery
            recovery_verified = await self.failure_detector.monitor_region(region)
            if not recovery_verified:
                raise Exception(f"Recovery verification failed for {region}")

            logger.info(f"Region {region} recovered successfully")
            return {'status': 'recovered', 'region': region}

        except Exception as e:
            logger.error(f"Recovery failed for {region}: {str(e)}")
            raise

    async def _rebuild_region(self, region: str) -> bool:
        """Rebuild region from snapshots"""
        try:
            logger.info(f"Rebuilding region {region}")

            # Get latest snapshot
            snapshot = await self.db.get_latest_snapshot(self.active_primary)
            if not snapshot:
                raise Exception("No snapshot available for rebuild")

            # Restore snapshot to region
            await self.db.restore_snapshot(region, snapshot)

            logger.info(f"Snapshot restored to {region}")
            return True

        except Exception as e:
            logger.error(f"Rebuild failed for {region}: {str(e)}")
            raise

    async def _resume_replication(self, region: str) -> bool:
        """Resume replication to recovered region"""
        try:
            logger.info(f"Resuming replication to {region}")

            # Get WAL files since snapshot
            wal_position = await self.db.get_wal_position(self.active_primary)

            # Apply WAL files to rebuilt region
            await self.db.apply_wal_files(region, wal_position)

            # Verify replication is current
            lag = await self.db.get_replication_lag(region)
            if lag.total_seconds() > 30:
                logger.warning(f"Replication lag for {region} exceeds SLO: {lag.total_seconds()}s")

            logger.info(f"Replication resumed to {region}")
            return True

        except Exception as e:
            logger.error(f"Replication resume failed for {region}: {str(e)}")
            raise

    async def get_failover_history(self, limit: int = 100) -> List[Dict]:
        """Get failover history"""
        failovers = await self.db.query(f"""
            SELECT *
            FROM failover_logs
            ORDER BY timestamp DESC
            LIMIT {limit}
        """)

        return [dict(f) for f in failovers] if failovers else []

    async def get_failover_metrics(self, hours: int = 24) -> Dict:
        """Get failover statistics"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        metrics = await self.db.query(f"""
            SELECT
                COUNT(*) as total_failovers,
                AVG(total_failover_time_ms) as avg_failover_time_ms,
                MIN(total_failover_time_ms) as min_failover_time_ms,
                MAX(total_failover_time_ms) as max_failover_time_ms,
                SUM(data_loss_estimate) as total_data_loss,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as successful_failovers,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_failovers
            FROM failover_logs
            WHERE timestamp > '{cutoff.isoformat()}'
        """)

        if metrics and metrics[0]:
            return {
                'period_hours': hours,
                'total_failovers': metrics[0]['total_failovers'],
                'avg_failover_time_seconds': (metrics[0]['avg_failover_time_ms'] or 0) / 1000,
                'min_failover_time_seconds': (metrics[0]['min_failover_time_ms'] or 0) / 1000,
                'max_failover_time_seconds': (metrics[0]['max_failover_time_ms'] or 0) / 1000,
                'total_data_loss_records': metrics[0]['total_data_loss'] or 0,
                'successful_failovers': metrics[0]['successful_failovers'] or 0,
                'failed_failovers': metrics[0]['failed_failovers'] or 0,
                'success_rate': (
                    ((metrics[0]['successful_failovers'] or 0) / (metrics[0]['total_failovers'] or 1)) * 100
                )
            }

        return {
            'period_hours': hours,
            'total_failovers': 0,
            'success_rate': 100.0
        }
