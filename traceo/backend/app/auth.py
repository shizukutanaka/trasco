"""
Authentication routes for Traceo backend.
Handles user login, token refresh, and logout operations.
"""

from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, status, Depends, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.security import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    verify_token,
    get_current_user,
    auth_limiter,
    hash_password,
    validate_email,
    log_security_event,
)
from app.database import get_db
from app.models import User as UserModel


router = APIRouter(prefix="/auth", tags=["authentication"])


# ===== Pydantic Models =====

class LoginRequest(BaseModel):
    """User login request"""
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=100)


class TokenResponse(BaseModel):
    """Token response"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict


class UserResponse(BaseModel):
    """User information response"""
    username: str
    email: Optional[str] = None
    disabled: bool = False
    created_at: Optional[datetime] = None
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True


class ChangePasswordRequest(BaseModel):
    """Change password request"""
    old_password: str = Field(..., min_length=6)
    new_password: str = Field(..., min_length=8)
    confirm_password: str = Field(..., min_length=8)


class PasswordResetRequest(BaseModel):
    """Password reset request"""
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Password reset confirmation"""
    token: str
    new_password: str = Field(..., min_length=8)


class TwoFactorSetupResponse(BaseModel):
    """2FA setup response"""
    secret: str
    backup_codes: list[str]
    qr_code: str  # Base64 encoded PNG


class Verify2FARequest(BaseModel):
    """2FA verification request"""
    token: str = Field(..., min_length=6, max_length=10, description="6-digit TOTP or backup code")


class Disable2FARequest(BaseModel):
    """Disable 2FA request"""
    password: str = Field(..., min_length=6, description="Current password for verification")


class Regenerate2FACodesRequest(BaseModel):
    """Regenerate backup codes request"""
    token: str = Field(..., min_length=6, max_length=10, description="TOTP token for verification")


class TwoFactorStatusResponse(BaseModel):
    """2FA status response"""
    is_enabled: bool
    secret_set: bool
    unused_backup_codes: int
    last_updated: Optional[str]


# ===== API Key Management Models =====

class APIKeyCreateRequest(BaseModel):
    """Create API key request"""
    name: str = Field(..., min_length=1, max_length=255, description="User-friendly name")
    description: Optional[str] = Field(None, max_length=500)
    tier: str = Field("free", description="free, pro, or enterprise")
    expires_in_days: Optional[int] = Field(None, ge=1, le=365, description="Optional expiration")
    scopes: Optional[list[str]] = Field(["read"], description="Permission scopes")


class APIKeyResponse(BaseModel):
    """API key response"""
    id: int
    name: str
    key_prefix: str  # Only show prefix, not full key
    tier: str
    rate_limit: int
    monthly_quota: int
    is_active: bool
    created_at: datetime
    expires_at: Optional[datetime] = None
    last_used: Optional[datetime] = None
    scopes: list[str]

    class Config:
        from_attributes = True


class APIKeyCreateResponse(BaseModel):
    """Response when creating API key (includes plaintext)"""
    plaintext_key: str  # Only shown once during creation
    key: APIKeyResponse


class APIKeyRotateResponse(BaseModel):
    """Response when rotating API key"""
    plaintext_key: str  # New key (only shown once)
    message: str


class APIKeyStatsResponse(BaseModel):
    """API key usage statistics"""
    id: int
    name: str
    tier: str
    created_at: datetime
    requests_lifetime: int
    requests_this_month: int
    monthly_quota: int
    quota_remaining: int
    quota_percentage: float
    last_used: Optional[datetime] = None
    is_active: bool
    expires_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ===== Authentication Routes =====

