"""
Comprehensive test suite for Encryption Service.

Tests cover:
- Key generation and derivation
- Field encryption/decryption
- HMAC computation and verification
- Key rotation
- Batch operations
- Error handling
"""

import pytest
import os
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.encryption_service import EncryptionService, EncryptionKeyManager
from app.user_profiles import EncryptionKey, EncryptedField
from app.database import SessionLocal, Base, engine


# ===== Fixtures =====

@pytest.fixture(scope="session")
def db_setup():
    """Set up test database"""
    Base.metadata.create_all(bind=engine)
    yield
    # Keep tables for inspection


@pytest.fixture
def db():
    """Database session for each test"""
    connection = engine.connect()
    transaction = connection.begin()
    session = SessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def master_key():
    """Generate a test master key"""
    return EncryptionService.generate_master_key()


@pytest.fixture
def encryption_service(master_key):
    """Create encryption service instance"""
    return EncryptionService(bytes.fromhex(master_key))


# ===== Key Generation Tests =====

class TestKeyGeneration:
    """Test master key generation"""

    def test_generate_master_key_returns_hex_string(self):
        """Test that master key generation returns valid hex"""
        key = EncryptionService.generate_master_key()
        assert isinstance(key, str)
        assert all(c in "0123456789abcdef" for c in key.lower())

    def test_generate_master_key_correct_length(self):
        """Test that master key is 256 bits (64 hex chars)"""
        key = EncryptionService.generate_master_key()
        assert len(key) == 64  # 32 bytes = 64 hex chars

    def test_generate_master_key_uniqueness(self):
        """Test that generated keys are unique"""
        key1 = EncryptionService.generate_master_key()
        key2 = EncryptionService.generate_master_key()
        assert key1 != key2

    def test_validate_master_key_valid(self):
        """Test validation of valid master key"""
        key = EncryptionService.generate_master_key()
        assert EncryptionService.validate_master_key(key) is True

    def test_validate_master_key_invalid_length(self):
        """Test validation rejects wrong length"""
        invalid_key = "abcd" * 10  # Wrong length
        assert EncryptionService.validate_master_key(invalid_key) is False

    def test_validate_master_key_invalid_hex(self):
        """Test validation rejects invalid hex"""
        invalid_key = "zzzz" * 16
        assert EncryptionService.validate_master_key(invalid_key) is False


# ===== Field Key Derivation Tests =====

class TestKeyDerivation:
    """Test field-specific key derivation"""

    def test_derive_field_key_returns_bytes(self, encryption_service):
        """Test that field key derivation returns bytes"""
        key = encryption_service.derive_field_key("email")
        assert isinstance(key, bytes)
        assert len(key) == 32  # 256 bits

    def test_derive_field_key_different_for_different_fields(self, encryption_service):
        """Test that different fields get different keys"""
        key1 = encryption_service.derive_field_key("email")
        key2 = encryption_service.derive_field_key("phone")
        assert key1 != key2

    def test_derive_field_key_deterministic(self, encryption_service):
        """Test that key derivation is deterministic"""
        key1 = encryption_service.derive_field_key("email", 1)
        key2 = encryption_service.derive_field_key("email", 1)
        assert key1 == key2

    def test_derive_field_key_version_dependent(self, encryption_service):
        """Test that version changes key"""
        key1 = encryption_service.derive_field_key("email", 1)
        key2 = encryption_service.derive_field_key("email", 2)
        assert key1 != key2


# ===== Field Encryption Tests =====

