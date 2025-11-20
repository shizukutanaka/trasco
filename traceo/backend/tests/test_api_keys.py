"""
Comprehensive test suite for API Key Management System.
Tests cover key generation, hashing, verification, usage tracking, and lifecycle management.
"""

import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from app.api_key_service import APIKeyService
from app.user_profiles import UserProfile, APIKey
from app.database import SessionLocal, Base, engine


# ===== Database Setup =====

@pytest.fixture(scope="session")
def db_setup():
    """Set up test database."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    """Database session for each test."""
    connection = engine.connect()
    transaction = connection.begin()
    session = SessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def test_user(db):
    """Create a test user."""
    user = UserProfile(
        id=1,
        username="testuser",
        email="test@example.com",
        full_name="Test User",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ===== Key Generation Tests =====

class TestKeyGeneration:
    """Test API key generation with cryptographic randomness."""

    def test_generate_key_returns_tuple(self):
        """Test that generate_key returns plaintext and prefix."""
        plaintext, prefix = APIKeyService.generate_key()

        assert isinstance(plaintext, str)
        assert isinstance(prefix, str)

    def test_generate_key_format(self):
        """Test that keys follow the correct format: sk_prod_..."""
        plaintext, prefix = APIKeyService.generate_key()

        assert plaintext.startswith("sk_prod_")
        assert prefix == plaintext[:20]
        assert len(plaintext) > 20

    def test_generate_key_uniqueness(self):
        """Test that generated keys are unique."""
        keys = set()
        for _ in range(10):
            plaintext, _ = APIKeyService.generate_key()
            keys.add(plaintext)

        assert len(keys) == 10  # All keys should be unique

    def test_generate_key_entropy(self):
        """Test that keys have sufficient entropy."""
        plaintext, _ = APIKeyService.generate_key()
        # Should be at least 32 bytes of randomness after prefix
        assert len(plaintext) > 20


# ===== Key Hashing Tests =====

class TestKeyHashing:
    """Test API key hashing and verification."""

    def test_hash_key_returns_string(self):
        """Test that hash_key returns a string."""
        plaintext, _ = APIKeyService.generate_key()
        hash_value = APIKeyService.hash_key(plaintext)

        assert isinstance(hash_value, str)

    def test_hash_key_consistency(self):
        """Test that the same key always produces the same hash."""
        plaintext, _ = APIKeyService.generate_key()
        hash1 = APIKeyService.hash_key(plaintext)
        hash2 = APIKeyService.hash_key(plaintext)

        assert hash1 == hash2

    def test_hash_key_uniqueness(self):
        """Test that different keys produce different hashes."""
        key1, _ = APIKeyService.generate_key()
        key2, _ = APIKeyService.generate_key()

        hash1 = APIKeyService.hash_key(key1)
        hash2 = APIKeyService.hash_key(key2)

        assert hash1 != hash2

    def test_verify_key_with_correct_hash(self):
        """Test that verify_key succeeds with correct hash."""
        plaintext, _ = APIKeyService.generate_key()
        hash_value = APIKeyService.hash_key(plaintext)

        assert APIKeyService.verify_key(plaintext, hash_value) is True

    def test_verify_key_with_incorrect_hash(self):
        """Test that verify_key fails with incorrect hash."""
        plaintext, _ = APIKeyService.generate_key()
        wrong_hash = APIKeyService.hash_key("different_key")

        assert APIKeyService.verify_key(plaintext, wrong_hash) is False

    def test_verify_key_timing_safe(self):
        """Test that verify_key uses timing-safe comparison."""
        plaintext, _ = APIKeyService.generate_key()
        hash_value = APIKeyService.hash_key(plaintext)

        # Correct verification
        result1 = APIKeyService.verify_key(plaintext, hash_value)

        # Incorrect verification (timing-safe should take similar time)
        wrong_key = plaintext[:-5] + "WRONG"
        result2 = APIKeyService.verify_key(wrong_key, hash_value)

        assert result1 is True
        assert result2 is False


# ===== Key Creation Tests =====

class TestKeyCreation:
    """Test API key creation and database storage."""

    def test_create_api_key_success(self, test_user, db):
        """Test successful API key creation."""
        plaintext_key, api_key = APIKeyService.create_api_key(
            user_id=test_user.id,
            name="Test Key",
            db=db,
        )

        assert plaintext_key is not None
        assert api_key is not None
        assert api_key.user_id == test_user.id
        assert api_key.name == "Test Key"
        assert api_key.is_active is True
        assert api_key.tier == "free"
        assert api_key.rate_limit == 100

    def test_create_api_key_stores_hash_not_plaintext(self, test_user, db):
        """Test that plaintext key is not stored, only hash."""
        plaintext_key, api_key = APIKeyService.create_api_key(
            user_id=test_user.id,
            name="Test Key",
            db=db,
        )

        # Plaintext should not be stored
        assert plaintext_key not in api_key.key_hash
        # Hash should be different from plaintext
        assert api_key.key_hash != plaintext_key

    def test_create_api_key_with_pro_tier(self, test_user, db):
        """Test API key creation with pro tier."""
        plaintext_key, api_key = APIKeyService.create_api_key(
            user_id=test_user.id,
            name="Pro Key",
            db=db,
            tier="pro",
        )

        assert api_key.tier == "pro"
        assert api_key.rate_limit == 1_000
        assert api_key.monthly_quota == 100_000

    def test_create_api_key_with_enterprise_tier(self, test_user, db):
        """Test API key creation with enterprise tier."""
        plaintext_key, api_key = APIKeyService.create_api_key(
            user_id=test_user.id,
            name="Enterprise Key",
            db=db,
            tier="enterprise",
        )

        assert api_key.tier == "enterprise"
        assert api_key.rate_limit == 10_000
        assert api_key.monthly_quota == 1_000_000

    def test_create_api_key_with_expiration(self, test_user, db):
        """Test API key creation with expiration."""
        plaintext_key, api_key = APIKeyService.create_api_key(
            user_id=test_user.id,
            name="Expiring Key",
            db=db,
            expires_in_days=30,
        )

        assert api_key.expires_at is not None
        # Should expire in approximately 30 days
        delta = (api_key.expires_at - datetime.now(timezone.utc)).days
        assert 29 <= delta <= 31

    def test_create_api_key_with_scopes(self, test_user, db):
        """Test API key creation with specific scopes."""
        scopes = ["read", "write"]
        plaintext_key, api_key = APIKeyService.create_api_key(
            user_id=test_user.id,
            name="Scoped Key",
            db=db,
            scopes=scopes,
        )

        assert api_key.scopes == scopes

    def test_create_api_key_invalid_tier(self, test_user, db):
        """Test API key creation with invalid tier."""
        with pytest.raises(ValueError):
            APIKeyService.create_api_key(
                user_id=test_user.id,
                name="Invalid Key",
                db=db,
                tier="invalid",
            )

    def test_create_api_key_nonexistent_user(self, db):
        """Test API key creation for nonexistent user."""
        with pytest.raises(ValueError):
            APIKeyService.create_api_key(
                user_id=99999,
                name="Key",
                db=db,
            )

    def test_create_api_key_tier_limit(self, test_user, db):
        """Test API key creation respects tier limits."""
        # Free tier allows 1 key
        APIKeyService.create_api_key(
            user_id=test_user.id,
            name="Key 1",
            db=db,
            tier="free",
        )

        # Second key should fail
        with pytest.raises(ValueError, match="reached maximum"):
            APIKeyService.create_api_key(
                user_id=test_user.id,
                name="Key 2",
                db=db,
                tier="free",
            )


# ===== Key Verification Tests =====

class TestKeyVerification:
    """Test API key verification during authentication."""

    def test_verify_api_key_success(self, test_user, db):
        """Test successful API key verification."""
        plaintext_key, _ = APIKeyService.create_api_key(
            user_id=test_user.id,
            name="Test Key",
            db=db,
        )

        result = APIKeyService.verify_api_key(plaintext_key, db)

        assert result is not None
        api_key, user = result
        assert api_key.user_id == test_user.id
        assert user.id == test_user.id

    def test_verify_api_key_invalid_key(self, db):
        """Test verification with invalid key."""
        result = APIKeyService.verify_api_key("sk_prod_invalid_key", db)

        assert result is None

    def test_verify_api_key_inactive_key(self, test_user, db):
        """Test that inactive keys cannot be verified."""
        plaintext_key, api_key = APIKeyService.create_api_key(
            user_id=test_user.id,
            name="Test Key",
            db=db,
        )

        # Deactivate the key
        api_key.is_active = False
        db.add(api_key)
        db.commit()

        result = APIKeyService.verify_api_key(plaintext_key, db)

        assert result is None

    def test_verify_api_key_expired_key(self, test_user, db):
        """Test that expired keys cannot be verified."""
        plaintext_key, api_key = APIKeyService.create_api_key(
            user_id=test_user.id,
            name="Expiring Key",
            db=db,
            expires_in_days=1,
        )

        # Set expiration to past
        api_key.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        db.add(api_key)
        db.commit()

        result = APIKeyService.verify_api_key(plaintext_key, db)

        assert result is None


# ===== Usage Tracking Tests =====

class TestUsageTracking:
    """Test API key usage recording and quota tracking."""

    def test_record_usage_updates_counters(self, test_user, db):
        """Test that usage recording increments counters."""
        plaintext_key, api_key = APIKeyService.create_api_key(
            user_id=test_user.id,
            name="Test Key",
            db=db,
        )

        APIKeyService.record_usage(api_key.id, db, "192.168.1.1")

        # Refresh from database
        api_key = db.query(APIKey).filter(APIKey.id == api_key.id).first()

        assert api_key.requests_lifetime == 1
        assert api_key.requests_this_month == 1
        assert api_key.last_used is not None
        assert api_key.last_used_ip == "192.168.1.1"

    def test_record_usage_increments_multiple_times(self, test_user, db):
        """Test that usage can be recorded multiple times."""
        plaintext_key, api_key = APIKeyService.create_api_key(
            user_id=test_user.id,
            name="Test Key",
            db=db,
        )

        for i in range(5):
            APIKeyService.record_usage(api_key.id, db)

        # Refresh from database
        api_key = db.query(APIKey).filter(APIKey.id == api_key.id).first()

        assert api_key.requests_lifetime == 5
        assert api_key.requests_this_month == 5

    def test_check_rate_limit_within_limit(self, test_user, db):
        """Test rate limit check when within limits."""
        plaintext_key, api_key = APIKeyService.create_api_key(
            user_id=test_user.id,
            name="Test Key",
            db=db,
        )

        is_allowed, info = APIKeyService.check_rate_limit(api_key, requests_in_window=50)

        assert is_allowed is True
        assert info["remaining_requests"] > 0

    def test_check_rate_limit_exceeded_monthly(self, test_user, db):
        """Test rate limit check when monthly quota exceeded."""
        plaintext_key, api_key = APIKeyService.create_api_key(
            user_id=test_user.id,
            name="Test Key",
            db=db,
        )

        # Set usage to exceed quota
        api_key.requests_this_month = api_key.monthly_quota + 1
        db.add(api_key)
        db.commit()

        is_allowed, info = APIKeyService.check_rate_limit(api_key)

        assert is_allowed is False
        assert "exceeded" in info.get("error", "").lower()

    def test_reset_monthly_quota(self, test_user, db):
        """Test monthly quota reset."""
        # Create multiple keys
        for i in range(3):
            plaintext_key, api_key = APIKeyService.create_api_key(
                user_id=test_user.id,
                name=f"Key {i}",
                db=db,
            )
            api_key.requests_this_month = 100
            db.add(api_key)
        db.commit()

        count = APIKeyService.reset_monthly_quota(db)

        assert count == 3

        # Verify all keys reset
        keys = db.query(APIKey).filter(APIKey.is_active == True).all()
        for api_key in keys:
            assert api_key.requests_this_month == 0

    def test_get_key_stats(self, test_user, db):
        """Test retrieving key statistics."""
        plaintext_key, api_key = APIKeyService.create_api_key(
            user_id=test_user.id,
            name="Test Key",
            db=db,
        )

        # Record some usage
        APIKeyService.record_usage(api_key.id, db)
        APIKeyService.record_usage(api_key.id, db)

        stats = APIKeyService.get_key_stats(api_key.id, db)

        assert stats["id"] == api_key.id
        assert stats["name"] == "Test Key"
        assert stats["requests_lifetime"] == 2
        assert stats["requests_this_month"] == 2
        assert stats["quota_remaining"] == api_key.monthly_quota - 2


# ===== Key Rotation Tests =====

class TestKeyRotation:
    """Test API key rotation functionality."""

    def test_rotate_key_creates_new_key(self, test_user, db):
        """Test that key rotation creates a new active key."""
        plaintext_key, old_api_key = APIKeyService.create_api_key(
            user_id=test_user.id,
            name="Original Key",
            db=db,
        )

        new_plaintext, new_api_key = APIKeyService.rotate_key(old_api_key.id, db)

        assert new_plaintext != plaintext_key
        assert new_api_key.id != old_api_key.id
        assert new_api_key.is_active is True

    def test_rotate_key_deactivates_old_key(self, test_user, db):
        """Test that rotation deactivates the old key."""
        plaintext_key, old_api_key = APIKeyService.create_api_key(
            user_id=test_user.id,
            name="Original Key",
            db=db,
        )

        new_plaintext, new_api_key = APIKeyService.rotate_key(old_api_key.id, db)

        # Refresh old key from database
        old_api_key = db.query(APIKey).filter(APIKey.id == old_api_key.id).first()

        assert old_api_key.is_active is False

    def test_rotate_key_preserves_properties(self, test_user, db):
        """Test that rotation preserves key properties."""
        scopes = ["read", "write"]
        plaintext_key, old_api_key = APIKeyService.create_api_key(
            user_id=test_user.id,
            name="Original Key",
            db=db,
            tier="pro",
            scopes=scopes,
        )

        new_plaintext, new_api_key = APIKeyService.rotate_key(old_api_key.id, db)

        assert new_api_key.tier == old_api_key.tier
        assert new_api_key.scopes == old_api_key.scopes
        assert new_api_key.user_id == old_api_key.user_id


# ===== Key Disable/Delete Tests =====

class TestKeyLifecycle:
    """Test API key disable and delete operations."""

    def test_disable_key(self, test_user, db):
        """Test disabling an API key."""
        plaintext_key, api_key = APIKeyService.create_api_key(
            user_id=test_user.id,
            name="Test Key",
            db=db,
        )

        APIKeyService.disable_key(api_key.id, db)

        # Refresh from database
        api_key = db.query(APIKey).filter(APIKey.id == api_key.id).first()

        assert api_key.is_active is False

    def test_delete_key(self, test_user, db):
        """Test deleting an API key."""
        plaintext_key, api_key = APIKeyService.create_api_key(
            user_id=test_user.id,
            name="Test Key",
            db=db,
        )

        key_id = api_key.id
        APIKeyService.delete_key(key_id, db)

        # Verify key is deleted
        api_key = db.query(APIKey).filter(APIKey.id == key_id).first()

        assert api_key is None

    def test_get_user_keys(self, test_user, db):
        """Test retrieving user's API keys."""
        for i in range(3):
            APIKeyService.create_api_key(
                user_id=test_user.id,
                name=f"Key {i}",
                db=db,
            )

        keys = APIKeyService.get_user_keys(test_user.id, db)

        assert len(keys) == 3

    def test_get_user_keys_excludes_inactive(self, test_user, db):
        """Test that inactive keys are excluded by default."""
        plaintext_key, api_key = APIKeyService.create_api_key(
            user_id=test_user.id,
            name="Test Key",
            db=db,
        )

        # Create another and disable it
        plaintext_key2, api_key2 = APIKeyService.create_api_key(
            user_id=test_user.id,
            name="Disabled Key",
            db=db,
            tier="pro",
        )

        APIKeyService.disable_key(api_key2.id, db)

        keys = APIKeyService.get_user_keys(test_user.id, db, include_inactive=False)

        assert len(keys) == 1
        assert keys[0].id == api_key.id

    def test_get_user_keys_includes_inactive(self, test_user, db):
        """Test that inactive keys are included when requested."""
        plaintext_key, api_key = APIKeyService.create_api_key(
            user_id=test_user.id,
            name="Test Key",
            db=db,
        )

        plaintext_key2, api_key2 = APIKeyService.create_api_key(
            user_id=test_user.id,
            name="Disabled Key",
            db=db,
            tier="pro",
        )

        APIKeyService.disable_key(api_key2.id, db)

        keys = APIKeyService.get_user_keys(test_user.id, db, include_inactive=True)

        assert len(keys) == 2


