import requests
import whois
from typing import Dict, Optional
from datetime import datetime
from loguru import logger


class DomainInfo:
    """Retrieve domain information from WHOIS and RDAP"""

    RDAP_BASE_URL = "https://rdap.org"
    SUSPICIOUS_REGISTRARS = ["west263", "alibaba", "namecheap", "godaddy"]

    def __init__(self):
        self.cache = {}

    def get_domain_info(self, domain: str) -> Dict:
        """Get comprehensive domain information"""
        # Try WHOIS first
        try:
            whois_info = self._get_whois(domain)
            if whois_info:
                return whois_info
        except Exception as e:
            logger.warning(f"WHOIS lookup failed for {domain}: {e}")

        # Fallback to RDAP
        try:
            rdap_info = self._get_rdap(domain)
            if rdap_info:
                return rdap_info
        except Exception as e:
            logger.warning(f"RDAP lookup failed for {domain}: {e}")

        return {
            "domain": domain,
            "status": "error",
            "error": "Could not retrieve domain information",
        }

    def _get_whois(self, domain: str) -> Optional[Dict]:
        """Get domain info from WHOIS"""
        try:
            w = whois.whois(domain)

            # Extract relevant information
            info = {
                "domain": domain,
                "status": "success",
                "registrar": str(w.registrar) if w.registrar else "Unknown",
                "creation_date": self._format_date(w.creation_date),
                "expiration_date": self._format_date(w.expiration_date),
                "name_servers": w.name_servers if w.name_servers else [],
                "registrant_country": self._extract_country(w),
                "abuse_email": self._extract_abuse_email(w),
            }

            # Calculate domain age
            if w.creation_date:
                creation = (
                    w.creation_date[0]
                    if isinstance(w.creation_date, list)
                    else w.creation_date
                )
                info["domain_age_days"] = (
                    datetime.utcnow() - creation
                ).days

            # Risk assessment
            info["risk_score"] = self._assess_domain_risk(info)

            logger.info(f"Retrieved WHOIS info for {domain}")
            return info

        except Exception as e:
            logger.debug(f"WHOIS error for {domain}: {e}")
            return None

    def _get_rdap(self, domain: str) -> Optional[Dict]:
        """Get domain info from RDAP"""
        try:
            url = f"{self.RDAP_BASE_URL}/domain/{domain}"
            response = requests.get(url, timeout=10)

            if response.status_code != 200:
                return None

            data = response.json()

            info = {
                "domain": domain,
                "status": "success",
                "registrar": self._extract_rdap_registrar(data),
                "name_servers": self._extract_rdap_nameservers(data),
                "abuse_email": self._extract_rdap_abuse_email(data),
            }

            logger.info(f"Retrieved RDAP info for {domain}")
            return info

        except Exception as e:
            logger.debug(f"RDAP error for {domain}: {e}")
            return None

    def _format_date(self, date) -> Optional[str]:
        """Format date to ISO string"""
        if isinstance(date, list):
            date = date[0]
        if isinstance(date, datetime):
            return date.isoformat()
        return str(date) if date else None

    def _extract_country(self, whois_data) -> Optional[str]:
        """Extract country from WHOIS data"""
        if hasattr(whois_data, "registrant_country"):
            return whois_data.registrant_country
        if hasattr(whois_data, "country"):
            return whois_data.country
        return None

    def _extract_abuse_email(self, whois_data) -> Optional[str]:
        """Extract abuse contact email"""
        if hasattr(whois_data, "abuse_email"):
            return whois_data.abuse_email
        if hasattr(whois_data, "admin_email"):
            return whois_data.admin_email
        return None

    def _extract_rdap_registrar(self, data: Dict) -> Optional[str]:
        """Extract registrar from RDAP response"""
        if "entities" in data:
            for entity in data["entities"]:
                if "roles" in entity and "registrar" in entity["roles"]:
                    if "vcardArray" in entity:
                        return entity["vcardArray"][1][1][3]
        return None

    def _extract_rdap_nameservers(self, data: Dict) -> list:
        """Extract name servers from RDAP response"""
        nameservers = []
        if "nameservers" in data:
            for ns in data["nameservers"]:
                if "ldhName" in ns:
                    nameservers.append(ns["ldhName"])
        return nameservers

    def _extract_rdap_abuse_email(self, data: Dict) -> Optional[str]:
        """Extract abuse email from RDAP response"""
        if "entities" in data:
            for entity in data["entities"]:
                if "roles" in entity and "abuse" in entity["roles"]:
                    if "vcardArray" in entity:
                        vcard = entity["vcardArray"]
                        for item in vcard[1:]:
                            if item[0] == "email":
                                return item[3]
        return None

    def _assess_domain_risk(self, info: Dict) -> int:
        """Assess risk score based on domain info"""
        score = 0

        # New domain (< 30 days)
        if info.get("domain_age_days", 0) < 30:
            score += 25

        # Suspicious registrar
        registrar = (info.get("registrar") or "").lower()
        for suspicious in self.SUSPICIOUS_REGISTRARS:
            if suspicious in registrar:
                score += 20
                break

        # Suspicious country (e.g., CN for phishing)
        country = info.get("registrant_country", "").upper()
        if country in ["CN", "RU", "KP"]:  # Simplified list
            score += 15

        # No name servers
        if not info.get("name_servers"):
            score += 10

        # Cloudflare (often used for anonymity)
        nameservers = info.get("name_servers", [])
        if any("cloudflare" in str(ns).lower() for ns in nameservers):
            score += 10

        return min(score, 100)

    def get_abuse_contact(self, domain: str) -> Optional[str]:
        """Get abuse contact email for domain"""
        info = self.get_domain_info(domain)
        return info.get("abuse_email")


# Global instance
domain_lookup = DomainInfo()