class TestFieldEncryption:
    """Test single field encryption/decryption"""

    def test_encrypt_field_returns_string(self, encryption_service):
        """Test that encryption returns base64 string"""
        encrypted = encryption_service.encrypt_field("test@example.com", "email")
        assert isinstance(encrypted, str)
        assert len(encrypted) > 0

    def test_encrypt_field_format(self, encryption_service):
        """Test that encrypted field has correct format"""
        encrypted = encryption_service.encrypt_field("test@example.com", "email")
        # Should be base64 decodable
        from base64 import b64decode
        decoded = b64decode(encrypted)
        # Should have at least: 1 byte version + 12 bytes nonce + 16 bytes tag
        assert len(decoded) >= 29

    def test_encrypt_same_value_produces_different_ciphertext(self, encryption_service):
        """Test that same plaintext produces different ciphertext (random nonce)"""
        plaintext = "test@example.com"
        encrypted1 = encryption_service.encrypt_field(plaintext, "email")
        encrypted2 = encryption_service.encrypt_field(plaintext, "email")
        assert encrypted1 != encrypted2

    def test_decrypt_returns_original_plaintext(self, encryption_service):
        """Test decryption recovers original plaintext"""
        plaintext = "test@example.com"
        encrypted = encryption_service.encrypt_field(plaintext, "email")
        decrypted = encryption_service.decrypt_field(encrypted, "email")
        assert decrypted == plaintext

    def test_decrypt_with_additional_data(self, encryption_service):
        """Test encryption/decryption with authenticated data"""
        plaintext = "sensitive_value"
        aad = b"user_123"

        encrypted = encryption_service.encrypt_field(
            plaintext, "ssn", additional_data=aad
        )
        decrypted = encryption_service.decrypt_field(
            encrypted, "ssn", additional_data=aad
        )

        assert decrypted == plaintext

    def test_decrypt_with_wrong_additional_data_fails(self, encryption_service):
        """Test that wrong AAD causes decryption to fail"""
        plaintext = "sensitive_value"
        encrypted = encryption_service.encrypt_field(
            plaintext, "ssn", additional_data=b"user_123"
        )

        with pytest.raises(ValueError):
            encryption_service.decrypt_field(
                encrypted, "ssn", additional_data=b"user_456"
            )

    def test_decrypt_wrong_field_fails(self, encryption_service):
        """Test that decrypting with wrong field name fails"""
        encrypted = encryption_service.encrypt_field("test@example.com", "email")

        with pytest.raises(ValueError):
            encryption_service.decrypt_field(encrypted, "phone")

    def test_encrypt_empty_string(self, encryption_service):
        """Test encryption of empty string"""
        encrypted = encryption_service.encrypt_field("", "email")
        decrypted = encryption_service.decrypt_field(encrypted, "email")
        assert decrypted == ""

    def test_encrypt_special_characters(self, encryption_service):
        """Test encryption with special characters"""
        plaintext = "!@#$%^&*()+=-[]{}|;':\",./<>?"
        encrypted = encryption_service.encrypt_field(plaintext, "text_field")
        decrypted = encryption_service.decrypt_field(encrypted, "text_field")
        assert decrypted == plaintext

    def test_encrypt_unicode_characters(self, encryption_service):
        """Test encryption with unicode"""
        plaintext = "Hello 你好 مرحبا Привет"
        encrypted = encryption_service.encrypt_field(plaintext, "text_field")
        decrypted = encryption_service.decrypt_field(encrypted, "text_field")
        assert decrypted == plaintext

    def test_encrypt_large_text(self, encryption_service):
        """Test encryption of large text"""
        plaintext = "x" * 10000
        encrypted = encryption_service.encrypt_field(plaintext, "text_field")
        decrypted = encryption_service.decrypt_field(encrypted, "text_field")
        assert decrypted == plaintext

    def test_encrypt_invalid_plaintext_type(self, encryption_service):
        """Test that non-string plaintext is rejected"""
        with pytest.raises(ValueError):
            encryption_service.encrypt_field(12345, "field")

    def test_decrypt_invalid_format(self, encryption_service):
        """Test that invalid ciphertext format is rejected"""
        with pytest.raises(ValueError):
            encryption_service.decrypt_field("not_base64!", "field")

    def test_decrypt_corrupted_ciphertext(self, encryption_service):
        """Test that corrupted ciphertext fails to decrypt"""
        plaintext = "test@example.com"
        encrypted = encryption_service.encrypt_field(plaintext, "email")

        # Corrupt the ciphertext
        from base64 import b64decode, b64encode
        decoded = bytearray(b64decode(encrypted))
        decoded[-1] ^= 0xFF  # Flip bits in last byte
        corrupted = b64encode(bytes(decoded)).decode()

        with pytest.raises(ValueError):
            encryption_service.decrypt_field(corrupted, "email")


