"""
Two-Factor Authentication (2FA) Service for Traceo.
Implements TOTP (Time-based One-Time Password) and backup codes for enhanced security.
"""

import secrets
import hashlib
import pyotp
import qrcode
from io import BytesIO
from datetime import datetime, timedelta
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from loguru import logger

from app.user_profiles import UserProfile, BackupCode


class TwoFactorAuthService:
    """Service for managing two-factor authentication operations."""

    # Rate limiting for TOTP verification attempts
    MAX_ATTEMPTS = 5
    LOCKOUT_DURATION = 15 * 60  # 15 minutes in seconds

    @staticmethod
    def generate_secret() -> str:
        """
        Generate a new TOTP secret.

        Returns:
            str: Base32-encoded TOTP secret (32 characters)
        """
        return pyotp.random_base32()

    @staticmethod
    def generate_qr_code(username: str, secret: str, issuer_name: str = "Traceo") -> bytes:
        """
        Generate QR code for TOTP secret.

        Args:
            username: User's username
            secret: TOTP secret
            issuer_name: Issuer name (shown in authenticator apps)

        Returns:
            bytes: QR code image in PNG format
        """
        totp = pyotp.TOTP(secret)
        uri = totp.provisioning_uri(
            name=username,
            issuer_name=issuer_name
        )

        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(uri)
        qr.make(fit=True)

        # Convert to PNG
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)

        return buffer.getvalue()

    @staticmethod
    def verify_totp(secret: str, token: str, valid_window: int = 1) -> bool:
        """
        Verify a TOTP token.

        Args:
            secret: TOTP secret
            token: 6-digit code from authenticator app
            valid_window: Number of time windows to check (default 1 for ±30 seconds)

        Returns:
            bool: True if token is valid, False otherwise
        """
        try:
            totp = pyotp.TOTP(secret)
            # valid_window allows for some clock skew
            return totp.verify(token, valid_window=valid_window)
        except Exception as e:
            logger.warning(f"TOTP verification failed: {str(e)}")
            return False

    @staticmethod
    def generate_backup_codes(count: int = 10) -> List[str]:
        """
        Generate backup codes for account recovery.

        Args:
            count: Number of codes to generate (default 10)

        Returns:
            list[str]: List of backup codes in format XXX-XXX-XXX
        """
        codes = []
        for _ in range(count):
            # Generate 9 random characters and format as XXX-XXX-XXX
            code = secrets.token_urlsafe(9)[:9].upper()
            formatted_code = f"{code[:3]}-{code[3:6]}-{code[6:9]}"
            codes.append(formatted_code)
        return codes

    @staticmethod
    def hash_backup_code(code: str) -> str:
        """
        Hash a backup code for secure storage.

        Args:
            code: Raw backup code

        Returns:
            str: SHA256 hash of the code
        """
        # Remove hyphens for hashing
        clean_code = code.replace("-", "")
        return hashlib.sha256(clean_code.encode()).hexdigest()

    @staticmethod
    def verify_backup_code(code: str, stored_hash: str) -> bool:
        """
        Verify a backup code against its stored hash.

        Args:
            code: Backup code to verify
            stored_hash: Stored hash to compare against

        Returns:
            bool: True if code matches hash
        """
        code_hash = TwoFactorAuthService.hash_backup_code(code)
        # Use constant-time comparison to prevent timing attacks
        return secrets.compare_digest(code_hash, stored_hash)

    @staticmethod
    def setup_2fa(
        user_id: int,
        username: str,
        db: Session
    ) -> Tuple[str, List[str], bytes]:
        """
        Set up 2FA for a user.

        Args:
            user_id: User ID
            username: Username
            db: Database session

        Returns:
            tuple: (secret, backup_codes, qr_code_bytes)
        """
        # Generate secret and backup codes
        secret = TwoFactorAuthService.generate_secret()
        backup_codes = TwoFactorAuthService.generate_backup_codes()

        # Generate QR code
        qr_code = TwoFactorAuthService.generate_qr_code(username, secret)

        logger.info(f"Generated 2FA setup for user {user_id}")

        return secret, backup_codes, qr_code

    @staticmethod
    def confirm_2fa(
        user_id: int,
        secret: str,
        totp_token: str,
        backup_codes: List[str],
        db: Session
    ) -> bool:
        """
        Confirm and enable 2FA for a user.

        Args:
            user_id: User ID
            secret: TOTP secret
            totp_token: TOTP token to verify (must be valid)
            backup_codes: List of backup codes to save
            db: Database session

        Returns:
            bool: True if 2FA was successfully enabled

        Raises:
            ValueError: If TOTP verification fails
        """
        # Verify TOTP token first
        if not TwoFactorAuthService.verify_totp(secret, totp_token):
            raise ValueError("Invalid TOTP token")

        # Get user
        user = db.query(UserProfile).filter(UserProfile.id == user_id).first()
        if not user:
            raise ValueError("User not found")

        # Delete any existing backup codes
        db.query(BackupCode).filter(BackupCode.user_id == user_id).delete()

        # Create new backup codes
        for code in backup_codes:
            code_hash = TwoFactorAuthService.hash_backup_code(code)
            backup_code_obj = BackupCode(
                user_id=user_id,
                code_hash=code_hash,
                used=False
            )
            db.add(backup_code_obj)

        # Update user
        user.totp_secret = secret
        user.is_2fa_enabled = True
        user.updated_at = datetime.utcnow()

        db.commit()
        logger.info(f"2FA enabled for user {user_id}")

        return True

    @staticmethod
    def verify_login_token(
        user_id: int,
        token: str,
        db: Session
    ) -> Tuple[bool, Optional[str]]:
        """
        Verify a login token (TOTP or backup code).

        Args:
            user_id: User ID
            token: TOTP token or backup code
            db: Database session

        Returns:
            tuple: (is_valid, error_message)
                - If valid TOTP: (True, None)
                - If valid backup code: (True, None)
                - If invalid: (False, error_message)
        """
        user = db.query(UserProfile).filter(UserProfile.id == user_id).first()
        if not user or not user.is_2fa_enabled:
            return False, "2FA not enabled for this user"

        # Try TOTP verification first
        if user.totp_secret:
            if TwoFactorAuthService.verify_totp(user.totp_secret, token):
                logger.info(f"User {user_id} verified with TOTP")
                return True, None

        # Try backup code verification
        clean_token = token.replace("-", "").replace(" ", "")
        backup_code = db.query(BackupCode).filter(
            BackupCode.user_id == user_id,
            BackupCode.used == False
        ).first()

        if backup_code:
            # Verify against backup code
            if TwoFactorAuthService.verify_backup_code(clean_token, backup_code.code_hash):
                # Mark backup code as used
                backup_code.used = True
                backup_code.used_at = datetime.utcnow()
                db.commit()

                logger.info(f"User {user_id} verified with backup code")
                return True, None

        # Check if we have unused backup codes
        unused_codes = db.query(BackupCode).filter(
            BackupCode.user_id == user_id,
            BackupCode.used == False
        ).count()

        if unused_codes == 0:
            return False, "No valid backup codes remaining. Generate new backup codes."

        return False, "Invalid TOTP token or backup code"

    @staticmethod
    def disable_2fa(user_id: int, db: Session) -> bool:
        """
        Disable 2FA for a user.

        Args:
            user_id: User ID
            db: Database session

        Returns:
            bool: True if disabled successfully
        """
        user = db.query(UserProfile).filter(UserProfile.id == user_id).first()
        if not user:
            return False

        # Clear 2FA settings
        user.totp_secret = None
        user.is_2fa_enabled = False
        user.backup_codes_used = []
        user.updated_at = datetime.utcnow()

        # Delete all backup codes
        db.query(BackupCode).filter(BackupCode.user_id == user_id).delete()

        db.commit()
        logger.info(f"2FA disabled for user {user_id}")

        return True

    @staticmethod
    def regenerate_backup_codes(
        user_id: int,
        totp_token: str,
        db: Session
    ) -> Optional[List[str]]:
        """
        Regenerate backup codes for a user (requires 2FA verification).

        Args:
            user_id: User ID
            totp_token: TOTP token for verification
            db: Database session

        Returns:
            list[str]: New backup codes if successful, None otherwise
        """
        user = db.query(UserProfile).filter(UserProfile.id == user_id).first()
        if not user or not user.is_2fa_enabled:
            return None

        # Verify TOTP first
        if not user.totp_secret or not TwoFactorAuthService.verify_totp(user.totp_secret, totp_token):
            return None

        # Generate new backup codes
        new_codes = TwoFactorAuthService.generate_backup_codes()

        # Delete old codes
        db.query(BackupCode).filter(BackupCode.user_id == user_id).delete()

        # Store new codes
        for code in new_codes:
            code_hash = TwoFactorAuthService.hash_backup_code(code)
            backup_code = BackupCode(
                user_id=user_id,
                code_hash=code_hash,
                used=False
            )
            db.add(backup_code)

        db.commit()
        logger.info(f"Backup codes regenerated for user {user_id}")

        return new_codes

    @staticmethod
    def get_2fa_status(user_id: int, db: Session) -> dict:
        """
        Get 2FA status for a user.

        Args:
            user_id: User ID
            db: Database session

        Returns:
            dict: Status information including:
                - is_enabled: Whether 2FA is enabled
                - unused_backup_codes: Number of unused backup codes
                - secret_set: Whether TOTP secret is configured
        """
        user = db.query(UserProfile).filter(UserProfile.id == user_id).first()
        if not user:
            return {"error": "User not found"}

        unused_codes = db.query(BackupCode).filter(
            BackupCode.user_id == user_id,
            BackupCode.used == False
        ).count()

        return {
            "is_enabled": user.is_2fa_enabled,
            "secret_set": bool(user.totp_secret),
            "unused_backup_codes": unused_codes,
            "last_updated": user.updated_at.isoformat() if user.updated_at else None
        }
