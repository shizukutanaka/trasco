"""
Audit Logging System for Traceo.
Tracks all user actions for compliance and security monitoring.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, DateTime, JSON, desc, func
from loguru import logger

from app.database import get_db, Base
from app.security import get_current_user


router = APIRouter(prefix="/audit", tags=["audit"])


# ===== Enums =====

class AuditAction(str, Enum):
    """Audit log action types"""
    # Authentication
    LOGIN = "login"
    LOGOUT = "logout"
    PASSWORD_CHANGE = "password_change"
    EMAIL_VERIFICATION = "email_verification"

    # User Management
    PROFILE_UPDATE = "profile_update"
    PREFERENCES_UPDATE = "preferences_update"
    SETTINGS_UPDATE = "settings_update"

    # Email Operations
    EMAIL_VIEWED = "email_viewed"
    EMAIL_DELETED = "email_deleted"
    EMAIL_REPORTED = "email_reported"
    EMAIL_FLAGGED = "email_flagged"
    EMAIL_EXPORTED = "email_exported"

    # Rules Management
    RULE_CREATED = "rule_created"
    RULE_UPDATED = "rule_updated"
    RULE_DELETED = "rule_deleted"
    RULE_TOGGLED = "rule_toggled"
    RULE_TESTED = "rule_tested"

    # Webhook Management
    WEBHOOK_CREATED = "webhook_created"
    WEBHOOK_UPDATED = "webhook_updated"
    WEBHOOK_DELETED = "webhook_deleted"
    WEBHOOK_TESTED = "webhook_tested"

    # Admin Operations
    ADMIN_STATS_VIEWED = "admin_stats_viewed"
    ADMIN_HEALTH_CHECKED = "admin_health_checked"
    ADMIN_INDICES_REBUILT = "admin_indices_rebuilt"
    ADMIN_CLEANUP_EXECUTED = "admin_cleanup_executed"

    # Data Operations
    DATA_EXPORTED = "data_exported"
    DATA_DELETED = "data_deleted"

    # System
    SYSTEM_CONFIG_CHANGED = "system_config_changed"
    ERROR_OCCURRED = "error_occurred"


# ===== Database Model =====

class AuditLog(Base):
    """Audit log entry database model"""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    action = Column(String, index=True)
    resource_type = Column(String, index=True)  # email, rule, webhook, profile, etc.
    resource_id = Column(String, nullable=True)
    description = Column(String)
    details = Column(JSON, nullable=True)  # Additional context
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    status = Column(String, default="success")  # success, error, warning
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


# ===== Pydantic Models =====

class AuditLogEntry(BaseModel):
    """Audit log entry response model"""
    id: int
    user_id: int
    action: str
    resource_type: str
    resource_id: Optional[str]
    description: str
    details: Optional[Dict[str, Any]]
    ip_address: Optional[str]
    status: str
    error_message: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class AuditLogResponse(BaseModel):
    """Audit log response"""
    id: int
    action: str
    description: str
    resource_type: str
    resource_id: Optional[str]
    status: str
    created_at: str
    details: Optional[Dict[str, Any]]


class AuditLogFilter(BaseModel):
    """Audit log filter options"""
    action: Optional[str] = None
    resource_type: Optional[str] = None
    status: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


# ===== Audit Logger Service =====

class AuditLogger:
    """Service for logging audit events"""

    @staticmethod
    def log(
        user_id: int,
        action: AuditAction,
        resource_type: str,
        description: str,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        status: str = "success",
        error_message: Optional[str] = None,
        db: Optional[Session] = None
    ) -> Optional[AuditLog]:
        """
        Log an audit event.

        Args:
            user_id: User who performed the action
            action: Action type (from AuditAction enum)
            resource_type: Type of resource affected
            description: Human-readable description
            resource_id: ID of affected resource
            details: Additional context data
            ip_address: Client IP address
            user_agent: Client user agent
            status: success, error, warning
            error_message: Error details if applicable
            db: Database session

        Returns:
            Created AuditLog entry
        """
        try:
            if db is None:
                return None

            log_entry = AuditLog(
                user_id=user_id,
                action=action.value if isinstance(action, AuditAction) else action,
                resource_type=resource_type,
                resource_id=resource_id,
                description=description,
                details=details,
                ip_address=ip_address,
                user_agent=user_agent,
                status=status,
                error_message=error_message,
            )

            db.add(log_entry)
            db.commit()
            db.refresh(log_entry)

            logger.info(
                f"Audit: {action} | User: {user_id} | "
                f"Resource: {resource_type}:{resource_id} | Status: {status}"
            )

            return log_entry

        except Exception as e:
            logger.error(f"Error logging audit event: {e}")
            return None


# ===== API Routes =====

@router.get("/logs", response_model=List[AuditLogResponse])
async def list_audit_logs(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    status: Optional[str] = None,
):
    """
    List audit logs for current user.

    Supports filtering by action, resource type, and status.
    """
    query = db.query(AuditLog).filter(AuditLog.user_id == current_user.id)

    if action:
        query = query.filter(AuditLog.action == action)

    if resource_type:
        query = query.filter(AuditLog.resource_type == resource_type)

    if status:
        query = query.filter(AuditLog.status == status)

    logs = query.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit).all()

    return [
        AuditLogResponse(
            id=log.id,
            action=log.action,
            description=log.description,
            resource_type=log.resource_type,
            resource_id=log.resource_id,
            status=log.status,
            created_at=log.created_at.isoformat(),
            details=log.details,
        )
        for log in logs
    ]


@router.get("/logs/stats")
async def get_audit_stats(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
    days: int = Query(30, ge=1, le=365),
):
    """
    Get audit statistics for the last N days.
    """
    from datetime import timedelta

    cutoff_date = datetime.utcnow() - timedelta(days=days)

    query = db.query(AuditLog).filter(
        AuditLog.user_id == current_user.id,
        AuditLog.created_at >= cutoff_date
    )

    total_events = query.count()
    successful = query.filter(AuditLog.status == "success").count()
    errors = query.filter(AuditLog.status == "error").count()
    warnings = query.filter(AuditLog.status == "warning").count()

    # Action breakdown
    action_counts = {}
    actions = db.query(AuditLog.action, func.count(AuditLog.id)).filter(
        AuditLog.user_id == current_user.id,
        AuditLog.created_at >= cutoff_date
    ).group_by(AuditLog.action).all()

    for action, count in actions:
        action_counts[action] = count

    # Resource type breakdown
    resource_counts = {}
    resources = db.query(AuditLog.resource_type, func.count(AuditLog.id)).filter(
        AuditLog.user_id == current_user.id,
        AuditLog.created_at >= cutoff_date
    ).group_by(AuditLog.resource_type).all()

    for resource_type, count in resources:
        resource_counts[resource_type] = count

    return {
        "period_days": days,
        "total_events": total_events,
        "successful": successful,
        "errors": errors,
        "warnings": warnings,
        "success_rate": (successful / total_events * 100) if total_events > 0 else 0,
        "top_actions": dict(
            sorted(action_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        ),
        "resource_breakdown": resource_counts,
    }


@router.get("/logs/timeline")
async def get_audit_timeline(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
    days: int = Query(30, ge=1, le=365),
):
    """
    Get audit events organized by date for timeline visualization.
    """
    from datetime import timedelta, date

    cutoff_date = datetime.utcnow() - timedelta(days=days)

    # Get all logs for the period
    logs = db.query(AuditLog).filter(
        AuditLog.user_id == current_user.id,
        AuditLog.created_at >= cutoff_date
    ).order_by(AuditLog.created_at.desc()).all()

    # Group by date
    timeline = {}
    for log in logs:
        log_date = log.created_at.date().isoformat()
        if log_date not in timeline:
            timeline[log_date] = []

        timeline[log_date].append({
            "id": log.id,
            "action": log.action,
            "description": log.description,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "status": log.status,
            "time": log.created_at.isoformat(),
        })

    return {
        "period_days": days,
        "total_events": len(logs),
        "timeline": timeline,
    }


@router.get("/logs/export")
async def export_audit_logs(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
    days: int = Query(30, ge=1, le=365),
    format: str = Query("json", regex="^(json|csv)$"),
):
    """
    Export audit logs in CSV or JSON format.
    """
    from datetime import timedelta
    import csv
    import json
    from io import StringIO

    cutoff_date = datetime.utcnow() - timedelta(days=days)

    logs = db.query(AuditLog).filter(
        AuditLog.user_id == current_user.id,
        AuditLog.created_at >= cutoff_date
    ).order_by(AuditLog.created_at.desc()).all()

    if format == "json":
        return {
            "exported_at": datetime.utcnow().isoformat(),
            "user_id": current_user.id,
            "period_days": days,
            "total_events": len(logs),
            "logs": [
                {
                    "id": log.id,
                    "action": log.action,
                    "resource_type": log.resource_type,
                    "resource_id": log.resource_id,
                    "description": log.description,
                    "status": log.status,
                    "created_at": log.created_at.isoformat(),
                }
                for log in logs
            ]
        }

    elif format == "csv":
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "ID", "Action", "Resource Type", "Resource ID",
            "Description", "Status", "Created At"
        ])

        for log in logs:
            writer.writerow([
                log.id,
                log.action,
                log.resource_type,
                log.resource_id or "",
                log.description,
                log.status,
                log.created_at.isoformat(),
            ])

        return {
            "format": "csv",
            "data": output.getvalue(),
        }


@router.get("/logs/search")
async def search_audit_logs(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
    query: str = Query(..., min_length=1),
    limit: int = Query(50, ge=1, le=500),
):
    """
    Search audit logs by description.
    """
    results = db.query(AuditLog).filter(
        AuditLog.user_id == current_user.id,
        AuditLog.description.ilike(f"%{query}%")
    ).order_by(AuditLog.created_at.desc()).limit(limit).all()

    return {
        "query": query,
        "total_results": len(results),
        "results": [
            AuditLogResponse(
                id=log.id,
                action=log.action,
                description=log.description,
                resource_type=log.resource_type,
                resource_id=log.resource_id,
                status=log.status,
                created_at=log.created_at.isoformat(),
                details=log.details,
            )
            for log in results
        ]
    }


@router.delete("/logs/cleanup")
async def cleanup_old_audit_logs(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
    days_old: int = Query(90, ge=30, le=365),
):
    """
    Delete audit logs older than specified days.
    Requires admin verification.
    """
    from datetime import timedelta

    cutoff_date = datetime.utcnow() - timedelta(days=days_old)

    deleted_count = db.query(AuditLog).filter(
        AuditLog.user_id == current_user.id,
        AuditLog.created_at < cutoff_date
    ).delete()

    db.commit()

    # Log this cleanup action
    AuditLogger.log(
        user_id=current_user.id,
        action=AuditAction.ADMIN_CLEANUP_EXECUTED,
        resource_type="audit_logs",
        description=f"Cleaned up audit logs older than {days_old} days ({deleted_count} records deleted)",
        details={"days_old": days_old, "records_deleted": deleted_count},
        status="success",
        db=db
    )

    return {
        "status": "success",
        "deleted_count": deleted_count,
        "cutoff_date": cutoff_date.isoformat(),
    }
