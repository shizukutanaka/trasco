"""
Compliance Monitoring API endpoints for Traceo - Phase 7C.

Provides endpoints for:
- SOC 2 compliance status
- GDPR compliance verification
- ISO 27001 compliance checks
- Comprehensive compliance reports
- Compliance dashboard data
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import get_current_user, log_security_event
from app.compliance_service import ComplianceService, ComplianceFramework, ComplianceStatus


router = APIRouter(prefix="/admin/compliance", tags=["compliance"])


# ===== Pydantic Models =====

class ComplianceCheckResponse(BaseModel):
    """Single compliance check result"""
    status: str
    description: str
    details: Optional[str] = None
    recommendation: Optional[str] = None
    error: Optional[str] = None


class ComplianceFrameworkResponse(BaseModel):
    """Compliance framework check result"""
    framework: str
    status: str
    compliance_score: str
    checks: Dict[str, Any]
    timestamp: str
    last_updated: str


class ComplianceSummaryResponse(BaseModel):
    """Complete compliance summary"""
    timestamp: str
    overall_status: str
    overall_score: str
    frameworks: Dict[str, ComplianceFrameworkResponse]


class ComplianceReportResponse(BaseModel):
    """Detailed compliance report"""
    title: str
    timestamp: str
    executive_summary: Dict[str, Any]
    frameworks: Dict[str, Any]
    recommendations: list[str]
    next_audit_date: str


# ===== SOC 2 Routes =====

@router.get("/soc2", response_model=ComplianceFrameworkResponse)
async def get_soc2_compliance(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get SOC 2 Type II compliance status.

    Checks:
    - User access control and logging
    - System availability
    - Data protection (encryption)
    - Incident response procedures
    - Audit logging implementation
    """
    try:
        result = ComplianceService.check_soc2_compliance(db)

        log_security_event(
            "soc2_compliance_check",
            {
                "username": current_user.username,
                "status": result.get("status"),
                "score": result.get("compliance_score"),
            },
            severity="INFO",
        )

        return ComplianceFrameworkResponse(**result)

    except Exception as e:
        log_security_event(
            "soc2_compliance_check_error",
            {"username": current_user.username, "error": str(e)},
            severity="ERROR",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check SOC 2 compliance",
        )


# ===== GDPR Routes =====

