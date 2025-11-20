"""
Export API routes for Traceo.
Handles email and report exports in various formats.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, status, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Email, Report
from app.security import get_current_user, general_limiter
from app.export_service import (
    EmailExporter,
    ReportExporter,
    StatisticsExporter,
    ExportFormat,
)


router = APIRouter(prefix="/export", tags=["export"])


@router.get("/emails/csv")
async def export_emails_csv(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
    detailed: bool = Query(False, description="Include full email content"),
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    min_score: int = Query(0, ge=0, le=100, description="Minimum risk score"),
    max_score: int = Query(100, ge=0, le=100, description="Maximum risk score"),
):
    """
    Export emails to CSV format.

    Query parameters:
    - detailed: Include full email content
    - status_filter: Filter by status (pending, analyzed, reported, etc.)
    - min_score: Minimum risk score (0-100)
    - max_score: Maximum risk score (0-100)
    """
    # Build query
    query = db.query(Email)

    if status_filter:
        query = query.filter(Email.status == status_filter)

    query = query.filter(Email.score.between(min_score, max_score))

    emails = query.all()

    if not emails:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No emails match the filter criteria"
        )

    # Generate CSV
    if detailed:
        csv_content = EmailExporter.to_csv_detailed(emails)
        filename = f"emails_detailed_{len(emails)}.csv"
    else:
        csv_content = EmailExporter.to_csv(emails)
        filename = f"emails_{len(emails)}.csv"

    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/emails/json")
async def export_emails_json(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
    detailed: bool = Query(False, description="Include full email content"),
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    min_score: int = Query(0, ge=0, le=100, description="Minimum risk score"),
    max_score: int = Query(100, ge=0, le=100, description="Maximum risk score"),
):
    """
    Export emails to JSON format.

    Query parameters:
    - detailed: Include full email content
    - status_filter: Filter by status
    - min_score: Minimum risk score
    - max_score: Maximum risk score
    """
    # Build query
    query = db.query(Email)

    if status_filter:
        query = query.filter(Email.status == status_filter)

    query = query.filter(Email.score.between(min_score, max_score))

    emails = query.all()

    if not emails:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No emails match the filter criteria"
        )

    # Generate JSON
    json_content = EmailExporter.to_json(emails, detailed=detailed)

    return StreamingResponse(
        iter([json_content]),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=emails.json"}
    )


@router.get("/emails/pdf")
async def export_emails_pdf(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
    min_score: int = Query(0, ge=0, le=100, description="Minimum risk score"),
    max_score: int = Query(100, ge=0, le=100, description="Maximum risk score"),
    title: str = Query("Email Analysis Report", description="Report title"),
):
    """
    Export emails to PDF format.

    Query parameters:
    - min_score: Minimum risk score
    - max_score: Maximum risk score
    - title: Custom report title
    """
    # Build query
    query = db.query(Email).filter(Email.score.between(min_score, max_score))
    emails = query.all()

    if not emails:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No emails match the filter criteria"
        )

    try:
        # Generate PDF
        pdf_content = EmailExporter.to_pdf(emails, title=title)

        return StreamingResponse(
            iter([pdf_content]),
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=emails_report.pdf"}
        )
    except ImportError as e:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="PDF export is not available. Install reportlab with: pip install reportlab"
        )


@router.get("/reports/csv")
async def export_reports_csv(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
    status_filter: Optional[str] = Query(None, description="Filter by status"),
):
    """
    Export reports to CSV format.

    Query parameters:
    - status_filter: Filter by status (pending, sent, failed)
    """
    # Build query
    query = db.query(Report)

    if status_filter:
        query = query.filter(Report.status == status_filter)

    reports = query.all()

    if not reports:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No reports found"
        )

    # Generate CSV
    csv_content = ReportExporter.to_csv(reports)
    filename = f"reports_{len(reports)}.csv"

    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/reports/json")
async def export_reports_json(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
    status_filter: Optional[str] = Query(None, description="Filter by status"),
):
    """
    Export reports to JSON format.

    Query parameters:
    - status_filter: Filter by status (pending, sent, failed)
    """
    # Build query
    query = db.query(Report)

    if status_filter:
        query = query.filter(Report.status == status_filter)

    reports = query.all()

    if not reports:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No reports found"
        )

    # Generate JSON
    json_content = ReportExporter.to_json(reports)

    return StreamingResponse(
        iter([json_content]),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=reports.json"}
    )


@router.get("/statistics")
async def export_statistics(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
    format: ExportFormat = Query(ExportFormat.JSON, description="Export format"),
):
    """
    Export statistics and summary data.

    Query parameters:
    - format: Export format (json or csv)
    """
    # Get all emails and reports
    emails = db.query(Email).all()
    reports = db.query(Report).all()

    # Generate summary
    summary = StatisticsExporter.generate_summary(emails, reports)

    if format == ExportFormat.JSON:
        import json
        json_content = json.dumps(summary, indent=2)

        return StreamingResponse(
            iter([json_content]),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=statistics.json"}
        )

    elif format == ExportFormat.CSV:
        import csv
        from io import StringIO

        output = StringIO()
        writer = csv.writer(output)

        # Write statistics
        writer.writerow(['Metric', 'Value'])
        writer.writerow(['Total Emails', summary['email_statistics']['total']])
        writer.writerow(['Average Score', summary['email_statistics']['average_score']])
        writer.writerow(['Critical (80+)', summary['email_statistics']['by_risk_level']['critical']])
        writer.writerow(['High (60-79)', summary['email_statistics']['by_risk_level']['high']])
        writer.writerow(['Medium (40-59)', summary['email_statistics']['by_risk_level']['medium']])
        writer.writerow(['Low (<40)', summary['email_statistics']['by_risk_level']['low']])
        writer.writerow(['Total Reports', summary['report_statistics']['total']])
        writer.writerow(['Reports Sent', summary['report_statistics']['sent']])
        writer.writerow(['Reports Failed', summary['report_statistics']['failed']])

        csv_content = output.getvalue()

        return StreamingResponse(
            iter([csv_content]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=statistics.csv"}
        )


@router.get("/summary")
async def get_export_summary(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get summary of available exports.

    Shows count of emails and reports available for export.
    """
    emails = db.query(Email).all()
    reports = db.query(Report).all()

    return {
        "summary": {
            "timestamp": db.query(Email).first().created_at if emails else None,
            "emails_available": len(emails),
            "reports_available": len(reports),
            "emails_by_status": {
                "pending": sum(1 for e in emails if e.status.value == 'pending'),
                "analyzed": sum(1 for e in emails if e.status.value == 'analyzed'),
                "reported": sum(1 for e in emails if e.status.value == 'reported'),
            },
            "reports_by_status": {
                "pending": sum(1 for r in reports if r.status.value == 'pending'),
                "sent": sum(1 for r in reports if r.status.value == 'sent'),
                "failed": sum(1 for r in reports if r.status.value == 'failed'),
            },
        },
        "available_formats": ["csv", "json", "pdf"],
        "available_exports": [
            "/export/emails/csv",
            "/export/emails/json",
            "/export/emails/pdf",
            "/export/reports/csv",
            "/export/reports/json",
            "/export/statistics",
        ]
    }
