"""
User profile and preference management for Traceo.
Handles user settings, preferences, and profile information.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field, EmailStr
from sqlalchemy.orm import Session, relationship
from sqlalchemy import Column, String, Integer, JSON, DateTime, Boolean, ForeignKey

from app.database import get_db, Base
from app.security import get_current_user, log_security_event


router = APIRouter(prefix="/users", tags=["user management"])


# ===== Database Models =====

class UserProfile(Base):
    """User profile database model"""
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True, nullable=True)
    full_name = Column(String, nullable=True)
    language = Column(String, default="en")
    theme = Column(String, default="light")
    timezone = Column(String, default="UTC")

    # Notification preferences
    email_notifications = Column(Boolean, default=True)
    push_notifications = Column(Boolean, default=False)
    digest_frequency = Column(String, default="daily")  # daily, weekly, never

    # Analysis preferences
    score_threshold = Column(Integer, default=50)
    auto_report = Column(Boolean, default=False)
    report_recipients = Column(JSON, default=list)

    # Advanced settings
    custom_rules = Column(JSON, default=dict)
    blocked_senders = Column(JSON, default=list)
    trusted_domains = Column(JSON, default=list)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    # Session tracking
    active_sessions = Column(JSON, default=list)

    # Two-Factor Authentication (2FA)
    totp_secret = Column(String(32), nullable=True)  # TOTP secret (encrypted in production)
    is_2fa_enabled = Column(Boolean, default=False)  # 2FA status
    backup_codes_used = Column(JSON, default=list)  # Tracks which backup codes have been used

    # Relationship to backup codes
    backup_codes = relationship("BackupCode", back_populates="user", cascade="all, delete-orphan")

    # Relationship to API keys
    api_keys = relationship("APIKey", back_populates="user", cascade="all, delete-orphan")


class BackupCode(Base):
    """Backup code for account recovery when 2FA device is unavailable"""
    __tablename__ = "backup_codes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('user_profiles.id'), nullable=False, index=True)
    code_hash = Column(String(255), nullable=False, unique=True, index=True)
    used = Column(Boolean, default=False)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship back to user
    user = relationship("UserProfile", back_populates="backup_codes")


class APIKey(Base):
    """API Key for programmatic access to Traceo API"""
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('user_profiles.id'), nullable=False, index=True)

    # Key storage: hash only, not plaintext
    # Format: sk_prod_xxxxxxxxxxxxx (prefix + tier + environment + random)
    key_hash = Column(String(255), nullable=False, unique=True, index=True)  # SHA256/Argon2id hash
    key_prefix = Column(String(20), nullable=False, index=True)  # First 8 chars for display: sk_prod_xxxx

    # Key metadata
    name = Column(String(255), nullable=False)  # User-friendly name
    description = Column(String(500), nullable=True)  # Optional description

    # Tier and rate limiting
    tier = Column(String(20), default="free")  # free, pro, enterprise
    rate_limit = Column(Integer, default=100)  # requests per minute
    monthly_quota = Column(Integer, default=10000)  # total requests per month

    # Usage tracking
    requests_this_month = Column(Integer, default=0)
    requests_lifetime = Column(Integer, default=0)
    last_used = Column(DateTime, nullable=True)
    last_used_ip = Column(String(45), nullable=True)  # IPv6 support

    # Lifecycle management
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True, index=True)  # Optional expiration
    last_rotated_at = Column(DateTime, nullable=True)  # Track rotation history

    # Permissions scoping
    scopes = Column(JSON, default=list)  # [read, write, admin, etc.]

    # Relationship back to user
    user = relationship("UserProfile", back_populates="api_keys")


class EncryptionKey(Base):
    """Encryption key management for field-level encryption"""
    __tablename__ = "encryption_keys"

    id = Column(Integer, primary_key=True, index=True)
    version = Column(Integer, unique=True, index=True, nullable=False)
    status = Column(String(20), default="active", index=True)  # active, rotating, inactive
    description = Column(String(500), nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    created_by = Column(String(255), nullable=False)
    deactivated_at = Column(DateTime, nullable=True)

    # Statistics
    fields_encrypted = Column(Integer, default=0)
    last_rotation_at = Column(DateTime, nullable=True)


class EncryptedField(Base):
    """Encrypted field records with versioning"""
    __tablename__ = "encrypted_fields"

    id = Column(Integer, primary_key=True, index=True)
    field_name = Column(String(255), nullable=False, index=True)  # e.g., 'email', 'phone'
    encrypted_value = Column(String, nullable=False)  # Base64-encoded ciphertext
    key_version = Column(Integer, ForeignKey('encryption_keys.version'), index=True)

    # Field reference (polymorphic: can reference any table)
    entity_type = Column(String(50), nullable=False, index=True)  # e.g., 'user', 'audit_log'
    entity_id = Column(Integer, nullable=False, index=True)

    # Additional authenticated data (for GCM)
    additional_data = Column(String(500), nullable=True)

    # Field hash for searchability (HMAC-SHA256)
    field_hash = Column(String(255), nullable=True, index=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ===== Pydantic Models =====

class NotificationPreferences(BaseModel):
    """Notification preferences"""
    email_notifications: bool = True
    push_notifications: bool = False
    digest_frequency: str = "daily"  # daily, weekly, never


class AnalysisPreferences(BaseModel):
    """Analysis and reporting preferences"""
    score_threshold: int = Field(default=50, ge=0, le=100)
    auto_report: bool = False
    report_recipients: list[str] = []


class SecurityPreferences(BaseModel):
    """Security and filtering preferences"""
    blocked_senders: list[str] = []
    trusted_domains: list[str] = []
    require_two_factor: bool = False


class UserPreferences(BaseModel):
    """Complete user preferences"""
    language: str = "en"
    theme: str = "light"  # light, dark, auto
    timezone: str = "UTC"
    notifications: NotificationPreferences = NotificationPreferences()
    analysis: AnalysisPreferences = AnalysisPreferences()
    security: SecurityPreferences = SecurityPreferences()


class UserProfileResponse(BaseModel):
    """User profile response"""
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    language: str
    theme: str
    timezone: str
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None
    preferences: UserPreferences

    class Config:
        from_attributes = True


class UserProfileUpdate(BaseModel):
    """User profile update"""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    language: Optional[str] = None
    theme: Optional[str] = None
    timezone: Optional[str] = None


# ===== User Profile Routes =====

@router.get("/me/profile", response_model=UserProfileResponse)
async def get_user_profile(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get current user profile and preferences.
    """
    profile = db.query(UserProfile).filter(
        UserProfile.username == current_user.username
    ).first()

    if not profile:
        # Create default profile
        profile = UserProfile(
            username=current_user.username,
            email=current_user.email,
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)

    return UserProfileResponse(
        username=profile.username,
        email=profile.email,
        full_name=profile.full_name,
        language=profile.language,
        theme=profile.theme,
        timezone=profile.timezone,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
        last_login=profile.last_login,
        preferences=UserPreferences(
            language=profile.language,
            theme=profile.theme,
            timezone=profile.timezone,
            notifications=NotificationPreferences(
                email_notifications=profile.email_notifications,
                push_notifications=profile.push_notifications,
                digest_frequency=profile.digest_frequency,
            ),
            analysis=AnalysisPreferences(
                score_threshold=profile.score_threshold,
                auto_report=profile.auto_report,
                report_recipients=profile.report_recipients or [],
            ),
            security=SecurityPreferences(
                blocked_senders=profile.blocked_senders or [],
                trusted_domains=profile.trusted_domains or [],
            ),
        )
    )