@router.get("/gdpr", response_model=ComplianceFrameworkResponse)
async def get_gdpr_compliance(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get GDPR compliance status.

    Checks:
    - Data minimization (only necessary data collected)
    - Storage limitation (data retention policies)
    - User rights (access, modification, deletion)
    - Consent management
    - Breach notification procedures
    - Data Protection Impact Assessments (DPIA)
    - Third-party Data Processing Agreements (DPA)
    """
    try:
        result = ComplianceService.check_gdpr_compliance(db)

        log_security_event(
            "gdpr_compliance_check",
            {
                "username": current_user.username,
                "status": result.get("status"),
                "score": result.get("compliance_score"),
            },
            severity="INFO",
        )

        return ComplianceFrameworkResponse(**result)

    except Exception as e:
        log_security_event(
            "gdpr_compliance_check_error",
            {"username": current_user.username, "error": str(e)},
            severity="ERROR",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check GDPR compliance",
        )


# ===== ISO 27001 Routes =====

@router.get("/iso27001", response_model=ComplianceFrameworkResponse)
async def get_iso27001_compliance(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get ISO 27001 compliance status.

    Checks:
    - Information security policy
    - Access control implementation
    - Cryptographic measures
    - Physical security
    - Incident management
    - Business continuity planning
    - Third-party supplier management
    - Asset management and inventory
    """
    try:
        result = ComplianceService.check_iso27001_compliance(db)

        log_security_event(
            "iso27001_compliance_check",
            {
                "username": current_user.username,
                "status": result.get("status"),
                "score": result.get("compliance_score"),
            },
            severity="INFO",
        )

        return ComplianceFrameworkResponse(**result)

    except Exception as e:
        log_security_event(
            "iso27001_compliance_check_error",
            {"username": current_user.username, "error": str(e)},
            severity="ERROR",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check ISO 27001 compliance",
        )


# ===== Comprehensive Compliance Routes =====

@router.get("/summary", response_model=ComplianceSummaryResponse)
async def get_compliance_summary(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get comprehensive compliance summary across all frameworks.

    Returns overall compliance status and scores for:
    - SOC 2 Type II
    - GDPR
    - ISO 27001
    """
    try:
        result = ComplianceService.check_all_compliance(db)

        log_security_event(
            "compliance_summary_requested",
            {
                "username": current_user.username,
                "overall_status": result.get("overall_status"),
            },
            severity="INFO",
        )

        return ComplianceSummaryResponse(**result)

    except Exception as e:
        log_security_event(
            "compliance_summary_error",
            {"username": current_user.username, "error": str(e)},
            severity="ERROR",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate compliance summary",
        )


@router.get("/report", response_model=ComplianceReportResponse)
async def get_compliance_report(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generate detailed compliance report.

    Includes:
    - Executive summary
    - Detailed findings per framework
    - Compliance gaps and recommendations
    - Next audit date
    """
    try:
        compliance_result = ComplianceService.check_all_compliance(db)

        # Extract recommendations
        all_recommendations = []

        for framework_name, framework_data in compliance_result.get("frameworks", {}).items():
            for check_name, check_data in framework_data.get("checks", {}).items():
                if "recommendation" in check_data:
                    all_recommendations.append(
                        f"[{framework_name.upper()}] {check_name}: {check_data['recommendation']}"
                    )

        # Calculate next audit date (90 days from now)
        next_audit = (datetime.now(timezone.utc) + __import__("datetime").timedelta(days=90)).isoformat()

        report = ComplianceReportResponse(
            title="Traceo Platform Compliance Report",
            timestamp=compliance_result.get("timestamp"),
            executive_summary={
                "overall_status": compliance_result.get("overall_status"),
                "overall_score": compliance_result.get("overall_score"),
                "frameworks_checked": 3,
                "last_check_date": datetime.now(timezone.utc).isoformat(),
            },
            frameworks=compliance_result.get("frameworks", {}),
            recommendations=all_recommendations[:10],  # Top 10 recommendations
            next_audit_date=next_audit,
        )

        log_security_event(
            "compliance_report_generated",
            {
                "username": current_user.username,
                "overall_status": compliance_result.get("overall_status"),
            },
            severity="INFO",
        )

        return report

    except Exception as e:
        log_security_event(
            "compliance_report_error",
            {"username": current_user.username, "error": str(e)},
            severity="ERROR",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate compliance report",
        )


# ===== Compliance Dashboard Routes =====

@router.get("/dashboard")
async def get_compliance_dashboard(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get compliance dashboard data for visualization.

    Includes:
    - Status cards for each framework
    - Compliance trends
    - Key metrics
    - Pending actions
    """
    try:
        compliance_result = ComplianceService.check_all_compliance(db)

        # Extract framework scores
        framework_scores = {}
        framework_statuses = {}

        for name, data in compliance_result.get("frameworks", {}).items():
            score_str = data.get("compliance_score", "0%").rstrip("%")
            try:
                framework_scores[name] = float(score_str)
            except ValueError:
                framework_scores[name] = 0

            framework_statuses[name] = data.get("status", "unknown")

        dashboard = {
            "timestamp": compliance_result.get("timestamp"),
            "overall_status": compliance_result.get("overall_status"),
            "overall_score": compliance_result.get("overall_score"),
            "frameworks": {
                "soc2": {
                    "name": "SOC 2 Type II",
                    "score": framework_scores.get("soc2", 0),
                    "status": framework_statuses.get("soc2", "unknown"),
                    "description": "Security, Availability, Integrity controls",
                },
                "gdpr": {
                    "name": "GDPR",
                    "score": framework_scores.get("gdpr", 0),
                    "status": framework_statuses.get("gdpr", "unknown"),
                    "description": "Data Protection Regulation",
                },
                "iso27001": {
                    "name": "ISO 27001",
                    "score": framework_scores.get("iso27001", 0),
                    "status": framework_statuses.get("iso27001", "unknown"),
                    "description": "Information Security Management",
                },
            },
            "key_metrics": {
                "average_compliance": (
                    (framework_scores.get("soc2", 0) +
                     framework_scores.get("gdpr", 0) +
                     framework_scores.get("iso27001", 0)) / 3
                ),
                "frameworks_assessed": 3,
                "areas_of_concern": sum(
                    1 for status in framework_statuses.values()
                    if status in ["non_compliant", "warning"]
                ),
            },
            "recent_checks": [
                {
                    "framework": "soc2",
                    "timestamp": compliance_result.get("timestamp"),
                    "status": framework_statuses.get("soc2"),
                },
                {
                    "framework": "gdpr",
                    "timestamp": compliance_result.get("timestamp"),
                    "status": framework_statuses.get("gdpr"),
                },
                {
                    "framework": "iso27001",
                    "timestamp": compliance_result.get("timestamp"),
                    "status": framework_statuses.get("iso27001"),
                },
            ],
        }

        log_security_event(
            "compliance_dashboard_accessed",
            {
                "username": current_user.username,
                "overall_status": compliance_result.get("overall_status"),
            },
            severity="INFO",
        )

        return dashboard

    except Exception as e:
        log_security_event(
            "compliance_dashboard_error",
            {"username": current_user.username, "error": str(e)},
            severity="ERROR",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve compliance dashboard",
        )


# ===== Compliance Health Check =====

@router.get("/health")
async def compliance_health_check(
    current_user = Depends(get_current_user),
):
    """
    Check compliance system health and status.

    Returns overall compliance status without running full checks.
    """
    try:
        return {
            "status": "healthy",
            "compliance_system": "operational",
            "frameworks_supported": ["SOC2_TYPE_II", "GDPR", "ISO27001"],
            "last_check": datetime.now(timezone.utc).isoformat(),
            "endpoints_available": [
                "/admin/compliance/soc2",
                "/admin/compliance/gdpr",
                "/admin/compliance/iso27001",
                "/admin/compliance/summary",
                "/admin/compliance/report",
                "/admin/compliance/dashboard",
            ],
        }

    except Exception as e:
        log_security_event(
            "compliance_health_check_failed",
            {"error": str(e)},
            severity="ERROR",
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Compliance system health check failed",
        )
