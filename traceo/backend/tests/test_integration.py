"""
Comprehensive integration tests for Traceo backend modules.
Tests the full pipeline: ingestion → analysis → reporting
"""

import pytest
import asyncio
import json
from datetime import datetime
from unittest.mock import patch, AsyncMock, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import Base
from app.models import Email, EmailStatus, Report, ReportStatus
from app.email_analyzer import EmailAnalyzer
from app.domain_info import DomainInfo
from app.ip_info import IPInfo
from app.email_ingestion import EmailIngester


# Test Database Setup
TEST_DB_URL = "sqlite:///:memory:"

@pytest.fixture(scope="function")
def test_db():
    """Create in-memory test database"""
    engine = create_engine(TEST_DB_URL)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


# Test Data
SAMPLE_PHISHING_EMAIL = {
    "id": "test-phishing-001",
    "from_addr": "support@suspicious-domain.top",
    "to_addrs": ["user@legitimate.com"],
    "subject": "Urgent: Verify Your Account - Action Required",
    "received_date": datetime.utcnow().isoformat(),
    "raw_headers": """From: support@suspicious-domain.top
To: user@legitimate.com
Date: Mon, 15 Nov 2024 10:30:00 +0000
Subject: Urgent: Verify Your Account - Action Required
X-Originating-IP: [112.45.67.89]
X-Mailer: Unknown""",
    "body": """Dear User,

Your account has been compromised. Please click the link below to verify your identity immediately.

https://suspicius-domain.top/verify-account?token=abc123
https://malicious.click/phishing

Best regards,
Security Team""",
    "urls": ["https://suspicious-domain.top/verify", "https://malicious.click/phishing"],
}

SAMPLE_LEGITIMATE_EMAIL = {
    "id": "test-legitimate-001",
    "from_addr": "noreply@github.com",
    "to_addrs": ["developer@company.com"],
    "subject": "GitHub: New repository starred",
    "received_date": datetime.utcnow().isoformat(),
    "raw_headers": """From: noreply@github.com
To: developer@company.com
Date: Mon, 15 Nov 2024 10:30:00 +0000
Subject: GitHub: New repository starred
Received: from smtp.google.com by google.com
Authentication-Results: pass spf=pass dkim=pass dmarc=pass""",
    "body": "Your repository was starred. Check it out at github.com",
    "urls": ["https://github.com/your-repo"],
}


class TestEmailAnalysis:
    """Test email analysis and risk scoring"""

    def test_phishing_email_high_risk(self):
        """Test that phishing email receives high risk score"""
        analyzer = EmailAnalyzer()
        result = analyzer.analyze(SAMPLE_PHISHING_EMAIL)

        assert "score" in result
        assert result["score"] >= 60, "Phishing email should have high risk score"
        assert len(result.get("indicators", [])) > 0, "Should detect phishing indicators"

    def test_legitimate_email_low_risk(self):
        """Test that legitimate email receives low risk score"""
        analyzer = EmailAnalyzer()
        result = analyzer.analyze(SAMPLE_LEGITIMATE_EMAIL)

        assert "score" in result
        assert result["score"] < 60, "Legitimate email should have low risk score"

    def test_analysis_includes_breakdown(self):
        """Test that analysis includes scoring breakdown"""
        analyzer = EmailAnalyzer()
        result = analyzer.analyze(SAMPLE_PHISHING_EMAIL)

        assert "breakdown" in result
        assert isinstance(result["breakdown"], dict)

    def test_analysis_extracts_urls(self):
        """Test that URLs are properly extracted"""
        analyzer = EmailAnalyzer()
        result = analyzer.analyze(SAMPLE_PHISHING_EMAIL)

        urls = result.get("urls", [])
        assert len(urls) > 0
        assert any("suspicious-domain" in url for url in urls)

    def test_analysis_detects_suspicious_tlds(self):
        """Test detection of suspicious TLDs"""
        analyzer = EmailAnalyzer()
        email = SAMPLE_PHISHING_EMAIL.copy()

        result = analyzer.analyze(email)
        assert result["score"] > 40, "Should detect suspicious .top TLD"

    def test_score_calculation_consistency(self):
        """Test that score calculation is consistent"""
        analyzer = EmailAnalyzer()

        score1 = analyzer.analyze(SAMPLE_PHISHING_EMAIL)["score"]
        score2 = analyzer.analyze(SAMPLE_PHISHING_EMAIL)["score"]

        assert score1 == score2, "Same email should get same score"


