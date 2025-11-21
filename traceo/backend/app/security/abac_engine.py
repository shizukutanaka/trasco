#!/usr/bin/env python3
"""
Attribute-Based Access Control (ABAC) Engine for Traceo
Zero-trust security with fine-grained access policies
Date: November 21, 2024
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass, field
from enum import Enum
import json

logger = logging.getLogger(__name__)


class PolicyEffect(Enum):
    """Policy effect types"""
    ALLOW = 'allow'
    DENY = 'deny'


class OperatorType(Enum):
    """Condition operator types"""
    EQUALS = 'equals'
    NOT_EQUALS = 'not_equals'
    IN = 'in'
    NOT_IN = 'not_in'
    CONTAINS = 'contains'
    NOT_CONTAINS = 'not_contains'
    GREATER_THAN = 'greater_than'
    LESS_THAN = 'less_than'
    MATCHES_PATTERN = 'matches_pattern'


@dataclass
class Subject:
    """Subject making the request"""
    user_id: str
    username: str
    groups: List[str] = field(default_factory=list)
    roles: List[str] = field(default_factory=list)
    department: Optional[str] = None
    email: Optional[str] = None
    custom_attributes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            'user_id': self.user_id,
            'username': self.username,
            'groups': self.groups,
            'roles': self.roles,
            'department': self.department,
            'email': self.email,
            'custom_attributes': self.custom_attributes
        }


@dataclass
class Resource:
    """Resource being accessed"""
    resource_id: str
    resource_type: str
    owner: Optional[str] = None
    labels: Dict[str, str] = field(default_factory=dict)
    sensitivity: str = 'normal'  # low, normal, high, critical
    custom_attributes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            'resource_id': self.resource_id,
            'resource_type': self.resource_type,
            'owner': self.owner,
            'labels': self.labels,
            'sensitivity': self.sensitivity,
            'custom_attributes': self.custom_attributes
        }


@dataclass
class Action:
    """Action being performed"""
    action_name: str
    resource_type: str

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            'action_name': self.action_name,
            'resource_type': self.resource_type
        }


@dataclass
class Context:
    """Request context"""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    ip_address: Optional[str] = None
    request_id: Optional[str] = None
    mfa_verified: bool = False
    from_trusted_network: bool = False
    custom_context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'ip_address': self.ip_address,
            'request_id': self.request_id,
            'mfa_verified': self.mfa_verified,
            'from_trusted_network': self.from_trusted_network,
            'custom_context': self.custom_context
        }


class Condition:
    """ABAC condition"""

    def __init__(self, attribute_path: str, operator: OperatorType, value: Any):
        """
        Args:
            attribute_path: Path to attribute (e.g., 'subject.department', 'resource.labels.env')
            operator: Comparison operator
            value: Value to compare against
        """
        self.attribute_path = attribute_path
        self.operator = operator
        self.value = value

    def evaluate(self, subject: Subject, resource: Resource,
                action: Action, context: Context) -> bool:
        """Evaluate condition"""

        # Resolve attribute value
        attribute_value = self._resolve_attribute(attribute_path=self.attribute_path,
                                                  subject=subject,
                                                  resource=resource,
                                                  action=action,
                                                  context=context)

        if attribute_value is None:
            return False

        # Apply operator
        if self.operator == OperatorType.EQUALS:
            return attribute_value == self.value
        elif self.operator == OperatorType.NOT_EQUALS:
            return attribute_value != self.value
        elif self.operator == OperatorType.IN:
            return attribute_value in self.value
        elif self.operator == OperatorType.NOT_IN:
            return attribute_value not in self.value
        elif self.operator == OperatorType.CONTAINS:
            return self.value in attribute_value if isinstance(attribute_value, str) else False
        elif self.operator == OperatorType.NOT_CONTAINS:
            return self.value not in attribute_value if isinstance(attribute_value, str) else True
        elif self.operator == OperatorType.GREATER_THAN:
            return attribute_value > self.value
        elif self.operator == OperatorType.LESS_THAN:
            return attribute_value < self.value
        elif self.operator == OperatorType.MATCHES_PATTERN:
            import re
            return bool(re.match(self.value, str(attribute_value)))
        else:
            return False

    @staticmethod
    def _resolve_attribute(attribute_path: str, subject: Subject,
                         resource: Resource, action: Action, context: Context) -> Any:
        """Resolve attribute path to value"""

        parts = attribute_path.split('.')

        if parts[0] == 'subject':
            obj = subject.to_dict()
        elif parts[0] == 'resource':
            obj = resource.to_dict()
        elif parts[0] == 'action':
            obj = action.to_dict()
        elif parts[0] == 'context':
            obj = context.to_dict()
        else:
            return None

        # Navigate through nested attributes
        for part in parts[1:]:
            if isinstance(obj, dict):
                obj = obj.get(part)
            else:
                return None

        return obj


class ABACPolicy:
    """ABAC policy definition"""

    def __init__(self, policy_id: str, effect: PolicyEffect,
                 subjects: List[str], actions: List[str],
                 resources: List[str], conditions: List[Condition] = None):
        """
        Args:
            policy_id: Unique policy identifier
            effect: ALLOW or DENY
            subjects: Subject patterns (e.g., 'group:engineering', 'user:alice')
            actions: Action patterns (e.g., 'metrics:read', 'dashboard:write')
            resources: Resource patterns (e.g., 'production:*', 'service:api-*')
            conditions: List of conditions that must all be true
        """
        self.policy_id = policy_id
        self.effect = effect
        self.subjects = subjects
        self.actions = actions
        self.resources = resources
        self.conditions = conditions or []
        self.created_at = datetime.utcnow()

    def matches(self, subject: Subject, action: Action,
               resource: Resource, context: Context) -> bool:
        """Check if policy matches request"""

        # Check subject match
        if not self._matches_pattern(f"user:{subject.user_id}", self.subjects):
            # Try groups
            if not any(self._matches_pattern(f"group:{g}", self.subjects)
                      for g in subject.groups):
                # Try roles
                if not any(self._matches_pattern(f"role:{r}", self.subjects)
                          for r in subject.roles):
                    return False

        # Check action match
        if not self._matches_pattern(f"{action.resource_type}:{action.action_name}",
                                    self.actions):
            return False

        # Check resource match
        if not self._matches_pattern(resource.resource_id, self.resources):
            return False

        # Evaluate conditions
        if not all(c.evaluate(subject, resource, action, context) for c in self.conditions):
            return False

        return True

    @staticmethod
    def _matches_pattern(value: str, patterns: List[str]) -> bool:
        """Check if value matches any pattern (supports wildcards)"""
        import fnmatch
        return any(fnmatch.fnmatch(value, pattern) for pattern in patterns)


class ABACEngine:
    """ABAC authorization engine"""

    def __init__(self):
        self.policies: Dict[str, ABACPolicy] = {}
        self.deny_overrides = True  # Deny policies override allow policies
        self.audit_log: List[Dict] = []

    def add_policy(self, policy: ABACPolicy):
        """Add policy to engine"""
        self.policies[policy.policy_id] = policy
        logger.info(f"Added policy: {policy.policy_id}")

    def remove_policy(self, policy_id: str):
        """Remove policy"""
        if policy_id in self.policies:
            del self.policies[policy_id]
            logger.info(f"Removed policy: {policy_id}")

    def authorize(self, subject: Subject, action: Action,
                 resource: Resource, context: Context) -> Tuple[bool, str]:
        """
        Authorize request using ABAC policies.

        Returns:
            (authorized, reason)
        """

        allow_policies = []
        deny_policies = []

        # Find matching policies
        for policy in self.policies.values():
            if policy.matches(subject, action, resource, context):
                if policy.effect == PolicyEffect.ALLOW:
                    allow_policies.append(policy)
                elif policy.effect == PolicyEffect.DENY:
                    deny_policies.append(policy)

        # Decision logic
        authorized = False
        reason = "No matching policies"

        if self.deny_overrides and deny_policies:
            authorized = False
            reason = f"Denied by policies: {[p.policy_id for p in deny_policies]}"
        elif allow_policies:
            authorized = True
            reason = f"Allowed by policies: {[p.policy_id for p in allow_policies]}"

        # Audit log
        self._audit_log(subject, action, resource, context, authorized, reason)

        return authorized, reason

    def _audit_log(self, subject: Subject, action: Action,
                   resource: Resource, context: Context,
                   authorized: bool, reason: str):
        """Log authorization decision"""

        log_entry = {
            'timestamp': datetime.utcnow(),
            'subject': subject.to_dict(),
            'action': action.to_dict(),
            'resource': resource.to_dict(),
            'context': context.to_dict(),
            'authorized': authorized,
            'reason': reason
        }

        self.audit_log.append(log_entry)

        log_level = logging.INFO if authorized else logging.WARNING
        logger.log(
            log_level,
            f"Authorization {'GRANTED' if authorized else 'DENIED'}: "
            f"{subject.username} -> {action.action_name} on {resource.resource_id}: {reason}"
        )

    def get_audit_logs(self, hours: int = 24, user_id: Optional[str] = None) -> List[Dict]:
        """Get audit logs"""

        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        logs = [log for log in self.audit_log if log['timestamp'] >= cutoff_time]

        if user_id:
            logs = [log for log in logs if log['subject']['user_id'] == user_id]

        return logs

    def get_policy_report(self) -> Dict:
        """Generate policy report"""

        allow_count = sum(1 for p in self.policies.values() if p.effect == PolicyEffect.ALLOW)
        deny_count = sum(1 for p in self.policies.values() if p.effect == PolicyEffect.DENY)

        return {
            'total_policies': len(self.policies),
            'allow_policies': allow_count,
            'deny_policies': deny_count,
            'audit_log_entries': len(self.audit_log),
            'recent_denials': len([log for log in self.audit_log[-100:]
                                   if not log['authorized']])
        }


# Example usage
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    # Initialize engine
    engine = ABACEngine()

    # Define policies

    # Policy 1: Engineers can read production metrics
    policy1 = ABACPolicy(
        policy_id='engineering-prod-read',
        effect=PolicyEffect.ALLOW,
        subjects=['group:engineering'],
        actions=['metrics:read', 'logs:read'],
        resources=['production:*'],
        conditions=[
            Condition('context.mfa_verified', OperatorType.EQUALS, True),
            Condition('context.from_trusted_network', OperatorType.EQUALS, True),
        ]
    )
    engine.add_policy(policy1)

    # Policy 2: Finance can access billing data
    policy2 = ABACPolicy(
        policy_id='finance-billing-access',
        effect=PolicyEffect.ALLOW,
        subjects=['group:finance'],
        actions=['billing:read', 'billing:export'],
        resources=['billing:*'],
        conditions=[
            Condition('context.mfa_verified', OperatorType.EQUALS, True),
        ]
    )
    engine.add_policy(policy2)

    # Policy 3: No one can delete production data
    policy3 = ABACPolicy(
        policy_id='deny-prod-delete',
        effect=PolicyEffect.DENY,
        subjects=['*'],
        actions=['data:delete'],
        resources=['production:*']
    )
    engine.add_policy(policy3)

    # Test authorization

    # Test 1: Engineer reading production metrics (should allow)
    subject = Subject(
        user_id='alice',
        username='alice',
        groups=['engineering'],
        email='alice@company.com'
    )
    action = Action(action_name='read', resource_type='metrics')
    resource = Resource(resource_id='production:api-metrics', resource_type='metrics')
    context = Context(
        ip_address='10.0.0.1',
        mfa_verified=True,
        from_trusted_network=True
    )

    authorized, reason = engine.authorize(subject, action, resource, context)
    print(f"\nTest 1: {authorized} - {reason}")

    # Test 2: Engineer deleting production data (should deny)
    action2 = Action(action_name='delete', resource_type='data')
    resource2 = Resource(resource_id='production:database-backup', resource_type='data')

    authorized2, reason2 = engine.authorize(subject, action2, resource2, context)
    print(f"Test 2: {authorized2} - {reason2}")

    # Report
    report = engine.get_policy_report()
    print(f"\n=== Policy Report ===")
    print(f"Total policies: {report['total_policies']}")
    print(f"Allow policies: {report['allow_policies']}")
    print(f"Deny policies: {report['deny_policies']}")
