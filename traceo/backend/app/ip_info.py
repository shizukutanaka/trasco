import socket
import requests
from typing import Dict, Optional
from loguru import logger


class IPInfo:
    """Retrieve IP address information"""

    # Free IP geolocation APIs
    IPINFO_API = "https://ipinfo.io/{ip}/json"
    ABUSEIPDB_API = "https://api.abuseipdb.com/api/v2/check"

    def __init__(self):
        self.cache = {}

    def get_ip_info(self, ip: str, api_key: Optional[str] = None) -> Dict:
        """Get comprehensive IP information"""
        if ip in self.cache:
            return self.cache[ip]

        info = {
            "ip": ip,
            "hostname": self._reverse_lookup(ip),
            "asn": None,
            "provider": None,
            "country": None,
            "city": None,
            "abuse_score": 0,
        }

        # Try IPInfo API (free tier available)
        try:
            ipinfo = self._get_ipinfo(ip)
            if ipinfo:
                info.update(ipinfo)
        except Exception as e:
            logger.warning(f"IPInfo lookup failed for {ip}: {e}")

        # Try AbuseIPDB (requires API key)
        if api_key:
            try:
                abuse_info = self._get_abuseipdb(ip, api_key)
                if abuse_info:
                    info.update(abuse_info)
            except Exception as e:
                logger.warning(f"AbuseIPDB lookup failed for {ip}: {e}")

        # Assess risk
        info["risk_score"] = self._assess_ip_risk(info)

        self.cache[ip] = info
        return info

    def _reverse_lookup(self, ip: str) -> Optional[str]:
        """Reverse DNS lookup"""
        try:
            hostname = socket.gethostbyaddr(ip)[0]
            logger.debug(f"Reverse lookup {ip} -> {hostname}")
            return hostname
        except socket.error:
            return None

    def _get_ipinfo(self, ip: str) -> Optional[Dict]:
        """Get info from IPInfo API"""
        try:
            response = requests.get(
                self.IPINFO_API.format(ip=ip),
                timeout=5,
            )
            if response.status_code != 200:
                return None

            data = response.json()
            return {
                "provider": self._identify_provider(data),
                "country": data.get("country"),
                "city": data.get("city"),
                "org": data.get("org"),
                "asn": self._extract_asn(data.get("org")),
            }

        except Exception as e:
            logger.debug(f"IPInfo error: {e}")
            return None

    def _get_abuseipdb(self, ip: str, api_key: str) -> Optional[Dict]:
        """Get info from AbuseIPDB API"""
        try:
            headers = {
                "Key": api_key,
                "Accept": "application/json",
            }
            params = {
                "ipAddress": ip,
                "maxAgeInDays": 90,
            }

            response = requests.get(
                self.ABUSEIPDB_API,
                headers=headers,
                params=params,
                timeout=5,
            )

            if response.status_code != 200:
                return None

            data = response.json()
            if "data" in data:
                abuse_data = data["data"]
                return {
                    "abuse_score": abuse_data.get("abuseConfidenceScore", 0),
                    "is_whitelisted": abuse_data.get("isWhitelisted", False),
                    "reports": abuse_data.get("totalReports", 0),
                }

            return None

        except Exception as e:
            logger.debug(f"AbuseIPDB error: {e}")
            return None

    def _identify_provider(self, ipinfo_data: Dict) -> Optional[str]:
        """Identify cloud provider from IP info"""
        org = (ipinfo_data.get("org") or "").lower()

        providers = {
            "google": ["google cloud", "gcp"],
            "amazon": ["amazon", "aws"],
            "microsoft": ["microsoft azure", "azure"],
            "cloudflare": ["cloudflare"],
            "digitalocean": ["digitalocean"],
            "linode": ["linode", "akamai"],
            "ovh": ["ovh"],
            "hetzner": ["hetzner"],
        }

        for provider, keywords in providers.items():
            if any(keyword in org for keyword in keywords):
                return provider

        return org if org else None

    def _extract_asn(self, org: Optional[str]) -> Optional[str]:
        """Extract ASN from org string"""
        if not org:
            return None
        # Format is typically "AS12345 Company Name"
        parts = org.split()
        if parts and parts[0].startswith("AS"):
            return parts[0]
        return None

    def _assess_ip_risk(self, info: Dict) -> int:
        """Assess risk score based on IP info"""
        score = 0

        # High abuse score
        if info.get("abuse_score", 0) > 50:
            score += 30

        # Known phishing countries (simplified)
        country = info.get("country", "").upper()
        if country in ["CN", "RU", "KP", "IR"]:
            score += 15

        # Cloud provider (often used for phishing)
        provider = (info.get("provider") or "").lower()
        cloud_providers = ["google", "amazon", "microsoft", "digitalocean"]
        if any(p in provider for p in cloud_providers):
            score += 10

        # VPN/Proxy detected
        if info.get("is_whitelisted") is False and info.get("reports", 0) > 0:
            score += 5

        return min(score, 100)


# Global instance
ip_lookup = IPInfo()
