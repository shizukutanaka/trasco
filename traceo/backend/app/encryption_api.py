"""
Encryption Management API endpoints for Traceo - Phase 7C.

Provides endpoints for:
- Key management and rotation
- Encryption key configuration
- Encryption status monitoring
- Data encryption/decryption operations (admin)
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, status, Depends, Field
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import get_current_user, log_security_event
from app.encryption_service import EncryptionService, EncryptionKeyManager
from app.user_profiles import EncryptionKey, EncryptedField


router = APIRouter(prefix="/admin/encryption", tags=["encryption management"])


# ===== Pydantic Models =====

class EncryptionKeyResponse(BaseModel):
    """Encryption key response"""
    version: int
    status: str
    description: Optional[str] = None
    created_at: str
    created_by: str
    deactivated_at: Optional[str] = None
    fields_encrypted: int

    class Config:
        from_attributes = True


class EncryptionKeysListResponse(BaseModel):
    """List of encryption keys"""
    total_keys: int
    active_count: int
    inactive_count: int
    latest_version: int
    keys: list[EncryptionKeyResponse]


class EncryptionInfoResponse(BaseModel):
    """Encryption system information"""
    algorithm: str
    key_size: int
    nonce_size: int
    tag_size: int
    hash_algorithm: str
    mode: str
    key_derivation: str
    standards: list[str]


class KeyRotationRequest(BaseModel):
    """Request to rotate encryption keys"""
    force: bool = Field(False, description="Force rotation even if current rotation in progress")


class KeyRotationResponse(BaseModel):
    """Key rotation operation result"""
    status: str
    old_version: int
    new_version: int
    fields_rotated: int
    errors: int
    elapsed_seconds: float
    message: str


class EncryptFieldRequest(BaseModel):
    """Request to encrypt a field"""
    plaintext: str = Field(..., description="Value to encrypt")
    field_name: str = Field(..., description="Field identifier (e.g., 'email', 'phone')")
    additional_data: Optional[str] = Field(None, description="Additional authenticated data")


class EncryptFieldResponse(BaseModel):
    """Encrypted field response"""
    encrypted: str
    field_name: str
    key_version: int
    algorithm: str


class DecryptFieldRequest(BaseModel):
    """Request to decrypt a field"""
    encrypted: str = Field(..., description="Base64-encoded ciphertext")
    field_name: str = Field(..., description="Field identifier")
    additional_data: Optional[str] = Field(None, description="Additional authenticated data")


class DecryptFieldResponse(BaseModel):
    """Decrypted field response"""
    plaintext: str
    field_name: str
    key_version: int


class OperationResultResponse(BaseModel):
    """Operation result"""
    status: str
    message: str
    timestamp: str


# ===== Encryption Information Routes =====

@router.get("/info", response_model=EncryptionInfoResponse)
async def get_encryption_info(
    current_user = Depends(get_current_user),
):
    """
    Get encryption system configuration information.

    Returns encryption algorithm details, key sizes, and standards compliance.
    """
    try:
        info = EncryptionService.get_encryption_info()

        log_security_event(
            "encryption_info_requested",
            {"username": current_user.username},
            severity="INFO",
        )

        return EncryptionInfoResponse(**info)

    except Exception as e:
        log_security_event(
            "encryption_info_error",
            {"username": current_user.username, "error": str(e)},
            severity="ERROR",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve encryption info",
        )


# ===== Key Management Routes =====

@router.get("/keys", response_model=EncryptionKeysListResponse)
async def list_encryption_keys(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List all encryption keys and their status.

    Returns list of key versions, statuses, and metadata.
    """
    try:
        stats = EncryptionKeyManager.get_key_stats(db)

        log_security_event(
            "encryption_keys_listed",
            {"username": current_user.username},
            severity="INFO",
        )

        return EncryptionKeysListResponse(
            total_keys=stats["total_keys"],
            active_count=stats["by_status"].get("active", 0),
            inactive_count=stats["by_status"].get("inactive", 0),
            latest_version=stats["latest_version"],
            keys=[EncryptionKeyResponse(**key) for key in stats["keys"]],
        )

    except Exception as e:
        log_security_event(
            "encryption_keys_list_error",
            {"username": current_user.username, "error": str(e)},
            severity="ERROR",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list encryption keys",
        )


