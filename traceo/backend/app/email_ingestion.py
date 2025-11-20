import asyncio
import hashlib
import re
from typing import List, Dict, Optional
from email.parser import BytesParser
from datetime import datetime
from loguru import logger

from imap_tools import MailBox, AND
from app.settings import settings
from app.models import Email as EmailModel, EmailStatus
from app.database import SessionLocal


class EmailIngester:
    """Handle email retrieval from IMAP"""

    def __init__(self):
        self.mailbox: Optional[MailBox] = None
        self.db = SessionLocal()

    def connect(self, server: str, user: str, password: str, use_ssl: bool = True):
        """Connect to IMAP server"""
        try:
            self.mailbox = MailBox(server, use_ssl=use_ssl)
            self.mailbox.login(user, password)
            logger.info(f"Connected to IMAP server: {server}")
            return True
        except Exception as e:
            logger.error(f"IMAP connection failed: {e}")
            return False

    def disconnect(self):
        """Disconnect from IMAP server"""
        if self.mailbox:
            try:
                self.mailbox.logout()
                logger.info("Disconnected from IMAP server")
            except Exception as e:
                logger.error(f"IMAP disconnect failed: {e}")

    def fetch_emails(self, folder: str = "INBOX", limit: int = 50) -> List[Dict]:
        """Fetch emails from IMAP folder"""
        if not self.mailbox:
            logger.error("Not connected to IMAP server")
            return []

        try:
            emails = []
            for msg in self.mailbox.fetch(
                AND(seen=False), limit=limit, mark_seen=False
            ):
                email_data = self._parse_email(msg.obj)
                if email_data:
                    emails.append(email_data)
            logger.info(f"Fetched {len(emails)} emails from {folder}")
            return emails
        except Exception as e:
            logger.error(f"Email fetch failed: {e}")
            return []

    def _parse_email(self, msg_bytes) -> Optional[Dict]:
        """Parse email message"""
        try:
            parser = BytesParser()
            msg = parser.parsebytes(msg_bytes)

            # Extract basic info
            from_addr = msg.get("From", "unknown")
            to_addrs = msg.get_all("To", [])
            subject = msg.get("Subject", "(No Subject)")
            date_str = msg.get("Date", "")

            # Parse date
            received_date = self._parse_date(date_str)

            # Extract headers
            raw_headers = "\n".join(
                [f"{k}: {v}" for k, v in msg.items()]
            )

            # Extract body and URLs
            body = ""
            urls = []
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        try:
                            body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                        except:
                            body = part.get_payload()
            else:
                body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")

            # Extract URLs
            urls = self._extract_urls(body)

            # Generate ID
            email_id = hashlib.md5(
                (from_addr + subject + date_str).encode()
            ).hexdigest()

            return {
                "id": email_id,
                "from_addr": from_addr,
                "to_addrs": to_addrs,
                "subject": subject,
                "received_date": received_date,
                "raw_headers": raw_headers,
                "body": body,
                "urls": urls,
            }

        except Exception as e:
            logger.error(f"Email parsing failed: {e}")
            return None

    def _parse_date(self, date_str: str) -> datetime:
        """Parse email date"""
        from email.utils import parsedate_to_datetime
        try:
            return parsedate_to_datetime(date_str)
        except:
            return datetime.utcnow()

    def _extract_urls(self, text: str) -> List[str]:
        """Extract URLs from text"""
        url_pattern = r"https?://[^\s\"'<>]+"
        return list(set(re.findall(url_pattern, text)))

    def save_email(self, email_data: Dict) -> bool:
        """Save email to database"""
        try:
            # Check if email already exists
            existing = self.db.query(EmailModel).filter(
                EmailModel.id == email_data["id"]
            ).first()
            if existing:
                logger.debug(f"Email {email_data['id']} already exists")
                return False

            # Create new email record
            email = EmailModel(
                id=email_data["id"],
                from_addr=email_data["from_addr"],
                to_addrs=email_data["to_addrs"],
                subject=email_data["subject"],
                received_date=email_data["received_date"],
                raw_headers=email_data["raw_headers"],
                body=email_data["body"],
                urls=email_data["urls"],
                status=EmailStatus.PENDING,
            )
            self.db.add(email)
            self.db.commit()
            logger.info(f"Saved email {email_data['id']}")
            return True

        except Exception as e:
            logger.error(f"Email save failed: {e}")
            self.db.rollback()
            return False

    def process_emails(self) -> int:
        """Fetch and save emails from IMAP"""
        if not settings.imap_server:
            logger.warning("IMAP server not configured")
            return 0

        # Connect to IMAP
        if not self.connect(
            settings.imap_server,
            settings.imap_user,
            settings.imap_password,
            settings.imap_use_ssl,
        ):
            return 0

        try:
            # Fetch emails
            emails = self.fetch_emails()
            saved_count = 0

            for email_data in emails:
                if self.save_email(email_data):
                    saved_count += 1

            logger.info(f"Processed {saved_count} new emails")
            return saved_count

        finally:
            self.disconnect()


# Global ingester instance
ingester = EmailIngester()