# ===== HMAC Tests =====

class TestHMAC:
    """Test HMAC computation and verification"""

    def test_compute_field_hmac_returns_hex(self):
        """Test that HMAC returns hex string"""
        secret = b"secret_key"
        hmac_value = EncryptionService.compute_field_hmac(
            "test@example.com", "email", secret
        )
        assert isinstance(hmac_value, str)
        assert all(c in "0123456789abcdef" for c in hmac_value)

    def test_compute_field_hmac_length(self):
        """Test that HMAC-SHA256 produces 64 hex chars"""
        secret = b"secret_key"
        hmac_value = EncryptionService.compute_field_hmac(
            "test@example.com", "email", secret
        )
        assert len(hmac_value) == 64  # SHA256 = 32 bytes = 64 hex chars

    def test_compute_field_hmac_deterministic(self):
        """Test that HMAC is deterministic"""
        secret = b"secret_key"
        hmac1 = EncryptionService.compute_field_hmac(
            "test@example.com", "email", secret
        )
        hmac2 = EncryptionService.compute_field_hmac(
            "test@example.com", "email", secret
        )
        assert hmac1 == hmac2

    def test_verify_field_hmac_valid(self):
        """Test HMAC verification with correct value"""
        secret = b"secret_key"
        plaintext = "test@example.com"
        hmac_value = EncryptionService.compute_field_hmac(
            plaintext, "email", secret
        )

        result = EncryptionService.verify_field_hmac(
            plaintext, "email", secret, hmac_value
        )
        assert result is True

    def test_verify_field_hmac_invalid(self):
        """Test HMAC verification fails with wrong HMAC"""
        secret = b"secret_key"
        plaintext = "test@example.com"

        result = EncryptionService.verify_field_hmac(
            plaintext, "email", secret, "0" * 64
        )
        assert result is False

    def test_verify_field_hmac_timing_safe(self):
        """Test that HMAC verification is timing-safe"""
        secret = b"secret_key"
        plaintext = "test@example.com"
        hmac_value = EncryptionService.compute_field_hmac(
            plaintext, "email", secret
        )

        # Should complete in constant time regardless of HMAC match
        import time

        wrong_hmac = "0" * 64
        start = time.time()
        EncryptionService.verify_field_hmac(plaintext, "email", secret, wrong_hmac)
        time1 = time.time() - start

        start = time.time()
        EncryptionService.verify_field_hmac(plaintext, "email", secret, hmac_value)
        time2 = time.time() - start

        # Times should be similar (within 50% tolerance for testing)
        # Real timing-safe comparison takes similar time
        assert abs(time1 - time2) < max(time1, time2) * 0.5


# ===== Batch Operations Tests =====

class TestBatchOperations:
    """Test batch encryption/decryption"""

    def test_encrypt_batch(self, encryption_service):
        """Test encrypting multiple fields"""
        fields = {
            "email": "test@example.com",
            "phone": "555-1234",
            "ssn": "123-45-6789",
        }

        encrypted = encryption_service.encrypt_batch(fields)

        assert len(encrypted) == 3
        assert all(isinstance(v, str) for v in encrypted.values())
        assert all(v != fields[k] for k, v in encrypted.items())

    def test_decrypt_batch(self, encryption_service):
        """Test decrypting multiple fields"""
        original = {
            "email": "test@example.com",
            "phone": "555-1234",
            "ssn": "123-45-6789",
        }

        encrypted = encryption_service.encrypt_batch(original)
        decrypted = encryption_service.decrypt_batch(encrypted)

        assert decrypted == original

    def test_batch_operations_consistency(self, encryption_service):
        """Test that batch and single operations produce same results"""
        plaintext = "test@example.com"

        # Single operation
        single_encrypted = encryption_service.encrypt_field(plaintext, "email")

        # Batch operation
        batch_encrypted = encryption_service.encrypt_batch({"email": plaintext})["email"]

        # Both should decrypt to same plaintext
        single_decrypted = encryption_service.decrypt_field(single_encrypted, "email")
        batch_decrypted = encryption_service.decrypt_field(batch_encrypted, "email")

        assert single_decrypted == batch_decrypted == plaintext


