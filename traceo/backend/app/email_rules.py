"""
Email filtering rules and auto-action system for Traceo.
Allows users to define custom filtering rules and automatic actions.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import Column, String, Integer, Boolean, JSON, DateTime, desc

from app.database import get_db, Base
from app.security import get_current_user
from app.user_profiles import UserProfile


router = APIRouter(prefix="/rules", tags=["email rules"])


# ===== Database Models =====

class EmailRule(Base):
    """Email filtering rule database model"""
    __tablename__ = "email_rules"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    name = Column(String, index=True)
    description = Column(String, nullable=True)

    # Rule conditions (all conditions must match)
    conditions = Column(JSON, default=list)  # [{field, operator, value}, ...]

    # Actions when rule matches
    actions = Column(JSON, default=list)  # [{type, params}, ...]

    # Settings
    enabled = Column(Boolean, default=True)
    priority = Column(Integer, default=0)  # Higher = executed first

    # Statistics
    matched_count = Column(Integer, default=0)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ===== Pydantic Models =====

class RuleCondition(BaseModel):
    """Rule condition definition"""
    field: str  # from_addr, subject, domain, score, urls_count
    operator: str  # equals, contains, startswith, endswith, greater_than, less_than, in
    value: Any  # Value to compare against


class RuleAction(BaseModel):
    """Rule action definition"""
    type: str  # auto_report, mark_status, flag, forward, delete, archive, add_label
    params: Dict[str, Any] = {}


class EmailRuleCreate(BaseModel):
    """Create email rule"""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    conditions: List[RuleCondition]
    actions: List[RuleAction]
    enabled: bool = True
    priority: int = Field(default=0, ge=0, le=100)


class EmailRuleUpdate(BaseModel):
    """Update email rule"""
    name: Optional[str] = None
    description: Optional[str] = None
    conditions: Optional[List[RuleCondition]] = None
    actions: Optional[List[RuleAction]] = None
    enabled: Optional[bool] = None
    priority: Optional[int] = None


class EmailRuleResponse(BaseModel):
    """Email rule response"""
    id: int
    name: str
    description: Optional[str]
    conditions: List[RuleCondition]
    actions: List[RuleAction]
    enabled: bool
    priority: int
    matched_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ===== Rule Engine =====

class RuleEngine:
    """Email rule evaluation and execution engine"""

    @staticmethod
    def evaluate_condition(email: Any, condition: Dict[str, Any]) -> bool:
        """
        Evaluate a single condition against an email.

        Args:
            email: Email database object
            condition: Condition dict with field, operator, value

        Returns:
            True if condition matches, False otherwise
        """
        field = condition.get('field')
        operator = condition.get('operator')
        value = condition.get('value')

        # Get email field value
        if field == 'from_addr':
            field_value = email.from_addr or ''
        elif field == 'subject':
            field_value = email.subject or ''
        elif field == 'domain':
            # Extract domain from sender
            if '@' in email.from_addr:
                field_value = email.from_addr.split('@')[1]
            else:
                field_value = ''
        elif field == 'score':
            field_value = email.score or 0
        elif field == 'urls_count':
            field_value = len(email.urls) if email.urls else 0
        elif field == 'status':
            field_value = email.status.value if email.status else ''
        else:
            return False

        # Apply operator
        if operator == 'equals':
            return field_value == value
        elif operator == 'contains':
            return str(value).lower() in str(field_value).lower()
        elif operator == 'startswith':
            return str(field_value).lower().startswith(str(value).lower())
        elif operator == 'endswith':
            return str(field_value).lower().endswith(str(value).lower())
        elif operator == 'greater_than':
            try:
                return float(field_value) > float(value)
            except (ValueError, TypeError):
                return False
        elif operator == 'less_than':
            try:
                return float(field_value) < float(value)
            except (ValueError, TypeError):
                return False
        elif operator == 'in':
            return field_value in value if isinstance(value, list) else False
        elif operator == 'regex':
            import re
            try:
                return bool(re.search(value, str(field_value)))
            except re.error:
                return False
        else:
            return False

    @staticmethod
    def evaluate_rule(email: Any, rule: EmailRule) -> bool:
        """
        Evaluate all conditions in a rule.
        All conditions must match (AND logic).

        Args:
            email: Email database object
            rule: EmailRule database object

        Returns:
            True if all conditions match, False otherwise
        """
        if not rule.enabled:
            return False

        conditions = rule.conditions or []
        if not conditions:
            return True

        # All conditions must match
        return all(
            RuleEngine.evaluate_condition(email, cond)
            for cond in conditions
        )

    @staticmethod
    def execute_actions(
        email: Any,
        rule: EmailRule,
        db: Session,
        current_user: Any
    ) -> Dict[str, Any]:
        """
        Execute all actions for a matched rule.

        Args:
            email: Email database object
            rule: EmailRule database object
            db: Database session
            current_user: Current user object

        Returns:
            Dict with execution results
        """
        results = {
            'rule_id': rule.id,
            'rule_name': rule.name,
            'executed_actions': [],
            'errors': []
        }

        actions = rule.actions or []

        for action in actions:
            action_type = action.get('type')
            params = action.get('params', {})

            try:
                if action_type == 'mark_status':
                    status_value = params.get('status', 'reported')
                    email.status = status_value
                    results['executed_actions'].append({
                        'type': action_type,
                        'status': 'success',
                        'message': f'Marked as {status_value}'
                    })

                elif action_type == 'auto_report':
                    # Mark for automatic reporting
                    email.status = 'reported'
                    results['executed_actions'].append({
                        'type': action_type,
                        'status': 'success',
                        'message': 'Marked for automatic reporting'
                    })

                elif action_type == 'flag':
                    # Flag for review
                    if not hasattr(email, 'flagged'):
                        email.flagged = True
                    results['executed_actions'].append({
                        'type': action_type,
                        'status': 'success',
                        'message': 'Flagged for review'
                    })

                elif action_type == 'delete':
                    # Delete email
                    db.delete(email)
                    results['executed_actions'].append({
                        'type': action_type,
                        'status': 'success',
                        'message': 'Email deleted'
                    })

                elif action_type == 'add_label':
                    # Add label/tag
                    label = params.get('label', 'spam')
                    if not hasattr(email, 'labels'):
                        email.labels = []
                    if label not in email.labels:
                        email.labels.append(label)
                    results['executed_actions'].append({
                        'type': action_type,
                        'status': 'success',
                        'message': f'Added label: {label}'
                    })

                elif action_type == 'block_sender':
                    # Block sender in user preferences
                    profile = db.query(UserProfile).filter(
                        UserProfile.id == current_user.id
                    ).first()
                    if profile:
                        if not profile.blocked_senders:
                            profile.blocked_senders = []
                        if email.from_addr not in profile.blocked_senders:
                            profile.blocked_senders.append(email.from_addr)
                    results['executed_actions'].append({
                        'type': action_type,
                        'status': 'success',
                        'message': f'Blocked sender: {email.from_addr}'
                    })

                elif action_type == 'trust_domain':
                    # Trust domain in user preferences
                    profile = db.query(UserProfile).filter(
                        UserProfile.id == current_user.id
                    ).first()
                    if profile:
                        if not profile.trusted_domains:
                            profile.trusted_domains = []
                        domain = email.from_addr.split('@')[1] if '@' in email.from_addr else ''
                        if domain and domain not in profile.trusted_domains:
                            profile.trusted_domains.append(domain)
                    results['executed_actions'].append({
                        'type': action_type,
                        'status': 'success',
                        'message': f'Trusted domain: {domain}'
                    })

                else:
                    results['errors'].append({
                        'action': action_type,
                        'error': 'Unknown action type'
                    })

            except Exception as e:
                results['errors'].append({
                    'action': action_type,
                    'error': str(e)
                })

        # Increment matched count
        rule.matched_count = (rule.matched_count or 0) + 1

        return results


# ===== API Routes =====

@router.get("/", response_model=List[EmailRuleResponse])
async def list_rules(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
    enabled_only: bool = Query(False, description="Show only enabled rules"),
):
    """
    List all email rules for current user.

    Query parameters:
    - enabled_only: Show only enabled rules
    """
    query = db.query(EmailRule).filter(EmailRule.user_id == current_user.id)

    if enabled_only:
        query = query.filter(EmailRule.enabled == True)

    rules = query.order_by(desc(EmailRule.priority), EmailRule.created_at.desc()).all()
    return rules


@router.post("/", response_model=EmailRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_rule(
    current_user = Depends(get_current_user),
    rule_data: EmailRuleCreate = None,
    db: Session = Depends(get_db),
):
    """
    Create a new email rule.

    Rules are evaluated in order of priority (highest first).
    All conditions must match for the rule to trigger (AND logic).
    """
    # Validate conditions
    if not rule_data.conditions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one condition is required"
        )

    # Validate actions
    if not rule_data.actions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one action is required"
        )

    # Check rule name uniqueness
    existing = db.query(EmailRule).filter(
        EmailRule.user_id == current_user.id,
        EmailRule.name == rule_data.name
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rule name already exists"
        )

    # Create rule
    rule = EmailRule(
        user_id=current_user.id,
        name=rule_data.name,
        description=rule_data.description,
        conditions=[c.dict() for c in rule_data.conditions],
        actions=[a.dict() for a in rule_data.actions],
        enabled=rule_data.enabled,
        priority=rule_data.priority,
    )

    db.add(rule)
    db.commit()
    db.refresh(rule)

    return EmailRuleResponse.from_orm(rule)


@router.get("/{rule_id}", response_model=EmailRuleResponse)
async def get_rule(
    rule_id: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a specific email rule"""
    rule = db.query(EmailRule).filter(
        EmailRule.id == rule_id,
        EmailRule.user_id == current_user.id
    ).first()

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule not found"
        )

    return rule


