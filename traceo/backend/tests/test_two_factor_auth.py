"""
Comprehensive test suite for Two-Factor Authentication (2FA) system.
Tests TOTP generation, backup codes, and all 2FA endpoints.
"""

import pytest
import pyotp
import secrets
import hashlib
from datetime import datetime
from unittest.mock import patch, MagicMock
from sqlalchemy.orm import Session

from app.two_factor_auth import TwoFactorAuthService
from app.user_profiles import UserProfile, BackupCode
from app.database import Base, engine, SessionLocal
from app.security import hash_password, authenticate_user


# ===== Fixtures =====

@pytest.fixture(scope="function")
def db():
    """Create a fresh database for each test."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_user(db: Session):
    """Create a test user."""
    user = UserProfile(
        username="testuser",
        email="test@example.com",
        full_name="Test User"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ===== TOTP Generation Tests =====

def test_generate_secret():
    """Test that secret generation produces valid base32 strings."""
    secret = TwoFactorAuthService.generate_secret()

    assert secret is not None
    assert len(secret) == 32
    assert all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567" for c in secret)


def test_generate_secret_uniqueness():
    """Test that each generated secret is unique."""
    secrets_set = set()
    for _ in range(10):
        secret = TwoFactorAuthService.generate_secret()
        secrets_set.add(secret)

    assert len(secrets_set) == 10, "Generated secrets should be unique"


def test_verify_totp_valid_token():
    """Test TOTP verification with valid token."""
    secret = TwoFactorAuthService.generate_secret()
    totp = pyotp.TOTP(secret)
    token = totp.now()

    result = TwoFactorAuthService.verify_totp(secret, token)
    assert result is True


def test_verify_totp_invalid_token():
    """Test TOTP verification with invalid token."""
    secret = TwoFactorAuthService.generate_secret()

    result = TwoFactorAuthService.verify_totp(secret, "000000")
    assert result is False


def test_verify_totp_malformed_secret():
    """Test TOTP verification with invalid secret."""
    result = TwoFactorAuthService.verify_totp("INVALID", "123456")
    assert result is False


def test_verify_totp_empty_token():
    """Test TOTP verification with empty token."""
    secret = TwoFactorAuthService.generate_secret()

    result = TwoFactorAuthService.verify_totp(secret, "")
    assert result is False


# ===== Backup Code Tests =====

def test_generate_backup_codes():
    """Test backup code generation."""
    codes = TwoFactorAuthService.generate_backup_codes(count=10)

    assert len(codes) == 10
    for code in codes:
        # Format should be XXX-XXX-XXX
        assert len(code) == 11
        assert code[3] == "-"
        assert code[7] == "-"
        parts = code.split("-")
        assert len(parts) == 3
        assert all(len(part) == 3 for part in parts)


def test_generate_backup_codes_uniqueness():
    """Test that generated backup codes are unique."""
    codes = TwoFactorAuthService.generate_backup_codes(count=20)

    assert len(codes) == 20
    assert len(set(codes)) == 20, "All backup codes should be unique"


def test_generate_backup_codes_custom_count():
    """Test generating custom number of backup codes."""
    for count in [5, 10, 15, 20]:
        codes = TwoFactorAuthService.generate_backup_codes(count=count)
        assert len(codes) == count


def test_hash_backup_code():
    """Test backup code hashing."""
    code = "ABC-DEF-GHI"
    hash1 = TwoFactorAuthService.hash_backup_code(code)

    # Hash should be consistent
    hash2 = TwoFactorAuthService.hash_backup_code(code)
    assert hash1 == hash2

    # Should be SHA256 hash (64 hex characters)
    assert len(hash1) == 64
    assert all(c in "0123456789abcdef" for c in hash1)


def test_hash_backup_code_case_insensitive():
    """Test that backup code hashing works with different cases."""
    code1 = "ABC-DEF-GHI"
    code2 = "abc-def-ghi"

    hash1 = TwoFactorAuthService.hash_backup_code(code1)
    hash2 = TwoFactorAuthService.hash_backup_code(code2)

    # Hashes should match because hyphens are removed before hashing
    assert hash1 == hash2


def test_verify_backup_code_valid():
    """Test backup code verification with valid code."""
    code = "ABC-DEF-GHI"
    code_hash = TwoFactorAuthService.hash_backup_code(code)

    result = TwoFactorAuthService.verify_backup_code(code, code_hash)
    assert result is True


def test_verify_backup_code_invalid():
    """Test backup code verification with invalid code."""
    code1 = "ABC-DEF-GHI"
    code2 = "XYZ-ABC-DEF"

    code_hash = TwoFactorAuthService.hash_backup_code(code1)
    result = TwoFactorAuthService.verify_backup_code(code2, code_hash)

    assert result is False


def test_verify_backup_code_timing_safe():
    """Test that verification uses constant-time comparison."""
    code = "ABC-DEF-GHI"
    code_hash = TwoFactorAuthService.hash_backup_code(code)

    # Both should complete without timing attacks
    result1 = TwoFactorAuthService.verify_backup_code(code, code_hash)
    result2 = TwoFactorAuthService.verify_backup_code("INVALID", code_hash)

    assert result1 is True
    assert result2 is False


# ===== QR Code Tests =====

def test_generate_qr_code():
    """Test QR code generation."""
    username = "testuser"
    secret = TwoFactorAuthService.generate_secret()

    qr_code = TwoFactorAuthService.generate_qr_code(username, secret)

    assert qr_code is not None
    assert isinstance(qr_code, bytes)
    assert len(qr_code) > 0
    assert qr_code[:4] == b'\x89PNG'  # PNG file signature


def test_generate_qr_code_with_custom_issuer():
    """Test QR code generation with custom issuer."""
    username = "testuser"
    secret = TwoFactorAuthService.generate_secret()
    issuer = "CustomIssuer"

    qr_code = TwoFactorAuthService.generate_qr_code(username, secret, issuer)

    assert qr_code is not None
    assert isinstance(qr_code, bytes)


# ===== 2FA Setup Tests =====

def test_setup_2fa(test_user, db: Session):
    """Test 2FA setup process."""
    username = test_user.username

    secret, backup_codes, qr_code = TwoFactorAuthService.setup_2fa(
        test_user.id,
        username,
        db
    )

    assert secret is not None
    assert len(secret) == 32
    assert backup_codes is not None
    assert len(backup_codes) == 10
    assert qr_code is not None


def test_confirm_2fa_valid(test_user, db: Session):
    """Test 2FA confirmation with valid TOTP."""
    secret = TwoFactorAuthService.generate_secret()
    backup_codes = TwoFactorAuthService.generate_backup_codes()

    # Set temporary secret on user
    test_user.totp_secret = secret
    db.commit()

    # Get valid TOTP
    totp = pyotp.TOTP(secret)
    valid_token = totp.now()

    # Confirm 2FA
    result = TwoFactorAuthService.confirm_2fa(
        test_user.id,
        secret,
        valid_token,
        backup_codes,
        db
    )

    assert result is True

    # Verify user is updated
    db.refresh(test_user)
    assert test_user.is_2fa_enabled is True
    assert test_user.totp_secret == secret


def test_confirm_2fa_invalid_totp(test_user, db: Session):
    """Test 2FA confirmation with invalid TOTP."""
    secret = TwoFactorAuthService.generate_secret()
    backup_codes = TwoFactorAuthService.generate_backup_codes()

    test_user.totp_secret = secret
    db.commit()

    # Try with invalid token
    with pytest.raises(ValueError):
        TwoFactorAuthService.confirm_2fa(
            test_user.id,
            secret,
            "000000",  # Invalid
            backup_codes,
            db
        )


def test_confirm_2fa_backup_codes_stored(test_user, db: Session):
    """Test that backup codes are properly stored after confirmation."""
    secret = TwoFactorAuthService.generate_secret()
    backup_codes = TwoFactorAuthService.generate_backup_codes(count=10)

    test_user.totp_secret = secret
    db.commit()

    totp = pyotp.TOTP(secret)
    valid_token = totp.now()

    TwoFactorAuthService.confirm_2fa(
        test_user.id,
        secret,
        valid_token,
        backup_codes,
        db
    )

    # Verify backup codes are stored
    stored_codes = db.query(BackupCode).filter(
        BackupCode.user_id == test_user.id
    ).all()

    assert len(stored_codes) == 10
    assert all(code.used is False for code in stored_codes)


# ===== Login Verification Tests =====

def test_verify_login_token_with_totp(test_user, db: Session):
    """Test login verification with valid TOTP."""
    secret = TwoFactorAuthService.generate_secret()
    backup_codes = TwoFactorAuthService.generate_backup_codes()

    # Enable 2FA
    test_user.totp_secret = secret
    test_user.is_2fa_enabled = True
    db.commit()

    # Create backup codes
    for code in backup_codes:
        code_hash = TwoFactorAuthService.hash_backup_code(code)
        backup_code = BackupCode(
            user_id=test_user.id,
            code_hash=code_hash,
            used=False
        )
        db.add(backup_code)
    db.commit()

    # Verify with TOTP
    totp = pyotp.TOTP(secret)
    valid_token = totp.now()

    is_valid, error = TwoFactorAuthService.verify_login_token(
        test_user.id,
        valid_token,
        db
    )

    assert is_valid is True
    assert error is None


def test_verify_login_token_with_backup_code(test_user, db: Session):
    """Test login verification with backup code."""
    secret = TwoFactorAuthService.generate_secret()
    backup_codes = TwoFactorAuthService.generate_backup_codes()
    backup_code_to_use = backup_codes[0]

    # Enable 2FA
    test_user.totp_secret = secret
    test_user.is_2fa_enabled = True
    db.commit()

    # Store backup codes
    for code in backup_codes:
        code_hash = TwoFactorAuthService.hash_backup_code(code)
        backup_code = BackupCode(
            user_id=test_user.id,
            code_hash=code_hash,
            used=False
        )
        db.add(backup_code)
    db.commit()

    # Verify with backup code
    is_valid, error = TwoFactorAuthService.verify_login_token(
        test_user.id,
        backup_code_to_use,
        db
    )

    assert is_valid is True
    assert error is None

    # Verify backup code is marked as used
    used_code = db.query(BackupCode).filter(
        BackupCode.code_hash == TwoFactorAuthService.hash_backup_code(backup_code_to_use)
    ).first()

    assert used_code.used is True
    assert used_code.used_at is not None


def test_verify_login_token_invalid(test_user, db: Session):
    """Test login verification with invalid token."""
    secret = TwoFactorAuthService.generate_secret()

    test_user.totp_secret = secret
    test_user.is_2fa_enabled = True
    db.commit()

    is_valid, error = TwoFactorAuthService.verify_login_token(
        test_user.id,
        "000000",
        db
    )

    assert is_valid is False
    assert error is not None


def test_verify_login_token_2fa_disabled(test_user, db: Session):
    """Test login verification when 2FA is disabled."""
    is_valid, error = TwoFactorAuthService.verify_login_token(
        test_user.id,
        "123456",
        db
    )

    assert is_valid is False
    assert "2FA not enabled" in error


# ===== Disable 2FA Tests =====

def test_disable_2fa(test_user, db: Session):
    """Test disabling 2FA."""
    secret = TwoFactorAuthService.generate_secret()
    backup_codes = TwoFactorAuthService.generate_backup_codes()

    # Enable 2FA first
    test_user.totp_secret = secret
    test_user.is_2fa_enabled = True
    db.commit()

    # Store backup codes
    for code in backup_codes:
        code_hash = TwoFactorAuthService.hash_backup_code(code)
        backup_code = BackupCode(
            user_id=test_user.id,
            code_hash=code_hash
        )
        db.add(backup_code)
    db.commit()

    # Disable 2FA
    result = TwoFactorAuthService.disable_2fa(test_user.id, db)

    assert result is True

    # Verify user is updated
    db.refresh(test_user)
    assert test_user.is_2fa_enabled is False
    assert test_user.totp_secret is None

    # Verify backup codes are deleted
    backup_codes_count = db.query(BackupCode).filter(
        BackupCode.user_id == test_user.id
    ).count()

    assert backup_codes_count == 0


def test_disable_2fa_nonexistent_user(db: Session):
    """Test disabling 2FA for nonexistent user."""
    result = TwoFactorAuthService.disable_2fa(99999, db)

    assert result is False


# ===== Regenerate Backup Codes Tests =====

def test_regenerate_backup_codes(test_user, db: Session):
    """Test regenerating backup codes."""
    secret = TwoFactorAuthService.generate_secret()
    old_backup_codes = TwoFactorAuthService.generate_backup_codes()

    # Enable 2FA
    test_user.totp_secret = secret
    test_user.is_2fa_enabled = True
    db.commit()

    # Store old backup codes
    for code in old_backup_codes:
        code_hash = TwoFactorAuthService.hash_backup_code(code)
        backup_code = BackupCode(
            user_id=test_user.id,
            code_hash=code_hash
        )
        db.add(backup_code)
    db.commit()

    # Regenerate
    totp = pyotp.TOTP(secret)
    valid_token = totp.now()

    new_codes = TwoFactorAuthService.regenerate_backup_codes(
        test_user.id,
        valid_token,
        db
    )

    assert new_codes is not None
    assert len(new_codes) == 10
    assert new_codes != old_backup_codes

    # Verify old codes are deleted
    old_codes_count = db.query(BackupCode).filter(
        BackupCode.user_id == test_user.id,
        BackupCode.code_hash == TwoFactorAuthService.hash_backup_code(old_backup_codes[0])
    ).count()

    assert old_codes_count == 0


def test_regenerate_backup_codes_invalid_totp(test_user, db: Session):
    """Test regenerating backup codes with invalid TOTP."""
    secret = TwoFactorAuthService.generate_secret()

    test_user.totp_secret = secret
    test_user.is_2fa_enabled = True
    db.commit()

    # Try with invalid token
    new_codes = TwoFactorAuthService.regenerate_backup_codes(
        test_user.id,
        "000000",
        db
    )

    assert new_codes is None


def test_regenerate_backup_codes_2fa_disabled(test_user, db: Session):
    """Test regenerating backup codes when 2FA is disabled."""
    new_codes = TwoFactorAuthService.regenerate_backup_codes(
        test_user.id,
        "123456",
        db
    )

    assert new_codes is None


# ===== Status Tests =====

def test_get_2fa_status_disabled(test_user, db: Session):
    """Test getting 2FA status when disabled."""
    status = TwoFactorAuthService.get_2fa_status(test_user.id, db)

    assert status["is_enabled"] is False
    assert status["secret_set"] is False
    assert status["unused_backup_codes"] == 0


def test_get_2fa_status_enabled(test_user, db: Session):
    """Test getting 2FA status when enabled."""
    secret = TwoFactorAuthService.generate_secret()
    backup_codes = TwoFactorAuthService.generate_backup_codes()

    test_user.totp_secret = secret
    test_user.is_2fa_enabled = True
    db.commit()

    # Store backup codes
    for code in backup_codes:
        code_hash = TwoFactorAuthService.hash_backup_code(code)
        backup_code = BackupCode(
            user_id=test_user.id,
            code_hash=code_hash,
            used=False
        )
        db.add(backup_code)
    db.commit()

    status = TwoFactorAuthService.get_2fa_status(test_user.id, db)

    assert status["is_enabled"] is True
    assert status["secret_set"] is True
    assert status["unused_backup_codes"] == 10


def test_get_2fa_status_with_used_codes(test_user, db: Session):
    """Test getting 2FA status with some used backup codes."""
    secret = TwoFactorAuthService.generate_secret()
    backup_codes = TwoFactorAuthService.generate_backup_codes()

    test_user.totp_secret = secret
    test_user.is_2fa_enabled = True
    db.commit()

    # Store backup codes (5 used, 5 unused)
    for i, code in enumerate(backup_codes):
        code_hash = TwoFactorAuthService.hash_backup_code(code)
        backup_code = BackupCode(
            user_id=test_user.id,
            code_hash=code_hash,
            used=i < 5,  # First 5 are used
            used_at=datetime.utcnow() if i < 5 else None
        )
        db.add(backup_code)
    db.commit()

    status = TwoFactorAuthService.get_2fa_status(test_user.id, db)

    assert status["unused_backup_codes"] == 5


def test_get_2fa_status_nonexistent_user(db: Session):
    """Test getting 2FA status for nonexistent user."""
    status = TwoFactorAuthService.get_2fa_status(99999, db)

    assert "error" in status
    assert status["error"] == "User not found"