@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    credentials: LoginRequest,
    db: Session = Depends(get_db),
):
    """
    User login endpoint.

    Returns access and refresh tokens on successful authentication.
    """
    # Rate limiting
    client_ip = request.client.host if request.client else "unknown"
    if not auth_limiter.is_allowed(client_ip):
        log_security_event(
            "login_rate_limit_exceeded",
            {"ip": client_ip, "username": credentials.username},
            severity="WARNING"
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Try again later."
        )

    # Authenticate user
    user = authenticate_user(credentials.username, credentials.password)

    if not user:
        log_security_event(
            "login_failed",
            {"ip": client_ip, "username": credentials.username},
            severity="WARNING"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create tokens
    access_token_expires = timedelta(minutes=30)
    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=access_token_expires
    )
    refresh_token = create_refresh_token(data={"sub": user.username})

    # Log successful login
    log_security_event(
        "login_success",
        {"ip": client_ip, "username": user.username},
        severity="INFO"
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=30 * 60,  # 30 minutes in seconds
        user={
            "username": user.username,
            "email": user.email,
        }
    )


@router.post("/token/refresh", response_model=TokenResponse)
async def refresh_token(
    request: Request,
    token: str = Field(..., description="Refresh token"),
    db: Session = Depends(get_db),
):
    """
    Refresh access token using refresh token.

    Returns new access and refresh tokens.
    """
    # Verify refresh token
    try:
        token_data = verify_token(token)
    except Exception as e:
        log_security_event(
            "token_refresh_failed",
            {"error": str(e)},
            severity="WARNING"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create new tokens
    access_token_expires = timedelta(minutes=30)
    access_token = create_access_token(
        data={"sub": token_data.username},
        expires_delta=access_token_expires
    )
    new_refresh_token = create_refresh_token(data={"sub": token_data.username})

    log_security_event(
        "token_refreshed",
        {"username": token_data.username},
        severity="INFO"
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        expires_in=30 * 60,
        user={"username": token_data.username}
    )


@router.post("/logout")
async def logout(
    request: Request,
    current_user = Depends(get_current_user),
):
    """
    Logout current user.

    Token is invalidated on the client side by deleting it.
    """
    log_security_event(
        "logout_success",
        {"username": current_user.username},
        severity="INFO"
    )

    return {
        "message": "Successfully logged out",
        "username": current_user.username
    }


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user = Depends(get_current_user),
):
    """
    Get current user information.

    Returns details of the authenticated user.
    """
    return UserResponse(
        username=current_user.username,
        email=current_user.email,
        disabled=current_user.disabled,
    )


@router.post("/change-password")
async def change_password(
    current_user = Depends(get_current_user),
    password_data: ChangePasswordRequest = None,
):
    """
    Change user password.

    Requires current password verification.
    """
    # Verify old password
    from app.security import verify_password, DEMO_CREDENTIALS

    if current_user.username not in DEMO_CREDENTIALS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found"
        )

    # Verify passwords match
    if password_data.new_password != password_data.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords do not match"
        )

    # Update password
    if verify_password(password_data.old_password, DEMO_CREDENTIALS[current_user.username]):
        DEMO_CREDENTIALS[current_user.username] = hash_password(password_data.new_password)

        log_security_event(
            "password_changed",
            {"username": current_user.username},
            severity="INFO"
        )

        return {"message": "Password changed successfully"}
    else:
        log_security_event(
            "password_change_failed",
            {"username": current_user.username, "reason": "invalid_old_password"},
            severity="WARNING"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid current password"
        )


@router.post("/verify-email")
async def verify_email(
    current_user = Depends(get_current_user),
    email: str = Field(..., description="Email to verify"),
):
    """
    Verify email address.

    In production, this would send a verification email.
    """
    if not validate_email(email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email format"
        )

    log_security_event(
        "email_verification_requested",
        {"username": current_user.username, "email": email},
        severity="INFO"
    )

    return {
        "message": "Verification email sent",
        "email": email
    }


@router.get("/health-check")
async def health_check():
    """
    Check authentication service health.
    """
    return {
        "status": "healthy",
        "service": "authentication",
        "timestamp": datetime.utcnow().isoformat()
    }


# ===== Two-Factor Authentication (2FA) Routes =====

