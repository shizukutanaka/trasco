import re
import socket
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from loguru import logger
import requests

from app.settings import settings


class EmailAnalyzer:
    """Analyze email headers and content for phishing indicators"""

    # Suspicious TLDs
    SUSPICIOUS_TLDS = [
        ".top", ".click", ".download", ".win", ".stream",
        ".review", ".faith", ".date", ".men", ".rocks",
        ".loan", ".xyz", ".gdn", ".work"
    ]

    # Cloud provider IP ranges (simplified)
    CLOUD_PROVIDERS = ["google", "amazon", "microsoft", "digitalocean", "linode"]

    def __init__(self):
        self.scores = {}

    def analyze(self, email_data: Dict) -> Dict:
        """Analyze email and return risk assessment"""
        self.scores = {
            "header_analysis": 0,
            "url_analysis": 0,
            "domain_analysis": 0,
            "attachment_analysis": 0,
            "content_analysis": 0,
        }

        # Run analyses
        self._analyze_headers(email_data.get("raw_headers", ""))
        self._analyze_urls(email_data.get("urls", []))
        self._analyze_content(email_data.get("body", ""))

        # Calculate total score
        total_score = self._calculate_score()

        return {
            "score": total_score,
            "breakdown": self.scores,
            "indicators": self._get_indicators(),
        }

    def _analyze_headers(self, headers: str) -> int:
        """Analyze email headers for SPF/DKIM/DMARC"""
        score = 0

        # Check for SPF
        if "SPF: fail" in headers or "spf=fail" in headers:
            score += 30
            logger.debug("SPF failed")

        # Check for DKIM
        if "DKIM: fail" in headers or "dkim=fail" in headers:
            score += 25
            logger.debug("DKIM failed")

        # Check for DMARC
        if "DMARC: fail" in headers or "dmarc=fail" in headers:
            score += 35
            logger.debug("DMARC failed")

        # Check for suspicious originating IP
        received_ips = self._extract_ips_from_headers(headers)
        for ip in received_ips:
            provider = self._check_cloud_provider(ip)
            if provider:
                score += 15
                logger.debug(f"Suspicious cloud IP detected: {ip} ({provider})")

        self.scores["header_analysis"] = min(score, 100)
        return self.scores["header_analysis"]

    def _analyze_urls(self, urls: List[str]) -> int:
        """Analyze URLs for phishing indicators"""
        score = 0

        for url in urls:
            # Check TLD
            for tld in self.SUSPICIOUS_TLDS:
                if url.lower().endswith(tld):
                    score += 20
                    logger.debug(f"Suspicious TLD detected: {tld}")
                    break

            # Check domain age (would require WHOIS API)
            # Placeholder for future implementation
            domain = self._extract_domain(url)
            if domain:
                # Check if domain contains suspicious patterns
                if "verify" in domain or "confirm" in domain or "update" in domain:
                    score += 15
                    logger.debug(f"Suspicious domain pattern: {domain}")

        self.scores["url_analysis"] = min(score, 100)
        return self.scores["url_analysis"]

    def _analyze_content(self, body: str) -> int:
        """Analyze email body for phishing patterns"""
        score = 0

        # Check for common phishing phrases
        phishing_phrases = [
            r"verify\s+(?:your|account|identity)",
            r"confirm\s+(?:your|account|password)",
            r"update\s+(?:your|account|information)",
            r"urgent\s+(?:action|attention|required)",
            r"click\s+(?:here|below|link)",
            r"expire",
            r"suspend",
            r"disable",
            r"unlock",
        ]

        for phrase in phishing_phrases:
            if re.search(phrase, body, re.IGNORECASE):
                score += 5
                logger.debug(f"Phishing phrase detected: {phrase}")

        # Check for grammar/formatting issues (indicators of low-quality phishing)
        # This is a simplified check
        sentence_count = len(re.findall(r"[.!?]+", body))
        if sentence_count > 0:
            avg_sentence_length = len(body.split()) / sentence_count
            if avg_sentence_length > 30:  # Unusually long sentences
                score += 5
                logger.debug("Unusual sentence length detected")

        self.scores["content_analysis"] = min(score, 100)
        return self.scores["content_analysis"]

    def _calculate_score(self) -> int:
        """Calculate total risk score (0-100)"""
        weights = {
            "header_analysis": 0.35,
            "url_analysis": 0.30,
            "domain_analysis": 0.15,
            "attachment_analysis": 0.10,
            "content_analysis": 0.10,
        }

        total = sum(
            self.scores.get(key, 0) * weight
            for key, weight in weights.items()
        )

        return min(int(total), 100)

    def _get_indicators(self) -> List[str]:
        """Get list of detected phishing indicators"""
        indicators = []

        if self.scores["header_analysis"] > 30:
            indicators.append("Suspicious email headers (SPF/DKIM/DMARC issues)")

        if self.scores["url_analysis"] > 20:
            indicators.append("Suspicious URLs detected")

        if self.scores["content_analysis"] > 15:
            indicators.append("Phishing-like content detected")

        return indicators

    def _extract_ips_from_headers(self, headers: str) -> List[str]:
        """Extract IP addresses from email headers"""
        ip_pattern = r"\b(?:\d{1,3}\.){3}\d{1,3}\b"
        return re.findall(ip_pattern, headers)

    def _check_cloud_provider(self, ip: str) -> str:
        """Check if IP belongs to cloud provider"""
        try:
            hostname = socket.gethostbyaddr(ip)[0]
            for provider in self.CLOUD_PROVIDERS:
                if provider in hostname.lower():
                    return provider
        except:
            pass
        return ""

    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL"""
        try:
            # Remove protocol
            domain = url.replace("https://", "").replace("http://", "")
            # Remove path
            domain = domain.split("/")[0]
            # Remove port
            domain = domain.split(":")[0]
            return domain
        except:
            return ""


# Global analyzer instance
analyzer = EmailAnalyzer()