# ===== Integration Tests =====

class TestIntegration:
    """Integration tests combining multiple operations."""

    def test_complete_key_lifecycle(self, test_user, db):
        """Test complete API key lifecycle."""
        # Create
        plaintext_key, api_key = APIKeyService.create_api_key(
            user_id=test_user.id,
            name="Lifecycle Key",
            db=db,
        )

        # Verify
        result = APIKeyService.verify_api_key(plaintext_key, db)
        assert result is not None

        # Record usage
        APIKeyService.record_usage(api_key.id, db)

        # Check stats
        stats = APIKeyService.get_key_stats(api_key.id, db)
        assert stats["requests_lifetime"] == 1

        # Rotate
        new_plaintext, new_api_key = APIKeyService.rotate_key(api_key.id, db)

        # Verify old key no longer works
        old_result = APIKeyService.verify_api_key(plaintext_key, db)
        assert old_result is None

        # Verify new key works
        new_result = APIKeyService.verify_api_key(new_plaintext, db)
        assert new_result is not None

        # Disable new key
        APIKeyService.disable_key(new_api_key.id, db)

        # Verify disabled key doesn't work
        disabled_result = APIKeyService.verify_api_key(new_plaintext, db)
        assert disabled_result is None

    def test_multi_user_key_isolation(self, db):
        """Test that users' keys are isolated."""
        # Create two users
        user1 = UserProfile(id=1, username="user1", email="user1@example.com")
        user2 = UserProfile(id=2, username="user2", email="user2@example.com")
        db.add_all([user1, user2])
        db.commit()

        # Create keys for each user
        key1_plaintext, key1 = APIKeyService.create_api_key(
            user_id=user1.id,
            name="User1 Key",
            db=db,
        )

        key2_plaintext, key2 = APIKeyService.create_api_key(
            user_id=user2.id,
            name="User2 Key",
            db=db,
        )

        # Verify each user can only see their own keys
        user1_keys = APIKeyService.get_user_keys(user1.id, db)
        user2_keys = APIKeyService.get_user_keys(user2.id, db)

        assert len(user1_keys) == 1
        assert len(user2_keys) == 1
        assert user1_keys[0].id == key1.id
        assert user2_keys[0].id == key2.id