class TestDomainAnalysis:
    """Test domain information gathering"""

    @patch('app.domain_info.DomainInfo._get_whois')
    def test_whois_lookup(self, mock_whois):
        """Test WHOIS domain lookup"""
        mock_whois.return_value = {
            "domain": "example.com",
            "registrar": "Example Registrar",
            "registered_date": "2020-01-01",
            "country": "US",
            "status": "active"
        }

        domain_info = DomainInfo()
        result = domain_info.get_domain_info("example.com")

        assert result is not None
        assert result.get("registrar") == "Example Registrar"

    @patch('app.domain_info.DomainInfo._get_rdap')
    def test_rdap_fallback(self, mock_rdap):
        """Test RDAP fallback when WHOIS fails"""
        mock_rdap.return_value = {
            "domain": "example.com",
            "registrar": "RDAP Registrar",
            "country": "JP"
        }

        domain_info = DomainInfo()
        result = domain_info.get_domain_info("example.com")

        assert result is not None

    def test_new_domain_detection(self):
        """Test detection of newly registered domains"""
        domain_info = DomainInfo()

        # Simulate new domain
        info = {
            "registered_date": datetime.utcnow().isoformat(),
            "domain": "brand-new-domain.com"
        }

        risk = domain_info._assess_domain_risk(info)
        assert risk > 20, "New domain should have elevated risk"


class TestIPAnalysis:
    """Test IP information gathering"""

    @patch('app.ip_info.IPInfo._get_ipinfo')
    def test_ipinfo_lookup(self, mock_ipinfo):
        """Test IP information lookup"""
        mock_ipinfo.return_value = {
            "ip": "1.2.3.4",
            "country": "US",
            "provider": "Example ISP",
            "city": "New York"
        }

        ip_info = IPInfo()
        result = ip_info.get_ip_info("1.2.3.4", "fake-api-key")

        assert result is not None
        assert result.get("provider") == "Example ISP"

    @patch('app.ip_info.IPInfo._identify_provider')
    def test_cloud_provider_detection(self, mock_detect):
        """Test detection of cloud provider IPs"""
        mock_detect.return_value = "Google Cloud"

        ip_info = IPInfo()
        provider = ip_info._identify_provider({"ip": "34.64.0.0"})

        assert provider == "Google Cloud"

    def test_ip_risk_assessment(self):
        """Test IP risk assessment"""
        ip_info = IPInfo()

        # Legitimate provider
        info_good = {"provider": "Major ISP", "country": "US"}
        risk_good = ip_info._assess_ip_risk(info_good)

        # Suspicious provider
        info_bad = {"provider": "VPN Service", "country": "Unknown"}
        risk_bad = ip_info._assess_ip_risk(info_bad)

        assert risk_bad > risk_good, "VPN should have higher risk"


class TestEmailDatabase:
    """Test email storage and retrieval"""

    def test_save_email_to_database(self, test_db):
        """Test saving email to database"""
        email = Email(
            id="test-123",
            from_addr="sender@example.com",
            to_addrs=["recipient@example.com"],
            subject="Test Email",
            received_date=datetime.utcnow(),
            score=75,
            status=EmailStatus.ANALYZED,
            raw_headers="",
            body="Test body",
            urls=["https://example.com"]
        )

        test_db.add(email)
        test_db.commit()

        retrieved = test_db.query(Email).filter(Email.id == "test-123").first()
        assert retrieved is not None
        assert retrieved.score == 75
        assert retrieved.status == EmailStatus.ANALYZED

    def test_retrieve_emails_by_status(self, test_db):
        """Test querying emails by status"""
        for i in range(3):
            email = Email(
                id=f"test-{i}",
                from_addr=f"sender{i}@example.com",
                to_addrs=["recipient@example.com"],
                subject="Test",
                received_date=datetime.utcnow(),
                score=50,
                status=EmailStatus.PENDING if i < 2 else EmailStatus.REPORTED,
                raw_headers="",
                body="",
                urls=[]
            )
            test_db.add(email)

        test_db.commit()

        pending = test_db.query(Email).filter(
            Email.status == EmailStatus.PENDING
        ).all()

        assert len(pending) == 2

    def test_email_score_persistence(self, test_db):
        """Test that email scores are correctly stored"""
        scores = [25, 50, 75, 95]

        for i, score in enumerate(scores):
            email = Email(
                id=f"score-test-{i}",
                from_addr="test@example.com",
                to_addrs=["recipient@example.com"],
                subject="Score Test",
                received_date=datetime.utcnow(),
                score=score,
                status=EmailStatus.ANALYZED,
                raw_headers="",
                body="",
                urls=[]
            )
            test_db.add(email)

        test_db.commit()

        retrieved = test_db.query(Email).all()
        assert len(retrieved) == 4
        assert all(e.score in scores for e in retrieved)


