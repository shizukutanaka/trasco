import aiosmtplib
import hashlib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Optional
from datetime import datetime
from loguru import logger

from app.settings import settings
from app.models import Report as ReportModel, ReportStatus
from app.database import SessionLocal
from app.domain_info import domain_lookup


class EmailReporter:
    """Send abuse reports to authorities"""

    # Known reporting recipients
    RECIPIENTS = {
        "registrar": "abuse@{registrar}",
        "cloudflare": "abuse@cloudflare.com",
        "jpcert": "report@jpcert.or.jp",
        "icann": "complaints-admins@icann.org",
    }

    def __init__(self):
        self.db = SessionLocal()

    async def send_report(
        self,
        email_id: str,
        email_data: Dict,
        analysis_result: Dict,
        language: str = "en",
        recipients: Optional[List[str]] = None,
    ) -> Dict:
        """Send phishing report to authorities"""

        if not recipients:
            recipients = await self._determine_recipients(email_data)

        results = {}
        for recipient_email in recipients:
            try:
                # Generate report content
                report_content = self._generate_report(
                    email_data, analysis_result, recipient_email, language
                )

                # Send email
                success = await self._send_email(
                    report_content, recipient_email
                )

                # Log report
                self._log_report(
                    email_id,
                    recipient_email,
                    report_content,
                    ReportStatus.SENT if success else ReportStatus.FAILED,
                    language,
                )

                results[recipient_email] = {
                    "status": "sent" if success else "failed",
                    "timestamp": datetime.utcnow().isoformat(),
                }

                logger.info(
                    f"Report sent to {recipient_email} for email {email_id}"
                )

            except Exception as e:
                logger.error(
                    f"Failed to send report to {recipient_email}: {e}"
                )
                results[recipient_email] = {
                    "status": "error",
                    "error": str(e),
                }

        return {
            "email_id": email_id,
            "results": results,
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def _determine_recipients(
        self, email_data: Dict
    ) -> List[str]:
        """Determine which authorities to report to"""
        recipients = []

        # Always report to JPCERT (Japan-focused for now)
        recipients.append(self.RECIPIENTS["jpcert"])

        # Check for Cloudflare nameservers
        domain_info = email_data.get("domain_info", {})
        nameservers = domain_info.get("name_servers", [])
        if any("cloudflare" in str(ns).lower() for ns in nameservers):
            recipients.append(self.RECIPIENTS["cloudflare"])

        return recipients

    def _generate_report(
        self,
        email_data: Dict,
        analysis_result: Dict,
        recipient_email: str,
        language: str,
    ) -> str:
        """Generate report content"""

        template_key = self._select_template(recipient_email)
        template_content = self._load_template(template_key, language)

        # Fill placeholders
        domain_info = email_data.get("domain_info", {})
        urls = email_data.get("urls", [])

        report = template_content.format(
            from_addr=email_data.get("from_addr", "Unknown"),
            subject=email_data.get("subject", "Unknown"),
            score=analysis_result.get("score", 0),
            domain=domain_info.get("domain", "Unknown"),
            url=urls[0] if urls else "N/A",
            urls_list="\n".join(urls) if urls else "N/A",
            registrar=domain_info.get("registrar", "Unknown"),
            received_date=email_data.get("received_date", "Unknown"),
        )

        return report

    def _select_template(self, recipient_email: str) -> str:
        """Select appropriate template based on recipient"""
        if "jpcert" in recipient_email.lower():
            return "jpcert"
        elif "cloudflare" in recipient_email.lower():
            return "cloudflare"
        else:
            return "registrar"

    def _load_template(self, template_type: str, language: str) -> str:
        """Load report template"""
        template_map = {
            "jpcert": f"abuse/jpcert_{language}.md",
            "cloudflare": f"abuse/cloudflare_{language}.md",
            "registrar": f"abuse/{language}.md",
        }

        template_path = (
            f"app/templates/{template_map.get(template_type, f'abuse/{language}.md')}"
        )

        try:
            with open(template_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            # Fallback to default template
            with open(f"app/templates/abuse/{language}.md", "r", encoding="utf-8") as f:
                return f.read()

    async def _send_email(self, content: str, recipient_email: str) -> bool:
        """Send email via SMTP"""

        if not all(
            [
                settings.smtp_server,
                settings.smtp_user,
                settings.smtp_password,
            ]
        ):
            logger.warning("SMTP not configured, skipping report send")
            return False

        try:
            # Create message
            msg = MIMEMultipart()
            msg["From"] = settings.smtp_user
            msg["To"] = recipient_email
            msg["Subject"] = "[Traceo] Phishing Report"

            msg.attach(MIMEText(content, "plain", "utf-8"))

            # Send email
            async with aiosmtplib.SMTP(
                hostname=settings.smtp_server,
                port=settings.smtp_port,
            ) as smtp:
                if settings.smtp_use_tls:
                    await smtp.starttls()

                await smtp.login(
                    settings.smtp_user, settings.smtp_password
                )
                await smtp.send_message(msg)

            logger.info(f"Report sent to {recipient_email}")
            return True

        except Exception as e:
            logger.error(f"SMTP send failed: {e}")
            return False

    def _log_report(
        self,
        email_id: str,
        recipient_email: str,
        content: str,
        status: ReportStatus,
        language: str,
    ):
        """Log report in database"""
        try:
            report = ReportModel(
                id=hashlib.md5(
                    (email_id + recipient_email).encode()
                ).hexdigest(),
                email_id=email_id,
                recipient_email=recipient_email,
                recipient_type=self._get_recipient_type(recipient_email),
                language=language,
                content=content,
                status=status,
                sent_at=datetime.utcnow() if status == ReportStatus.SENT else None,
            )
            self.db.add(report)
            self.db.commit()
            logger.debug(f"Report logged for {email_id}")
        except Exception as e:
            logger.error(f"Failed to log report: {e}")
            self.db.rollback()

    def _get_recipient_type(self, recipient_email: str) -> str:
        """Determine recipient type"""
        if "jpcert" in recipient_email.lower():
            return "jpcert"
        elif "cloudflare" in recipient_email.lower():
            return "cloudflare"
        else:
            return "registrar"


# Global instance
reporter = EmailReporter()