@router.put("/{rule_id}", response_model=EmailRuleResponse)
async def update_rule(
    rule_id: int,
    current_user = Depends(get_current_user),
    rule_data: EmailRuleUpdate = None,
    db: Session = Depends(get_db),
):
    """Update an email rule"""
    rule = db.query(EmailRule).filter(
        EmailRule.id == rule_id,
        EmailRule.user_id == current_user.id
    ).first()

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule not found"
        )

    # Update fields
    if rule_data.name:
        # Check uniqueness (excluding current rule)
        existing = db.query(EmailRule).filter(
            EmailRule.user_id == current_user.id,
            EmailRule.name == rule_data.name,
            EmailRule.id != rule_id
        ).first()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Rule name already exists"
            )

        rule.name = rule_data.name

    if rule_data.description is not None:
        rule.description = rule_data.description

    if rule_data.conditions:
        rule.conditions = [c.dict() for c in rule_data.conditions]

    if rule_data.actions:
        rule.actions = [a.dict() for a in rule_data.actions]

    if rule_data.enabled is not None:
        rule.enabled = rule_data.enabled

    if rule_data.priority is not None:
        rule.priority = rule_data.priority

    rule.updated_at = datetime.utcnow()

    db.add(rule)
    db.commit()
    db.refresh(rule)

    return rule


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(
    rule_id: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete an email rule"""
    rule = db.query(EmailRule).filter(
        EmailRule.id == rule_id,
        EmailRule.user_id == current_user.id
    ).first()

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule not found"
        )

    db.delete(rule)
    db.commit()


@router.post("/{rule_id}/toggle")
async def toggle_rule(
    rule_id: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Enable/disable a rule"""
    rule = db.query(EmailRule).filter(
        EmailRule.id == rule_id,
        EmailRule.user_id == current_user.id
    ).first()

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule not found"
        )

    rule.enabled = not rule.enabled
    db.add(rule)
    db.commit()

    return {
        "rule_id": rule_id,
        "enabled": rule.enabled
    }