@router.get("/keys/{version}", response_model=EncryptionKeyResponse)
async def get_encryption_key(
    version: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get details about a specific encryption key version.
    """
    try:
        key = db.query(EncryptionKey).filter(
            EncryptionKey.version == version
        ).first()

        if not key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Encryption key version {version} not found",
            )

        log_security_event(
            "encryption_key_viewed",
            {"username": current_user.username, "version": version},
            severity="INFO",
        )

        return EncryptionKeyResponse.from_orm(key)

    except HTTPException:
        raise
    except Exception as e:
        log_security_event(
            "encryption_key_view_error",
            {"username": current_user.username, "error": str(e)},
            severity="ERROR",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve encryption key",
        )


@router.post("/keys/rotate", response_model=KeyRotationResponse)
async def rotate_encryption_keys(
    request: KeyRotationRequest,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Rotate encryption keys for all encrypted fields.

    This is a zero-downtime operation that:
    1. Creates new key version
    2. Re-encrypts all fields with new key
    3. Deactivates old key

    Parameters:
    - force: Override any ongoing rotation (use with caution)
    """
    try:
        # Get current active key version
        try:
            current_version = EncryptionKeyManager.get_active_key_version(db)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No active encryption key found",
            )

        new_version = current_version + 1

        # Create new key record
        new_key = EncryptionKeyManager.create_encryption_key(
            db,
            version=new_version,
            status="active",
            description=f"Rotated from version {current_version}",
        )

        # Initialize encryption service
        encryption_svc = EncryptionService()

        # Perform key rotation
        result = encryption_svc.rotate_keys(db, current_version, new_version)

        # Deactivate old key
        EncryptionKeyManager.deactivate_key(db, current_version)

        log_security_event(
            "encryption_key_rotation_initiated",
            {
                "username": current_user.username,
                "old_version": current_version,
                "new_version": new_version,
                "fields_rotated": result["fields_rotated"],
            },
            severity="WARNING",  # Key rotation is a significant event
        )

        return KeyRotationResponse(
            status="success",
            old_version=current_version,
            new_version=new_version,
            fields_rotated=result["fields_rotated"],
            errors=result["errors"],
            elapsed_seconds=result["elapsed_seconds"],
            message=f"Successfully rotated {result['fields_rotated']} fields "
                    f"from key v{current_version} to v{new_version}",
        )

    except HTTPException:
        raise
    except Exception as e:
        log_security_event(
            "encryption_key_rotation_failed",
            {"username": current_user.username, "error": str(e)},
            severity="ERROR",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Key rotation failed: {str(e)}",
        )


# ===== Field Encryption Routes =====

