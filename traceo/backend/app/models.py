from sqlalchemy import Column, String, Integer, DateTime, JSON, Boolean, Text, Enum as SQLEnum
from datetime import datetime
import enum
from app.database import Base


class EmailStatus(str, enum.Enum):
    """Email analysis status"""
    PENDING = "pending"
    ANALYZED = "analyzed"
    REPORTED = "reported"
    FALSE_POSITIVE = "false_positive"
    ERROR = "error"


class ReportStatus(str, enum.Enum):
    """Report submission status"""
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class Email(Base):
    """Email record"""
    __tablename__ = "emails"

    id = Column(String(64), primary_key=True, index=True)
    from_addr = Column(String(255), index=True)
    to_addrs = Column(JSON)
    subject = Column(String(512))
    received_date = Column(DateTime, index=True)

    # Analysis results
    score = Column(Integer, default=0)
    status = Column(SQLEnum(EmailStatus), default=EmailStatus.PENDING)

    # Content
    raw_headers = Column(Text)
    body = Column(Text)

    # Extracted data
    urls = Column(JSON, default=[])
    attachments = Column(JSON, default=[])

    # Domain analysis
    domain_info = Column(JSON)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    analyzed_at = Column(DateTime)
    reported_at = Column(DateTime)

    def __repr__(self):
        return f"<Email id={self.id} from={self.from_addr} score={self.score}>"


class Report(Base):
    """Abuse report record"""
    __tablename__ = "reports"

    id = Column(String(64), primary_key=True, index=True)
    email_id = Column(String(64), index=True)

    # Report details
    recipient_email = Column(String(255))
    recipient_type = Column(String(50))  # registrar, cloudflare, jpcert, custom
    language = Column(String(10), default="en")

    # Content
    content = Column(Text)

    # Status
    status = Column(SQLEnum(ReportStatus), default=ReportStatus.PENDING)
    error_message = Column(Text)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    sent_at = Column(DateTime)

    def __repr__(self):
        return f"<Report id={self.id} email_id={self.email_id} status={self.status}>"


class User(Base):
    """User account"""
    __tablename__ = "users"

    id = Column(String(64), primary_key=True, index=True)
    username = Column(String(255), unique=True, index=True)
    password_hash = Column(String(255))

    # Settings
    email = Column(String(255))
    language = Column(String(10), default="en")
    auto_report = Column(Boolean, default=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)

    def __repr__(self):
        return f"<User username={self.username}>"


class Configuration(Base):
    """System configuration"""
    __tablename__ = "configuration"

    key = Column(String(255), primary_key=True)
    value = Column(Text)
    description = Column(String(512))

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Configuration key={self.key}>"