@router.put("/me/profile")
async def update_user_profile(
    current_user = Depends(get_current_user),
    profile_update: UserProfileUpdate = None,
    db: Session = Depends(get_db),
):
    """
    Update user profile information.
    """
    profile = db.query(UserProfile).filter(
        UserProfile.username == current_user.username
    ).first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found"
        )

    # Update fields
    if profile_update.email:
        profile.email = profile_update.email
    if profile_update.full_name:
        profile.full_name = profile_update.full_name
    if profile_update.language:
        profile.language = profile_update.language
    if profile_update.theme:
        profile.theme = profile_update.theme
    if profile_update.timezone:
        profile.timezone = profile_update.timezone

    profile.updated_at = datetime.utcnow()

    db.add(profile)
    db.commit()

    log_security_event(
        "profile_updated",
        {"username": current_user.username},
        severity="INFO"
    )

    return {"message": "Profile updated successfully"}


@router.put("/me/preferences")
async def update_preferences(
    current_user = Depends(get_current_user),
    preferences: UserPreferences = None,
    db: Session = Depends(get_db),
):
    """
    Update user preferences (notifications, analysis, security).
    """
    profile = db.query(UserProfile).filter(
        UserProfile.username == current_user.username
    ).first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found"
        )

    # Update preferences
    profile.language = preferences.language
    profile.theme = preferences.theme
    profile.timezone = preferences.timezone

    # Notifications
    profile.email_notifications = preferences.notifications.email_notifications
    profile.push_notifications = preferences.notifications.push_notifications
    profile.digest_frequency = preferences.notifications.digest_frequency

    # Analysis
    profile.score_threshold = preferences.analysis.score_threshold
    profile.auto_report = preferences.analysis.auto_report
    profile.report_recipients = preferences.analysis.report_recipients

    # Security
    profile.blocked_senders = preferences.security.blocked_senders
    profile.trusted_domains = preferences.security.trusted_domains

    profile.updated_at = datetime.utcnow()

    db.add(profile)
    db.commit()

    log_security_event(
        "preferences_updated",
        {"username": current_user.username},
        severity="INFO"
    )

    return {"message": "Preferences updated successfully"}


