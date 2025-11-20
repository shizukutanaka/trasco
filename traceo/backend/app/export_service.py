"""
Email export service for Traceo.
Exports emails and reports in various formats: CSV, JSON, PDF.
"""

import csv
import json
from io import BytesIO, StringIO
from typing import List, Optional
from datetime import datetime
from enum import Enum

from app.models import Email, Report


class ExportFormat(str, Enum):
    """Supported export formats"""
    CSV = "csv"
    JSON = "json"
    PDF = "pdf"


class EmailExporter:
    """Export emails in various formats"""

    @staticmethod
    def to_csv(emails: List[Email]) -> str:
        """
        Export emails to CSV format.

        Returns CSV string content.
        """
        output = StringIO()
        fieldnames = [
            'id', 'from_addr', 'to_addrs', 'subject', 'received_date',
            'score', 'status', 'urls', 'indicators'
        ]

        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for email in emails:
            writer.writerow({
                'id': email.id,
                'from_addr': email.from_addr,
                'to_addrs': ', '.join(email.to_addrs) if email.to_addrs else '',
                'subject': email.subject,
                'received_date': email.received_date.isoformat() if email.received_date else '',
                'score': email.score,
                'status': email.status.value if email.status else '',
                'urls': '; '.join(email.urls) if email.urls else '',
                'indicators': '; '.join(
                    email.analysis.get('indicators', [])
                ) if email.analysis else '',
            })

        return output.getvalue()

    @staticmethod
    def to_csv_detailed(emails: List[Email]) -> str:
        """
        Export emails with full details to CSV format.
        """
        output = StringIO()
        fieldnames = [
            'id', 'from_addr', 'to_addrs', 'subject', 'received_date',
            'score', 'status', 'raw_headers', 'body', 'urls', 'indicators',
            'domain', 'registrar', 'ip', 'provider'
        ]

        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for email in emails:
            analysis = email.analysis or {}
            domain_info = email.domain_info or {}
            ip_info = email.ip_info or {}

            writer.writerow({
                'id': email.id,
                'from_addr': email.from_addr,
                'to_addrs': ', '.join(email.to_addrs) if email.to_addrs else '',
                'subject': email.subject,
                'received_date': email.received_date.isoformat() if email.received_date else '',
                'score': email.score,
                'status': email.status.value if email.status else '',
                'raw_headers': email.raw_headers[:500] if email.raw_headers else '',
                'body': email.body[:500] if email.body else '',
                'urls': '; '.join(email.urls) if email.urls else '',
                'indicators': '; '.join(analysis.get('indicators', [])),
                'domain': domain_info.get('domain', ''),
                'registrar': domain_info.get('registrar', ''),
                'ip': ip_info.get('ip', ''),
                'provider': ip_info.get('provider', ''),
            })

        return output.getvalue()

    @staticmethod
    def to_json(emails: List[Email], detailed: bool = False) -> str:
        """
        Export emails to JSON format.

        Args:
            emails: List of emails to export
            detailed: Include full email content if True

        Returns:
            JSON string
        """
        data = {
            "metadata": {
                "exported_at": datetime.utcnow().isoformat(),
                "count": len(emails),
            },
            "emails": []
        }

        for email in emails:
            email_data = {
                "id": email.id,
                "from": email.from_addr,
                "to": email.to_addrs,
                "subject": email.subject,
                "received_date": email.received_date.isoformat() if email.received_date else None,
                "score": email.score,
                "status": email.status.value if email.status else None,
                "urls": email.urls or [],
            }

            if detailed:
                email_data.update({
                    "body": email.body,
                    "headers": email.raw_headers,
                    "analysis": email.analysis or {},
                    "domain_info": email.domain_info or {},
                    "ip_info": email.ip_info or {},
                })

            data["emails"].append(email_data)

        return json.dumps(data, indent=2, default=str)

    @staticmethod
    def to_pdf(emails: List[Email], title: str = "Email Analysis Report") -> bytes:
        """
        Export emails to PDF format.

        Note: Requires reportlab library
        """
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib import colors
            from reportlab.lib.units import inch
        except ImportError:
            raise ImportError("reportlab is required for PDF export. Install with: pip install reportlab")

        # Create PDF
        pdf_buffer = BytesIO()
        doc = SimpleDocTemplate(pdf_buffer, pagesize=letter)
        elements = []

        # Styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#667eea'),
            spaceAfter=30,
        )

        # Title
        elements.append(Paragraph(title, title_style))
        elements.append(Paragraph(
            f"Exported: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC",
            styles['Normal']
        ))
        elements.append(Spacer(1, 0.5 * inch))

        # Summary table
        summary_data = [
            ['Total Emails', str(len(emails))],
            ['Critical (80+)', str(sum(1 for e in emails if e.score >= 80))],
            ['High (60-79)', str(sum(1 for e in emails if 60 <= e.score < 80))],
            ['Medium (40-59)', str(sum(1 for e in emails if 40 <= e.score < 60))],
            ['Low (<40)', str(sum(1 for e in emails if e.score < 40))],
        ]

        summary_table = Table(summary_data, colWidths=[2 * inch, 2 * inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f5f5f5')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ]))

        elements.append(summary_table)
        elements.append(Spacer(1, 0.3 * inch))

        # Email details
        elements.append(Paragraph("Email Details", styles['Heading2']))

        for email in emails[:10]:  # Limit to first 10 emails
            elements.append(Spacer(1, 0.2 * inch))

            # Email summary
            email_text = f"""
            <b>From:</b> {email.from_addr}<br/>
            <b>Subject:</b> {email.subject}<br/>
            <b>Date:</b> {email.received_date.strftime('%Y-%m-%d %H:%M:%S') if email.received_date else 'N/A'}<br/>
            <b>Risk Score:</b> {email.score}/100<br/>
            <b>Status:</b> {email.status.value if email.status else 'N/A'}<br/>
            """

            elements.append(Paragraph(email_text, styles['Normal']))

        # Build PDF
        doc.build(elements)

        return pdf_buffer.getvalue()


class ReportExporter:
    """Export reports in various formats"""

    @staticmethod
    def to_csv(reports: List[Report]) -> str:
        """Export reports to CSV format"""
        output = StringIO()
        fieldnames = [
            'email_id', 'recipient', 'status', 'created_at', 'sent_at'
        ]

        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for report in reports:
            writer.writerow({
                'email_id': report.email_id,
                'recipient': report.recipient_email,
                'status': report.status.value if report.status else '',
                'created_at': report.created_at.isoformat() if report.created_at else '',
                'sent_at': report.sent_at.isoformat() if report.sent_at else '',
            })

        return output.getvalue()

    @staticmethod
    def to_json(reports: List[Report]) -> str:
        """Export reports to JSON format"""
        data = {
            "metadata": {
                "exported_at": datetime.utcnow().isoformat(),
                "count": len(reports),
                "success_count": sum(1 for r in reports if r.status.value == 'sent'),
                "failed_count": sum(1 for r in reports if r.status.value == 'failed'),
            },
            "reports": []
        }

        for report in reports:
            data["reports"].append({
                "email_id": report.email_id,
                "recipient": report.recipient_email,
                "status": report.status.value if report.status else None,
                "created_at": report.created_at.isoformat() if report.created_at else None,
                "sent_at": report.sent_at.isoformat() if report.sent_at else None,
            })

        return json.dumps(data, indent=2, default=str)


class StatisticsExporter:
    """Export statistics and analytics"""

    @staticmethod
    def generate_summary(emails: List[Email], reports: List[Report]) -> dict:
        """Generate summary statistics"""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "email_statistics": {
                "total": len(emails),
                "by_status": {
                    "pending": sum(1 for e in emails if e.status.value == 'pending'),
                    "analyzed": sum(1 for e in emails if e.status.value == 'analyzed'),
                    "reported": sum(1 for e in emails if e.status.value == 'reported'),
                    "false_positive": sum(1 for e in emails if e.status.value == 'false_positive'),
                },
                "by_risk_level": {
                    "critical": sum(1 for e in emails if e.score >= 80),
                    "high": sum(1 for e in emails if 60 <= e.score < 80),
                    "medium": sum(1 for e in emails if 40 <= e.score < 60),
                    "low": sum(1 for e in emails if e.score < 40),
                },
                "average_score": round(sum(e.score for e in emails) / len(emails) if emails else 0, 2),
            },
            "report_statistics": {
                "total": len(reports),
                "sent": sum(1 for r in reports if r.status.value == 'sent'),
                "failed": sum(1 for r in reports if r.status.value == 'failed'),
                "pending": sum(1 for r in reports if r.status.value == 'pending'),
            }
        }