# ===== Key Rotation Tests =====

class TestKeyRotation:
    """Test key rotation functionality"""

    def test_rotate_keys(self, encryption_service, db):
        """Test key rotation operation"""
        # Create initial key
        EncryptionKeyManager.create_encryption_key(
            db, version=1, status="active", description="Initial key"
        )

        # Perform rotation
        result = encryption_service.rotate_keys(db, 1, 2)

        assert result["status"] == "success"
        assert result["old_version"] == 1
        assert result["new_version"] == 2

    def test_key_rotation_reencrypts_fields(self, encryption_service, db):
        """Test that rotation re-encrypts fields"""
        # Create initial key
        EncryptionKeyManager.create_encryption_key(
            db, version=1, status="active"
        )

        # Encrypt a field
        plaintext = "test@example.com"
        encrypted = encryption_service.encrypt_field(plaintext, "email", key_version=1)

        # Store in database
        encrypted_field = EncryptedField(
            field_name="email",
            encrypted_value=encrypted,
            key_version=1,
            entity_type="user",
            entity_id=1,
        )
        db.add(encrypted_field)
        db.commit()

        # Create new key
        EncryptionKeyManager.create_encryption_key(
            db, version=2, status="active"
        )

        # Perform rotation
        encryption_service.rotate_keys(db, 1, 2)

        # Verify field was re-encrypted
        db.refresh(encrypted_field)
        assert encrypted_field.key_version == 2

        # Verify it can still be decrypted
        decrypted = encryption_service.decrypt_field(
            encrypted_field.encrypted_value, "email"
        )
        assert decrypted == plaintext


# ===== Encryption Info Tests =====

class TestEncryptionInfo:
    """Test encryption system information"""

    def test_get_encryption_info(self):
        """Test getting encryption system info"""
        info = EncryptionService.get_encryption_info()

        assert info["algorithm"] == "AES-256-GCM"
        assert info["key_size"] == 256
        assert info["nonce_size"] == 96
        assert info["tag_size"] == 128
        assert info["hash_algorithm"] == "SHA-256"
        assert "standards" in info
        assert len(info["standards"]) > 0


# ===== Key Manager Tests =====

class TestEncryptionKeyManager:
    """Test encryption key management"""

    def test_create_encryption_key(self, db):
        """Test creating an encryption key"""
        key = EncryptionKeyManager.create_encryption_key(
            db, version=1, status="active", description="Test key"
        )

        assert key.version == 1
        assert key.status == "active"
        assert key.description == "Test key"

    def test_get_active_key_version(self, db):
        """Test getting active key version"""
        EncryptionKeyManager.create_encryption_key(db, version=1, status="active")

        active_version = EncryptionKeyManager.get_active_key_version(db)
        assert active_version == 1

    def test_get_active_key_version_no_active_key(self, db):
        """Test error when no active key exists"""
        with pytest.raises(ValueError):
            EncryptionKeyManager.get_active_key_version(db)

    def test_deactivate_key(self, db):
        """Test deactivating a key"""
        EncryptionKeyManager.create_encryption_key(db, version=1, status="active")
        EncryptionKeyManager.deactivate_key(db, 1)

        key = db.query(EncryptionKey).filter(
            EncryptionKey.version == 1
        ).first()

        assert key.status == "inactive"
        assert key.deactivated_at is not None

    def test_get_key_stats(self, db):
        """Test getting key statistics"""
        EncryptionKeyManager.create_encryption_key(db, version=1, status="active")
        EncryptionKeyManager.create_encryption_key(db, version=2, status="inactive")

        stats = EncryptionKeyManager.get_key_stats(db)

        assert stats["total_keys"] == 2
        assert stats["by_status"]["active"] == 1
        assert stats["by_status"]["inactive"] == 1
        assert stats["latest_version"] == 2