@router.post("/2fa/setup", response_model=TwoFactorSetupResponse)
async def setup_2fa(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Initiate 2FA setup for the current user.

    Returns:
    - TOTP secret (for manual entry)
    - QR code (for scanning with authenticator app)
    - 10 backup codes for account recovery

    Important: Save the backup codes in a safe place!
    """
    from app.two_factor_auth import TwoFactorAuthService
    import base64

    # Generate 2FA setup
    secret, backup_codes, qr_code_bytes = TwoFactorAuthService.setup_2fa(
        current_user.id,
        current_user.username,
        db
    )

    # Encode QR code to base64
    qr_code_base64 = base64.b64encode(qr_code_bytes).decode()

    log_security_event(
        "2fa_setup_initiated",
        {"username": current_user.username},
        severity="INFO"
    )

    return TwoFactorSetupResponse(
        secret=secret,
        backup_codes=backup_codes,
        qr_code=qr_code_base64
    )


@router.post("/2fa/confirm", status_code=status.HTTP_200_OK)
async def confirm_2fa(
    current_user = Depends(get_current_user),
    verify_request: Verify2FARequest = None,
    db: Session = Depends(get_db),
):
    """
    Confirm and enable 2FA for the current user.

    Requires:
    - TOTP token from authenticator app (must be fresh)

    Stores backup codes in the database.
    """
    from app.two_factor_auth import TwoFactorAuthService

    try:
        # Get user profile to retrieve temporary secret
        from app.user_profiles import UserProfile
        user_profile = db.query(UserProfile).filter(
            UserProfile.username == current_user.username
        ).first()

        if not user_profile or not user_profile.totp_secret:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No 2FA setup in progress. Call /auth/2fa/setup first."
            )

        # Verify TOTP token
        if not TwoFactorAuthService.verify_totp(user_profile.totp_secret, verify_request.token):
            log_security_event(
                "2fa_confirmation_failed",
                {
                    "username": current_user.username,
                    "reason": "invalid_totp"
                },
                severity="WARNING"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid TOTP token. Please try again."
            )

        # Generate fresh backup codes for confirmation
        backup_codes = TwoFactorAuthService.generate_backup_codes()

        # Confirm 2FA (this saves the secret and backup codes)
        TwoFactorAuthService.confirm_2fa(
            current_user.id,
            user_profile.totp_secret,
            verify_request.token,
            backup_codes,
            db
        )

        log_security_event(
            "2fa_enabled",
            {"username": current_user.username},
            severity="INFO"
        )

        return {
            "message": "2FA enabled successfully",
            "backup_codes": backup_codes
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/2fa/verify", status_code=status.HTTP_200_OK)
async def verify_2fa_login(
    username: str = Field(..., description="Username"),
    verify_request: Verify2FARequest = None,
    db: Session = Depends(get_db),
):
    """
    Verify 2FA token during login.

    Accepts:
    - 6-digit TOTP code from authenticator
    - Backup code (format: XXX-XXX-XXX)

    This endpoint is called after successful password authentication
    if user has 2FA enabled.
    """
    from app.two_factor_auth import TwoFactorAuthService
    from app.user_profiles import UserProfile

    user = db.query(UserProfile).filter(
        UserProfile.username == username
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    # Verify token
    is_valid, error_message = TwoFactorAuthService.verify_login_token(
        user.id,
        verify_request.token,
        db
    )

    if not is_valid:
        log_security_event(
            "2fa_verification_failed",
            {
                "username": username,
                "reason": error_message or "invalid_token"
            },
            severity="WARNING"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error_message or "Invalid 2FA token"
        )

    log_security_event(
        "2fa_verified",
        {"username": username},
        severity="INFO"
    )

    return {
        "message": "2FA verification successful",
        "username": username
    }


@router.post("/2fa/disable", status_code=status.HTTP_200_OK)
async def disable_2fa(
    current_user = Depends(get_current_user),
    disable_request: Disable2FARequest = None,
    db: Session = Depends(get_db),
):
    """
    Disable 2FA for the current user.

    Requires password verification for security.
    """
    from app.two_factor_auth import TwoFactorAuthService
    from app.security import verify_password, DEMO_CREDENTIALS

    # Verify password
    if current_user.username not in DEMO_CREDENTIALS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User credentials not found"
        )

    if not verify_password(disable_request.password, DEMO_CREDENTIALS[current_user.username]):
        log_security_event(
            "2fa_disable_failed",
            {
                "username": current_user.username,
                "reason": "invalid_password"
            },
            severity="WARNING"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password"
        )

    # Disable 2FA
    success = TwoFactorAuthService.disable_2fa(current_user.id, db)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to disable 2FA"
        )

    log_security_event(
        "2fa_disabled",
        {"username": current_user.username},
        severity="WARNING"
    )

    return {"message": "2FA disabled successfully"}


@router.post("/2fa/regenerate-codes", status_code=status.HTTP_200_OK)
async def regenerate_backup_codes(
    current_user = Depends(get_current_user),
    regen_request: Regenerate2FACodesRequest = None,
    db: Session = Depends(get_db),
):
    """
    Regenerate backup codes for 2FA.

    Requires TOTP verification.
    Old backup codes are invalidated.
    """
    from app.two_factor_auth import TwoFactorAuthService

    new_codes = TwoFactorAuthService.regenerate_backup_codes(
        current_user.id,
        regen_request.token,
        db
    )

    if not new_codes:
        log_security_event(
            "backup_codes_regeneration_failed",
            {
                "username": current_user.username,
                "reason": "invalid_totp_or_2fa_not_enabled"
            },
            severity="WARNING"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid TOTP or 2FA not enabled"
        )

    log_security_event(
        "backup_codes_regenerated",
        {"username": current_user.username},
        severity="INFO"
    )

    return {
        "message": "Backup codes regenerated successfully",
        "backup_codes": new_codes
    }


@router.get("/2fa/status", response_model=TwoFactorStatusResponse)
async def get_2fa_status(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get 2FA status for the current user.

    Returns:
    - Whether 2FA is enabled
    - Number of unused backup codes
    - Whether TOTP secret is configured
    """
    from app.two_factor_auth import TwoFactorAuthService

    status_info = TwoFactorAuthService.get_2fa_status(current_user.id, db)

    if "error" in status_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=status_info["error"]
        )

    return TwoFactorStatusResponse(**status_info)