@router.post("/{rule_id}/test")
async def test_rule(
    rule_id: int,
    email_id: str,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Test a rule against a specific email.
    Shows if the rule matches and what actions would be executed.
    """
    from app.models import Email

    rule = db.query(EmailRule).filter(
        EmailRule.id == rule_id,
        EmailRule.user_id == current_user.id
    ).first()

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule not found"
        )

    email = db.query(Email).filter(Email.id == email_id).first()

    if not email:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email not found"
        )

    # Test if rule matches
    matches = RuleEngine.evaluate_rule(email, rule)

    result = {
        "rule_id": rule_id,
        "email_id": email_id,
        "matches": matches,
        "conditions": [
            {
                "condition": cond,
                "matched": RuleEngine.evaluate_condition(email, cond)
            }
            for cond in (rule.conditions or [])
        ],
        "actions": rule.actions if matches else []
    }

    return result


@router.get("/stats/summary")
async def get_rules_stats(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get summary statistics for user's rules"""
    rules = db.query(EmailRule).filter(
        EmailRule.user_id == current_user.id
    ).all()

    total_matched = sum(r.matched_count or 0 for r in rules)

    return {
        "total_rules": len(rules),
        "enabled_rules": sum(1 for r in rules if r.enabled),
        "total_matches": total_matched,
        "rules": [
            {
                "id": r.id,
                "name": r.name,
                "enabled": r.enabled,
                "matched_count": r.matched_count or 0
            }
            for r in rules
        ]
    }