@router.post("/me/preferences/notifications")
async def update_notification_preferences(
    current_user = Depends(get_current_user),
    notifications: NotificationPreferences = None,
    db: Session = Depends(get_db),
):
    """
    Update notification preferences.
    """
    profile = db.query(UserProfile).filter(
        UserProfile.username == current_user.username
    ).first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found"
        )

    profile.email_notifications = notifications.email_notifications
    profile.push_notifications = notifications.push_notifications
    profile.digest_frequency = notifications.digest_frequency
    profile.updated_at = datetime.utcnow()

    db.add(profile)
    db.commit()

    return {"message": "Notification preferences updated"}


@router.post("/me/preferences/analysis")
async def update_analysis_preferences(
    current_user = Depends(get_current_user),
    analysis: AnalysisPreferences = None,
    db: Session = Depends(get_db),
):
    """
    Update analysis and reporting preferences.
    """
    profile = db.query(UserProfile).filter(
        UserProfile.username == current_user.username
    ).first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found"
        )

    # Validate score threshold
    if not 0 <= analysis.score_threshold <= 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Score threshold must be between 0 and 100"
        )

    # Validate recipient emails
    if analysis.report_recipients:
        from app.security import validate_email
        for recipient in analysis.report_recipients:
            if not validate_email(recipient):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid email: {recipient}"
                )

    profile.score_threshold = analysis.score_threshold
    profile.auto_report = analysis.auto_report
    profile.report_recipients = analysis.report_recipients
    profile.updated_at = datetime.utcnow()

    db.add(profile)
    db.commit()

    return {"message": "Analysis preferences updated"}


@router.post("/me/preferences/security")
async def update_security_preferences(
    current_user = Depends(get_current_user),
    security: SecurityPreferences = None,
    db: Session = Depends(get_db),
):
    """
    Update security and filtering preferences.
    """
    profile = db.query(UserProfile).filter(
        UserProfile.username == current_user.username
    ).first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found"
        )

    profile.blocked_senders = security.blocked_senders
    profile.trusted_domains = security.trusted_domains
    profile.updated_at = datetime.utcnow()

    db.add(profile)
    db.commit()

    log_security_event(
        "security_preferences_updated",
        {
            "username": current_user.username,
            "blocked_senders_count": len(security.blocked_senders),
            "trusted_domains_count": len(security.trusted_domains),
        },
        severity="INFO"
    )

    return {"message": "Security preferences updated"}


@router.get("/me/activity")
async def get_user_activity(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get user activity summary.
    """
    profile = db.query(UserProfile).filter(
        UserProfile.username == current_user.username
    ).first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found"
        )

    return {
        "username": current_user.username,
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
        "last_login": profile.last_login,
        "active_sessions": len(profile.active_sessions or []),
    }


@router.delete("/me/data")
async def delete_user_data(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete all user data (GDPR compliance).

    This is an irreversible operation.
    """
    profile = db.query(UserProfile).filter(
        UserProfile.username == current_user.username
    ).first()

    if profile:
        db.delete(profile)
        db.commit()

    log_security_event(
        "user_data_deleted",
        {"username": current_user.username},
        severity="WARNING"
    )

    return {"message": "All user data has been deleted"}