@router.post("/encrypt", response_model=EncryptFieldResponse)
async def encrypt_field(
    request: EncryptFieldRequest,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Encrypt a field value.

    Used for encrypting sensitive data before storage.
    This endpoint is primarily for testing and administrative use.

    Parameters:
    - plaintext: Value to encrypt
    - field_name: Field identifier (e.g., 'email', 'phone')
    - additional_data: Optional authenticated data (verified but not encrypted)
    """
    try:
        encryption_svc = EncryptionService()
        active_version = EncryptionKeyManager.get_active_key_version(db)

        encrypted = encryption_svc.encrypt_field(
            request.plaintext,
            request.field_name,
            active_version,
            request.additional_data.encode() if request.additional_data else None,
        )

        log_security_event(
            "encryption_operation",
            {
                "username": current_user.username,
                "operation": "encrypt",
                "field_name": request.field_name,
            },
            severity="INFO",
        )

        return EncryptFieldResponse(
            encrypted=encrypted,
            field_name=request.field_name,
            key_version=active_version,
            algorithm=EncryptionService.ALGORITHM,
        )

    except Exception as e:
        log_security_event(
            "encryption_operation_failed",
            {
                "username": current_user.username,
                "operation": "encrypt",
                "error": str(e),
            },
            severity="ERROR",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Encryption failed: {str(e)}",
        )


@router.post("/decrypt", response_model=DecryptFieldResponse)
async def decrypt_field(
    request: DecryptFieldRequest,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Decrypt a field value.

    Used for decrypting sensitive data for viewing/modification.
    This endpoint logs all decryption operations for audit trail.

    Parameters:
    - encrypted: Base64-encoded ciphertext
    - field_name: Field identifier
    - additional_data: Optional authenticated data (must match encryption)
    """
    try:
        encryption_svc = EncryptionService()

        plaintext = encryption_svc.decrypt_field(
            request.encrypted,
            request.field_name,
            request.additional_data.encode() if request.additional_data else None,
        )

        # Extract key version from ciphertext header
        from base64 import b64decode
        import struct
        encrypted_bytes = b64decode(request.encrypted)
        key_version = struct.unpack(">B", encrypted_bytes[0:1])[0]

        log_security_event(
            "encryption_operation",
            {
                "username": current_user.username,
                "operation": "decrypt",
                "field_name": request.field_name,
                "key_version": key_version,
            },
            severity="WARNING",  # Decryption is logged as warning for audit
        )

        return DecryptFieldResponse(
            plaintext=plaintext,
            field_name=request.field_name,
            key_version=key_version,
        )

    except Exception as e:
        log_security_event(
            "encryption_operation_failed",
            {
                "username": current_user.username,
                "operation": "decrypt",
                "field_name": request.field_name,
                "error": str(e),
            },
            severity="ERROR",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Decryption failed: {str(e)}",
        )


# ===== Key Management Routes =====

@router.post("/keys/create", response_model=EncryptionKeyResponse)
async def create_encryption_key(
    version: int = Field(..., gt=0, description="Key version number"),
    description: Optional[str] = Field(None, description="Key description"),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a new encryption key (typically done during initialization).

    Note: This endpoint is for administrative setup. Normal key rotation
    should use the /rotate endpoint.
    """
    try:
        # Check if version already exists
        existing = db.query(EncryptionKey).filter(
            EncryptionKey.version == version
        ).first()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Key version {version} already exists",
            )

        key = EncryptionKeyManager.create_encryption_key(
            db,
            version=version,
            status="active",
            description=description,
        )

        log_security_event(
            "encryption_key_created",
            {
                "username": current_user.username,
                "version": version,
                "description": description,
            },
            severity="WARNING",
        )

        return EncryptionKeyResponse.from_orm(key)

    except HTTPException:
        raise
    except Exception as e:
        log_security_event(
            "encryption_key_creation_failed",
            {"username": current_user.username, "error": str(e)},
            severity="ERROR",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create encryption key",
        )


# ===== Health Check Routes =====

@router.get("/health")
async def encryption_health_check(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Check encryption system health.

    Returns:
    - Master key availability
    - Active key version
    - Encrypted field count
    - Last rotation date
    """
    try:
        active_version = EncryptionKeyManager.get_active_key_version(db)
        key_count = db.query(EncryptedField).count()

        active_key = db.query(EncryptionKey).filter(
            EncryptionKey.version == active_version
        ).first()

        return {
            "status": "healthy",
            "encryption_system": "operational",
            "active_key_version": active_version,
            "encrypted_fields": key_count,
            "last_key_rotation": active_key.last_rotation_at.isoformat()
            if active_key and active_key.last_rotation_at
            else None,
            "algorithm": EncryptionService.ALGORITHM,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Encryption system not initialized",
        )
    except Exception as e:
        log_security_event(
            "encryption_health_check_failed",
            {"username": current_user.username, "error": str(e)},
            severity="ERROR",
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Encryption health check failed",
        )
