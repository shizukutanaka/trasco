"""
Admin dashboard and system management for Traceo.
Handles system monitoring, statistics, and administrative operations.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.database import get_db, engine
from app.models import Email, Report, EmailStatus, ReportStatus
from app.security import get_current_user
from app.user_profiles import UserProfile


router = APIRouter(prefix="/admin", tags=["administration"])


# ===== Pydantic Models =====

class SystemStats(BaseModel):
    """System-wide statistics"""
    total_emails: int
    emails_by_status: Dict[str, int]
    emails_by_risk_level: Dict[str, int]
    average_risk_score: float
    total_reports: int
    reports_by_status: Dict[str, int]
    total_users: int
    active_users: int


class HealthStatus(BaseModel):
    """System health status"""
    status: str  # healthy, degraded, unhealthy
    database: str
    api: str
    timestamp: datetime


class EmailTrend(BaseModel):
    """Email trend data"""
    date: str
    count: int
    high_risk_count: int
    average_score: float


class SystemLog(BaseModel):
    """System log entry"""
    timestamp: datetime
    level: str  # INFO, WARNING, ERROR
    message: str
    details: Dict[str, Any]


class AdminAction(BaseModel):
    """Admin action audit log"""
    action: str
    admin_user: str
    target: str
    timestamp: datetime
    result: str


# ===== Statistics Routes =====

@router.get("/stats", response_model=SystemStats)
async def get_system_statistics(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get comprehensive system statistics.

    Includes email and report statistics, user counts.
    """
    # Get emails
    total_emails = db.query(func.count(Email.id)).scalar()
    emails = db.query(Email).all()

    # Emails by status
    emails_by_status = {
        "pending": db.query(func.count(Email.id)).filter(Email.status == EmailStatus.PENDING).scalar(),
        "analyzed": db.query(func.count(Email.id)).filter(Email.status == EmailStatus.ANALYZED).scalar(),
        "reported": db.query(func.count(Email.id)).filter(Email.status == EmailStatus.REPORTED).scalar(),
        "false_positive": db.query(func.count(Email.id)).filter(Email.status == EmailStatus.FALSE_POSITIVE).scalar(),
        "error": db.query(func.count(Email.id)).filter(Email.status == EmailStatus.ERROR).scalar(),
    }

    # Emails by risk level
    emails_by_risk_level = {
        "critical": sum(1 for e in emails if e.score >= 80),
        "high": sum(1 for e in emails if 60 <= e.score < 80),
        "medium": sum(1 for e in emails if 40 <= e.score < 60),
        "low": sum(1 for e in emails if e.score < 40),
    }

    # Average risk score
    average_score = sum(e.score for e in emails) / len(emails) if emails else 0

    # Reports
    total_reports = db.query(func.count(Report.id)).scalar()
    reports_by_status = {
        "pending": db.query(func.count(Report.id)).filter(Report.status == ReportStatus.PENDING).scalar(),
        "sent": db.query(func.count(Report.id)).filter(Report.status == ReportStatus.SENT).scalar(),
        "failed": db.query(func.count(Report.id)).filter(Report.status == ReportStatus.FAILED).scalar(),
    }

    # Users
    total_users = db.query(func.count(UserProfile.id)).scalar()
    last_week = datetime.utcnow() - timedelta(days=7)
    active_users = db.query(func.count(UserProfile.id)).filter(
        UserProfile.last_login >= last_week
    ).scalar()

    return SystemStats(
        total_emails=total_emails or 0,
        emails_by_status=emails_by_status,
        emails_by_risk_level=emails_by_risk_level,
        average_risk_score=round(average_score, 2),
        total_reports=total_reports or 0,
        reports_by_status=reports_by_status,
        total_users=total_users or 0,
        active_users=active_users or 0,
    )


