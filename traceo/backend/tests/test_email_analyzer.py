"""
Unit tests for email analyzer
"""

import pytest
from app.email_analyzer import EmailAnalyzer


@pytest.fixture
def analyzer():
    return EmailAnalyzer()


def test_analyze_clean_email(analyzer):
    """Test analysis of clean email"""
    email_data = {
        "raw_headers": "SPF: pass\nDKIM: pass\nDMARC: pass",
        "body": "This is a legitimate email from our customer.",
        "urls": ["https://example.com"],
    }

    result = analyzer.analyze(email_data)

    assert result["score"] < 30
    assert isinstance(result["breakdown"], dict)
    assert isinstance(result["indicators"], list)


def test_analyze_suspicious_email(analyzer):
    """Test analysis of suspicious email"""
    email_data = {
        "raw_headers": "SPF: fail\nDKIM: fail\nDMARC: fail",
        "body": """
            Please verify your account immediately.
            Click here to confirm your identity.
            Your account will be disabled if you don't act now.
        """,
        "urls": ["https://verify-account.click/login"],
    }

    result = analyzer.analyze(email_data)

    assert result["score"] >= 50
    assert len(result["indicators"]) > 0


def test_analyze_phishing_email(analyzer):
    """Test analysis of phishing email"""
    email_data = {
        "raw_headers": "SPF: fail\nDKIM: fail\nReceived: from [35.187.208.83]",
        "body": """
            URGENT: Update your banking information immediately!
            Click below to confirm your credentials.
            Failure to act may result in account suspension.
        """,
        "urls": [
            "https://confirm-credentials.top/banking",
            "https://update-account.xyz/info",
        ],
    }

    result = analyzer.analyze(email_data)

    assert result["score"] >= 70
    assert "Suspicious URLs detected" in result["indicators"]


def test_extract_urls():
    """Test URL extraction"""
    analyzer = EmailAnalyzer()
    urls = analyzer._extract_urls("Check https://example.com and http://test.org")
    assert len(urls) == 2


def test_extract_ips():
    """Test IP extraction"""
    analyzer = EmailAnalyzer()
    headers = "Received: from mail.example.com [192.168.1.1]"
    ips = analyzer._extract_ips_from_headers(headers)
    assert "192.168.1.1" in ips


def test_suspicious_tlds():
    """Test detection of suspicious TLDs"""
    analyzer = EmailAnalyzer()
    urls = [
        "https://verify.top/login",
        "https://bank.click/update",
        "https://paypal.win/confirm",
    ]

    for url in urls:
        assert any(url.endswith(tld) for tld in analyzer.SUSPICIOUS_TLDS)