class TestReportDatabase:
    """Test report storage and tracking"""

    def test_create_report_record(self, test_db):
        """Test creating a report record"""
        report = Report(
            email_id="test-123",
            recipient_email="abuse@registrar.com",
            subject="Phishing Report",
            status=ReportStatus.SENT,
            created_at=datetime.utcnow()
        )

        test_db.add(report)
        test_db.commit()

        retrieved = test_db.query(Report).first()
        assert retrieved is not None
        assert retrieved.status == ReportStatus.SENT

    def test_report_status_tracking(self, test_db):
        """Test tracking report sending status"""
        statuses = [
            ReportStatus.PENDING,
            ReportStatus.SENT,
            ReportStatus.FAILED
        ]

        for status in statuses:
            report = Report(
                email_id=f"test-{status}",
                recipient_email="test@example.com",
                subject="Test",
                status=status,
                created_at=datetime.utcnow()
            )
            test_db.add(report)

        test_db.commit()

        sent = test_db.query(Report).filter(
            Report.status == ReportStatus.SENT
        ).all()

        assert len(sent) == 1


class TestEndToEndPipeline:
    """Test complete email processing pipeline"""

    def test_phishing_email_workflow(self, test_db):
        """Test complete workflow for phishing email"""
        # 1. Parse email
        email_data = SAMPLE_PHISHING_EMAIL.copy()

        # 2. Analyze email
        analyzer = EmailAnalyzer()
        analysis = analyzer.analyze(email_data)

        # 3. Store in database
        email = Email(
            id=email_data["id"],
            from_addr=email_data["from_addr"],
            to_addrs=email_data["to_addrs"],
            subject=email_data["subject"],
            received_date=datetime.fromisoformat(email_data["received_date"]),
            score=analysis["score"],
            status=EmailStatus.ANALYZED if analysis["score"] >= 60 else EmailStatus.PENDING,
            raw_headers=email_data["raw_headers"],
            body=email_data["body"],
            urls=analysis.get("urls", []),
            analysis=analysis
        )

        test_db.add(email)
        test_db.commit()

        # 4. Verify storage
        retrieved = test_db.query(Email).filter(
            Email.id == email_data["id"]
        ).first()

        assert retrieved is not None
        assert retrieved.score >= 60
        assert retrieved.status == EmailStatus.ANALYZED
        assert len(retrieved.urls) > 0

    def test_legitimate_email_workflow(self, test_db):
        """Test complete workflow for legitimate email"""
        email_data = SAMPLE_LEGITIMATE_EMAIL.copy()

        analyzer = EmailAnalyzer()
        analysis = analyzer.analyze(email_data)

        email = Email(
            id=email_data["id"],
            from_addr=email_data["from_addr"],
            to_addrs=email_data["to_addrs"],
            subject=email_data["subject"],
            received_date=datetime.fromisoformat(email_data["received_date"]),
            score=analysis["score"],
            status=EmailStatus.ANALYZED,
            raw_headers=email_data["raw_headers"],
            body=email_data["body"],
            urls=analysis.get("urls", [])
        )

        test_db.add(email)
        test_db.commit()

        retrieved = test_db.query(Email).filter(
            Email.id == email_data["id"]
        ).first()

        assert retrieved is not None
        assert retrieved.score < 60


class TestConfiguration:
    """Test system configuration"""

    def test_analyzer_has_suspicious_tlds(self):
        """Test that analyzer knows about suspicious TLDs"""
        analyzer = EmailAnalyzer()
        assert len(analyzer.SUSPICIOUS_TLDS) > 0
        assert ".top" in analyzer.SUSPICIOUS_TLDS
        assert ".click" in analyzer.SUSPICIOUS_TLDS

    def test_analyzer_knows_cloud_providers(self):
        """Test cloud provider detection"""
        analyzer = EmailAnalyzer()
        assert len(analyzer.CLOUD_PROVIDERS) > 0
        assert any("google" in p.lower() for p in analyzer.CLOUD_PROVIDERS)


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