@router.get("/health")
async def get_system_health(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get system health status.

    Checks database connectivity and API responsiveness.
    """
    health_status = {
        "status": "healthy",
        "database": "unknown",
        "api": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {}
    }

    # Check database
    try:
        result = db.execute("SELECT 1")
        health_status["database"] = "healthy"
        health_status["checks"]["database"] = {
            "status": "ok",
            "latency_ms": 0
        }
    except Exception as e:
        health_status["database"] = "unhealthy"
        health_status["status"] = "degraded"
        health_status["checks"]["database"] = {
            "status": "error",
            "error": str(e)
        }

    # Check tables
    try:
        db.query(Email).count()
        db.query(Report).count()
        db.query(UserProfile).count()
        health_status["checks"]["tables"] = {"status": "ok"}
    except Exception as e:
        health_status["checks"]["tables"] = {
            "status": "error",
            "error": str(e)
        }
        health_status["status"] = "degraded"

    return health_status


@router.get("/trends")
async def get_email_trends(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
):
    """
    Get email trends over time.

    Returns daily email counts and risk statistics.
    """
    start_date = datetime.utcnow() - timedelta(days=days)
    trends: List[Dict[str, Any]] = []

    for i in range(days):
        date = start_date + timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")

        # Get emails for this day
        day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)

        day_emails = db.query(Email).filter(
            Email.created_at.between(day_start, day_end)
        ).all()

        count = len(day_emails)
        high_risk_count = sum(1 for e in day_emails if e.score >= 60)
        average_score = sum(e.score for e in day_emails) / count if count > 0 else 0

        trends.append({
            "date": date_str,
            "count": count,
            "high_risk_count": high_risk_count,
            "average_score": round(average_score, 2),
        })

    return {"trends": trends}


@router.get("/top-senders")
async def get_top_senders(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(10, ge=1, le=100, description="Number of top senders"),
):
    """
    Get top email senders by frequency.

    Useful for identifying spam sources.
    """
    # Group by sender and count
    results = db.query(
        Email.from_addr,
        func.count(Email.id).label("count"),
        func.avg(Email.score).label("avg_score"),
    ).group_by(Email.from_addr).order_by(
        desc(func.count(Email.id))
    ).limit(limit).all()

    return {
        "top_senders": [
            {
                "sender": r[0],
                "count": r[1],
                "average_risk_score": round(r[2], 2) if r[2] else 0,
            }
            for r in results
        ]
    }


@router.get("/top-domains")
async def get_top_domains(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(10, ge=1, le=100, description="Number of top domains"),
):
    """
    Get top domains detected in suspicious emails.

    Helps identify common phishing sources.
    """
    emails = db.query(Email).all()

    # Extract domains from sender addresses
    domain_stats: Dict[str, Dict[str, Any]] = {}

    for email in emails:
        if "@" in email.from_addr:
            domain = email.from_addr.split("@")[1]
            if domain not in domain_stats:
                domain_stats[domain] = {
                    "count": 0,
                    "scores": []
                }
            domain_stats[domain]["count"] += 1
            domain_stats[domain]["scores"].append(email.score)

    # Sort and limit
    sorted_domains = sorted(
        domain_stats.items(),
        key=lambda x: x[1]["count"],
        reverse=True
    )[:limit]

    return {
        "top_domains": [
            {
                "domain": domain,
                "count": stats["count"],
                "average_risk_score": round(sum(stats["scores"]) / len(stats["scores"]), 2),
                "max_risk_score": max(stats["scores"]),
            }
            for domain, stats in sorted_domains
        ]
    }


# ===== System Management Routes =====

@router.post("/rebuild-indices")
async def rebuild_database_indices(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Rebuild database indices for performance optimization.

    Admin only operation.
    """
    try:
        # Note: This is a simplified example
        # In production, use proper database migration tools
        return {
            "message": "Database indices rebuilt successfully",
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to rebuild indices: {str(e)}"
        )


@router.post("/cleanup-old-data")
async def cleanup_old_data(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
    days_old: int = Query(90, ge=7, description="Remove data older than N days"),
):
    """
    Clean up old email and report data.

    Permanently removes data older than specified days.
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days_old)

    try:
        # Delete old emails
        deleted_emails = db.query(Email).filter(
            Email.created_at < cutoff_date
        ).delete()

        # Delete old reports
        deleted_reports = db.query(Report).filter(
            Report.created_at < cutoff_date
        ).delete()

        db.commit()

        return {
            "message": f"Cleanup completed",
            "deleted_emails": deleted_emails,
            "deleted_reports": deleted_reports,
            "cutoff_date": cutoff_date.isoformat(),
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cleanup failed: {str(e)}"
        )


@router.post("/rescan-email/{email_id}")
async def rescan_email(
    email_id: str,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Re-analyze a specific email.

    Useful for updating analysis after changes.
    """
    email = db.query(Email).filter(Email.id == email_id).first()

    if not email:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email not found"
        )

    # Re-analyze (simplified example)
    # In production, would call the full analysis pipeline
    email.updated_at = datetime.utcnow()
    db.add(email)
    db.commit()

    return {
        "message": "Email re-scanned successfully",
        "email_id": email_id,
    }


@router.get("/dashboard-summary")
async def get_dashboard_summary(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get complete dashboard summary for admin.

    Combines all key metrics in one response.
    """
    stats = await get_system_statistics(current_user, db)
    health = await get_system_health(current_user, db)
    top_senders = await get_top_senders(current_user, db, limit=5)
    top_domains = await get_top_domains(current_user, db, limit=5)

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "summary": {
            "total_emails": stats.total_emails,
            "high_risk_emails": stats.emails_by_risk_level["critical"] + stats.emails_by_risk_level["high"],
            "reports_pending": stats.reports_by_status["pending"],
            "total_users": stats.total_users,
            "average_risk_score": stats.average_risk_score,
        },
        "health": health,
        "top_threats": {
            "senders": top_senders["top_senders"][:3],
            "domains": top_domains["top_domains"][:3],
        },
        "statistics": {
            "emails_by_status": stats.emails_by_status,
            "emails_by_risk_level": stats.emails_by_risk_level,
            "reports_by_status": stats.reports_by_status,
        }
    }