# ===== API Key Management Routes =====

@router.post("/api-keys/create", response_model=APIKeyCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    current_user = Depends(get_current_user),
    request_data: APIKeyCreateRequest = None,
    db: Session = Depends(get_db),
):
    """
    Create a new API key for the current user.

    Returns the plaintext key (only shown once), so users must save it immediately.

    Query Parameters:
    - name: User-friendly key name
    - tier: free, pro, or enterprise (default: free)
    - expires_in_days: Optional expiration period (1-365 days)
    """
    from app.api_key_service import APIKeyService

    try:
        plaintext_key, api_key = APIKeyService.create_api_key(
            user_id=current_user.id,
            name=request_data.name,
            db=db,
            tier=request_data.tier,
            description=request_data.description,
            expires_in_days=request_data.expires_in_days,
            scopes=request_data.scopes,
        )

        log_security_event(
            "api_key_created",
            {
                "username": current_user.username,
                "key_id": api_key.id,
                "tier": request_data.tier,
                "name": request_data.name,
            },
            severity="INFO"
        )

        return APIKeyCreateResponse(
            plaintext_key=plaintext_key,
            key=APIKeyResponse.from_orm(api_key)
        )

    except ValueError as e:
        log_security_event(
            "api_key_creation_failed",
            {
                "username": current_user.username,
                "error": str(e),
            },
            severity="WARNING"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/api-keys", response_model=list[APIKeyResponse])
async def list_api_keys(
    current_user = Depends(get_current_user),
    include_inactive: bool = False,
    db: Session = Depends(get_db),
):
    """
    List all API keys for the current user.

    Query Parameters:
    - include_inactive: Include deactivated keys (default: false)
    """
    from app.api_key_service import APIKeyService

    try:
        keys = APIKeyService.get_user_keys(
            user_id=current_user.id,
            db=db,
            include_inactive=include_inactive,
        )

        return [APIKeyResponse.from_orm(key) for key in keys]

    except Exception as e:
        log_security_event(
            "api_keys_list_failed",
            {"username": current_user.username, "error": str(e)},
            severity="WARNING"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve API keys"
        )


@router.get("/api-keys/{key_id}", response_model=APIKeyResponse)
async def get_api_key(
    current_user = Depends(get_current_user),
    key_id: int = Field(..., description="API Key ID"),
    db: Session = Depends(get_db),
):
    """
    Get details of a specific API key.

    Path Parameters:
    - key_id: The ID of the API key
    """
    from app.user_profiles import APIKey

    api_key = db.query(APIKey).filter(
        APIKey.id == key_id,
        APIKey.user_id == current_user.id
    ).first()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )

    return APIKeyResponse.from_orm(api_key)


