from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings"""

    # API
    api_title: str = "Traceo"
    api_version: str = "0.2.0"
    debug: bool = False

    # Language
    default_lang: str = "en"

    # Database
    database_url: str = "sqlite:///./traceo.db"  # Default to SQLite for PoC
    db_echo: bool = False

    # IMAP Configuration
    imap_server: Optional[str] = None
    imap_port: int = 993
    imap_user: Optional[str] = None
    imap_password: Optional[str] = None
    imap_use_ssl: bool = True

    # SMTP Configuration
    smtp_server: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_use_tls: bool = True

    # Email Analysis
    score_threshold_auto_report: int = 70
    score_threshold_warning: int = 50

    # External APIs
    virustotal_api_key: Optional[str] = None
    geoip_database_path: Optional[str] = None

    # Logging
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
