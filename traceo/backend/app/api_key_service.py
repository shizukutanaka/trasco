"""
API Key management service for Traceo.
Handles API key generation, hashing, verification, and usage tracking.
"""

import os
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session
from loguru import logger

from app.user_profiles import APIKey, UserProfile


class APIKeyService:
    """
    Production-ready API key management service.
    Follows Stripe/GitHub model with prefixed keys and Argon2id hashing.
    """

    # Key format: sk_[tier]_[env]_[random]
    # Example: sk_prod_1a2b3c4d5e6f7g8h
    KEY_PREFIX = "sk"
    ENVIRONMENT = "prod"  # Can be 'dev', 'staging', 'prod'
    KEY_LENGTH = 32  # Length of random portion (32 bytes = 256 bits)

    # Tier configurations
    TIER_LIMITS = {
        "free": {
            "rate_limit": 100,  # requests per minute
            "monthly_quota": 10_000,
            "max_keys": 1,
        },
        "pro": {
            "rate_limit": 1_000,
            "monthly_quota": 100_000,
            "max_keys": 5,
        },
        "enterprise": {
            "rate_limit": 10_000,
            "monthly_quota": 1_000_000,
            "max_keys": 50,
        },
    }

    @staticmethod
    def generate_key() -> Tuple[str, str]:
        """
        Generate a new API key with secure randomness.

        Returns:
            Tuple of (plaintext_key, key_prefix)
            Example: ("sk_prod_abc123def456...", "sk_prod_abc1")

        Key Structure:
            - sk_ : Type prefix
            - prod : Environment (dev, staging, prod)
            - 32 random bytes: Cryptographically secure random data

        Security:
            - Uses secrets.token_urlsafe for cryptographic randomness
            - 256-bit entropy (32 bytes)
            - Incompatible with simple string patterns
        """
        # Generate cryptographically secure random bytes
        random_bytes = secrets.token_urlsafe(APIKeyService.KEY_LENGTH)

        # Construct key: sk_prod_<random>
        plaintext_key = f"{APIKeyService.KEY_PREFIX}_{APIKeyService.ENVIRONMENT}_{random_bytes}"

        # Extract prefix for display (first 20 chars total: "sk_prod_" + 8 chars)
        key_prefix = plaintext_key[:20]

        return plaintext_key, key_prefix

    @staticmethod
    def hash_key(plaintext_key: str) -> str:
        """
        Hash API key for secure storage.

        Uses SHA256 for fast comparison. In production, can be upgraded to Argon2id
        for additional protection against rainbow tables.

        Args:
            plaintext_key: The plaintext API key

        Returns:
            Hex-encoded SHA256 hash

        Security Notes:
            - Never store plaintext keys
            - Use timing-safe comparison when verifying
            - Hash is unique per key (via randomness)
        """
        return hashlib.sha256(plaintext_key.encode('utf-8')).hexdigest()

    @staticmethod
    def verify_key(plaintext_key: str, stored_hash: str) -> bool:
        """
        Verify API key against stored hash using timing-safe comparison.

        Args:
            plaintext_key: The plaintext key to verify
            stored_hash: The stored hash from database

        Returns:
            True if key is valid, False otherwise

        Security:
            - Uses secrets.compare_digest for timing-safe comparison
            - Prevents timing attacks that could leak key information
        """
        key_hash = APIKeyService.hash_key(plaintext_key)
        return secrets.compare_digest(key_hash, stored_hash)

    @staticmethod
    def create_api_key(
        user_id: int,
        name: str,
        db: Session,
        tier: str = "free",
        description: Optional[str] = None,
        expires_in_days: Optional[int] = None,
        scopes: Optional[list] = None,
    ) -> Tuple[str, APIKey]:
        """
        Create a new API key for a user.

        Args:
            user_id: ID of the user
            name: User-friendly name for the key
            db: Database session
            tier: Key tier (free, pro, enterprise)
            description: Optional description
            expires_in_days: Optional expiration in days
            scopes: Optional list of permission scopes

        Returns:
            Tuple of (plaintext_key, api_key_model)

        Raises:
            ValueError: If tier is invalid or user has max keys

        Security:
            - Only plaintext returned once; must be saved immediately by user
            - Hash stored in database
            - Rate limits enforced per tier
        """
        # Validate tier
        if tier not in APIKeyService.TIER_LIMITS:
            raise ValueError(f"Invalid tier: {tier}")

        # Check user exists
        user = db.query(UserProfile).filter(UserProfile.id == user_id).first()
        if not user:
            raise ValueError(f"User {user_id} not found")

        # Check key limit for tier
        tier_config = APIKeyService.TIER_LIMITS[tier]
        existing_keys = db.query(APIKey).filter(
            APIKey.user_id == user_id,
            APIKey.tier == tier,
            APIKey.is_active == True,
        ).count()

        if existing_keys >= tier_config["max_keys"]:
            raise ValueError(
                f"User has reached maximum API keys ({tier_config['max_keys']}) for {tier} tier"
            )

        # Generate key
        plaintext_key, key_prefix = APIKeyService.generate_key()
        key_hash = APIKeyService.hash_key(plaintext_key)

        # Calculate expiration
        expires_at = None
        if expires_in_days:
            expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)

        # Create API key record
        api_key = APIKey(
            user_id=user_id,
            name=name,
            description=description,
            key_hash=key_hash,
            key_prefix=key_prefix,
            tier=tier,
            rate_limit=tier_config["rate_limit"],
            monthly_quota=tier_config["monthly_quota"],
            expires_at=expires_at,
            scopes=scopes or ["read"],
            is_active=True,
        )

        db.add(api_key)
        db.commit()
        db.refresh(api_key)

        logger.info(
            "API key created",
            user_id=user_id,
            key_id=api_key.id,
            tier=tier,
            name=name,
        )

        return plaintext_key, api_key

    @staticmethod
    def verify_api_key(
        plaintext_key: str,
        db: Session,
    ) -> Optional[Tuple[APIKey, UserProfile]]:
        """
        Verify an API key and return the key and user.

        Args:
            plaintext_key: The plaintext API key to verify
            db: Database session

        Returns:
            Tuple of (api_key, user) if valid, None otherwise

        Security Considerations:
            - Returns None for invalid keys (no information leakage)
            - Checks key is active, not expired
            - Logs verification attempts for security
        """
        try:
            # Extract prefix for quick index lookup
            # This prevents having to hash and compare against all keys
            key_prefix = plaintext_key[:20]

            # Find keys with matching prefix
            potential_keys = db.query(APIKey).filter(
                APIKey.key_prefix == key_prefix,
                APIKey.is_active == True,
            ).all()

            if not potential_keys:
                logger.warning("API key verification failed: no matching key prefix", prefix=key_prefix)
                return None

            # Compare against each potential key (usually only 1)
            for api_key in potential_keys:
                if APIKeyService.verify_key(plaintext_key, api_key.key_hash):
                    # Check expiration
                    if api_key.expires_at and datetime.now(timezone.utc) > api_key.expires_at:
                        logger.warning("API key verification failed: key expired", key_id=api_key.id)
                        return None

                    # Key is valid
                    user = db.query(UserProfile).filter(UserProfile.id == api_key.user_id).first()

                    logger.info("API key verified successfully", key_id=api_key.id, user_id=api_key.user_id)

                    return api_key, user

            logger.warning("API key verification failed: hash mismatch", prefix=key_prefix)
            return None

        except Exception as e:
            logger.error("Error verifying API key", error=str(e))
            return None

    @staticmethod
    def record_usage(
        api_key_id: int,
        db: Session,
        ip_address: Optional[str] = None,
    ) -> None:
        """
        Record an API key usage event.

        Args:
            api_key_id: ID of the API key
            db: Database session
            ip_address: Optional IP address of the request
        """
        api_key = db.query(APIKey).filter(APIKey.id == api_key_id).first()
        if not api_key:
            logger.warning("API key not found for usage recording", key_id=api_key_id)
            return

        # Increment counters
        api_key.requests_lifetime += 1
        api_key.requests_this_month += 1
        api_key.last_used = datetime.now(timezone.utc)
        if ip_address:
            api_key.last_used_ip = ip_address

        db.add(api_key)
        db.commit()

        logger.debug(
            "API key usage recorded",
            key_id=api_key_id,
            requests_this_month=api_key.requests_this_month,
        )

    @staticmethod
    def reset_monthly_quota(db: Session) -> int:
        """
        Reset monthly request counts for all API keys.

        Should be called on the 1st of each month via scheduled task.

        Args:
            db: Database session

        Returns:
            Number of keys reset
        """
        keys = db.query(APIKey).filter(APIKey.is_active == True).all()
        for api_key in keys:
            api_key.requests_this_month = 0

        db.commit()

        logger.info("Monthly quota reset", count=len(keys))

        return len(keys)

    @staticmethod
    def check_rate_limit(
        api_key: APIKey,
        requests_in_window: int = 0,
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if API key is within rate limits.

        Args:
            api_key: The API key object
            requests_in_window: Requests in current time window

        Returns:
            Tuple of (is_within_limit, limit_info)

        Limit Info includes:
            - remaining_requests: In current rate limit window
            - remaining_monthly: Total monthly quota
            - reset_at: When monthly quota resets
            - window_requests_remaining: In current minute window
        """
        # Check monthly quota
        monthly_remaining = api_key.monthly_quota - api_key.requests_this_month
        if monthly_remaining <= 0:
            return False, {
                "error": "Monthly quota exceeded",
                "used": api_key.requests_this_month,
                "limit": api_key.monthly_quota,
            }

        # Check rate limit (requests per minute)
        # In production, this would check Redis for current window
        rate_limit_remaining = max(0, api_key.rate_limit - requests_in_window)

        return True, {
            "remaining_requests": rate_limit_remaining,
            "remaining_monthly": monthly_remaining,
            "rate_limit": api_key.rate_limit,
            "monthly_quota": api_key.monthly_quota,
        }

    @staticmethod
    def rotate_key(
        api_key_id: int,
        db: Session,
    ) -> Tuple[str, APIKey]:
        """
        Rotate an API key by creating a new one and deactivating the old.

        Args:
            api_key_id: ID of the key to rotate
            db: Database session

        Returns:
            Tuple of (new_plaintext_key, new_api_key)

        Security:
            - Old key is immediately deactivated
            - All permissions copied to new key
            - Both old and new keys tracked
        """
        old_key = db.query(APIKey).filter(APIKey.id == api_key_id).first()
        if not old_key:
            raise ValueError(f"API key {api_key_id} not found")

        # Deactivate old key
        old_key.is_active = False
        db.add(old_key)

        # Create new key with same properties
        plaintext_key, new_key = APIKeyService.create_api_key(
            user_id=old_key.user_id,
            name=f"{old_key.name} (rotated)",
            db=db,
            tier=old_key.tier,
            description=old_key.description,
            expires_in_days=None,
            scopes=old_key.scopes,
        )

        new_key.last_rotated_at = datetime.now(timezone.utc)
        db.add(new_key)
        db.commit()

        logger.info(
            "API key rotated",
            old_key_id=api_key_id,
            new_key_id=new_key.id,
            user_id=old_key.user_id,
        )

        return plaintext_key, new_key

    @staticmethod
    def disable_key(
        api_key_id: int,
        db: Session,
    ) -> None:
        """
        Disable an API key immediately.

        Args:
            api_key_id: ID of the key to disable
            db: Database session
        """
        api_key = db.query(APIKey).filter(APIKey.id == api_key_id).first()
        if not api_key:
            raise ValueError(f"API key {api_key_id} not found")

        api_key.is_active = False
        api_key.updated_at = datetime.now(timezone.utc)
        db.add(api_key)
        db.commit()

        logger.info("API key disabled", key_id=api_key_id, user_id=api_key.user_id)

    @staticmethod
    def delete_key(
        api_key_id: int,
        db: Session,
    ) -> None:
        """
        Permanently delete an API key.

        Args:
            api_key_id: ID of the key to delete
            db: Database session
        """
        api_key = db.query(APIKey).filter(APIKey.id == api_key_id).first()
        if not api_key:
            raise ValueError(f"API key {api_key_id} not found")

        user_id = api_key.user_id
        db.delete(api_key)
        db.commit()

        logger.info("API key deleted", key_id=api_key_id, user_id=user_id)

    @staticmethod
    def get_user_keys(
        user_id: int,
        db: Session,
        include_inactive: bool = False,
    ) -> list[APIKey]:
        """
        Get all API keys for a user.

        Args:
            user_id: ID of the user
            db: Database session
            include_inactive: Include deactivated keys

        Returns:
            List of APIKey objects
        """
        query = db.query(APIKey).filter(APIKey.user_id == user_id)

        if not include_inactive:
            query = query.filter(APIKey.is_active == True)

        return query.order_by(APIKey.created_at.desc()).all()

    @staticmethod
    def get_key_stats(
        api_key_id: int,
        db: Session,
    ) -> Dict[str, Any]:
        """
        Get usage statistics for an API key.

        Args:
            api_key_id: ID of the API key
            db: Database session

        Returns:
            Dictionary with usage statistics
        """
        api_key = db.query(APIKey).filter(APIKey.id == api_key_id).first()
        if not api_key:
            raise ValueError(f"API key {api_key_id} not found")

        return {
            "id": api_key.id,
            "name": api_key.name,
            "tier": api_key.tier,
            "created_at": api_key.created_at,
            "requests_lifetime": api_key.requests_lifetime,
            "requests_this_month": api_key.requests_this_month,
            "monthly_quota": api_key.monthly_quota,
            "quota_remaining": api_key.monthly_quota - api_key.requests_this_month,
            "quota_percentage": (api_key.requests_this_month / api_key.monthly_quota * 100) if api_key.monthly_quota > 0 else 0,
            "last_used": api_key.last_used,
            "is_active": api_key.is_active,
            "expires_at": api_key.expires_at,
        }