@router.post("/api-keys/{key_id}/rotate", response_model=APIKeyRotateResponse)
async def rotate_api_key(
    current_user = Depends(get_current_user),
    key_id: int = Field(..., description="API Key ID to rotate"),
    db: Session = Depends(get_db),
):
    """
    Rotate an API key, creating a new one and deactivating the old.

    The old key is immediately deactivated. The new plaintext key is shown once.

    Path Parameters:
    - key_id: The ID of the key to rotate
    """
    from app.api_key_service import APIKeyService
    from app.user_profiles import APIKey

    # Verify key ownership
    api_key = db.query(APIKey).filter(
        APIKey.id == key_id,
        APIKey.user_id == current_user.id
    ).first()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )

    try:
        plaintext_key, new_key = APIKeyService.rotate_key(key_id, db)

        log_security_event(
            "api_key_rotated",
            {
                "username": current_user.username,
                "old_key_id": key_id,
                "new_key_id": new_key.id,
            },
            severity="INFO"
        )

        return APIKeyRotateResponse(
            plaintext_key=plaintext_key,
            message="API key rotated successfully. Old key has been deactivated."
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/api-keys/{key_id}/disable", status_code=status.HTTP_200_OK)
async def disable_api_key(
    current_user = Depends(get_current_user),
    key_id: int = Field(..., description="API Key ID to disable"),
    db: Session = Depends(get_db),
):
    """
    Disable an API key without deleting it.

    The key can be re-enabled, but it cannot be used for authentication.

    Path Parameters:
    - key_id: The ID of the key to disable
    """
    from app.api_key_service import APIKeyService
    from app.user_profiles import APIKey

    # Verify key ownership
    api_key = db.query(APIKey).filter(
        APIKey.id == key_id,
        APIKey.user_id == current_user.id
    ).first()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )

    try:
        APIKeyService.disable_key(key_id, db)

        log_security_event(
            "api_key_disabled",
            {
                "username": current_user.username,
                "key_id": key_id,
            },
            severity="INFO"
        )

        return {"message": "API key disabled successfully"}

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_key(
    current_user = Depends(get_current_user),
    key_id: int = Field(..., description="API Key ID to delete"),
    db: Session = Depends(get_db),
):
    """
    Permanently delete an API key.

    This operation is irreversible. The key will no longer be usable.

    Path Parameters:
    - key_id: The ID of the key to delete
    """
    from app.api_key_service import APIKeyService
    from app.user_profiles import APIKey

    # Verify key ownership
    api_key = db.query(APIKey).filter(
        APIKey.id == key_id,
        APIKey.user_id == current_user.id
    ).first()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )

    try:
        APIKeyService.delete_key(key_id, db)

        log_security_event(
            "api_key_deleted",
            {
                "username": current_user.username,
                "key_id": key_id,
            },
            severity="WARNING"
        )

        return None

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/api-keys/{key_id}/stats", response_model=APIKeyStatsResponse)
async def get_api_key_stats(
    current_user = Depends(get_current_user),
    key_id: int = Field(..., description="API Key ID"),
    db: Session = Depends(get_db),
):
    """
    Get usage statistics for an API key.

    Includes request counts, quota usage, and last used information.

    Path Parameters:
    - key_id: The ID of the API key
    """
    from app.api_key_service import APIKeyService
    from app.user_profiles import APIKey

    # Verify key ownership
    api_key = db.query(APIKey).filter(
        APIKey.id == key_id,
        APIKey.user_id == current_user.id
    ).first()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )

    try:
        stats = APIKeyService.get_key_stats(key_id, db)
        return APIKeyStatsResponse(**stats)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
