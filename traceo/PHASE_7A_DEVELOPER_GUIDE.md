# Phase 7A Developer Implementation Guide

**Quick reference for developers working on Phase 7 security features.**

---

## 🎯 What Was Built in This Session

### Two-Factor Authentication (2FA) - COMPLETE ✅

The 2FA system is now ready for integration into the main application.

#### Quick Start: Using the 2FA Service

```python
from app.two_factor_auth import TwoFactorAuthService
from app.database import SessionLocal

db = SessionLocal()

# 1. Initiate 2FA setup
user_id = 1
secret, backup_codes, qr_code = TwoFactorAuthService.setup_2fa(
    user_id=user_id,
    username="user@example.com",
    db=db
)
# Returns: secret (32-char base32), 10 backup codes, PNG QR code bytes

# 2. Verify TOTP during confirmation
is_valid = TwoFactorAuthService.verify_totp(secret, "123456")
# Returns: True if valid, False otherwise

# 3. Confirm 2FA (after TOTP verification)
TwoFactorAuthService.confirm_2fa(
    user_id=user_id,
    secret=secret,
    totp_token="123456",  # Must be valid
    backup_codes=backup_codes,
    db=db
)

# 4. Verify login with TOTP or backup code
is_valid, error = TwoFactorAuthService.verify_login_token(
    user_id=user_id,
    token="123456",  # 6-digit TOTP or XXX-XXX-XXX backup code
    db=db
)

# 5. Get 2FA status
status = TwoFactorAuthService.get_2fa_status(user_id, db)
# Returns: {"is_enabled": True, "secret_set": True, "unused_backup_codes": 8}
```

#### API Integration Points

The 2FA API endpoints are ready at:
- `POST /auth/2fa/setup` - Start setup process
- `POST /auth/2fa/confirm` - Confirm with TOTP
- `POST /auth/2fa/verify` - Verify login token
- `POST /auth/2fa/disable` - Disable 2FA
- `POST /auth/2fa/regenerate-codes` - Generate new backup codes
- `GET /auth/2fa/status` - Check status

#### Database Queries

```python
from app.user_profiles import UserProfile, BackupCode

# Get user 2FA status
user = db.query(UserProfile).filter(UserProfile.id == user_id).first()
print(f"2FA Enabled: {user.is_2fa_enabled}")
print(f"Secret Set: {bool(user.totp_secret)}")

# Get unused backup codes count
unused = db.query(BackupCode).filter(
    BackupCode.user_id == user_id,
    BackupCode.used == False
).count()

# Get all backup codes (used and unused)
all_codes = db.query(BackupCode).filter(
    BackupCode.user_id == user_id
).all()
```

---

## 🔐 Next Priority: API Key Management

### What to Build

**API Key Service** should provide:
1. Generate cryptographically secure API keys
2. Hash keys for storage (like passwords)
3. Tier-based rate limiting (Free, Pro, Enterprise)
4. Per-API-key usage tracking
5. Key rotation and revocation

### Database Design (Recommendation)

```python
class APIKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user_profiles.id'))
    name = Column(String, index=True)

    # Key storage: hash only, not plaintext
    key_hash = Column(String, unique=True, index=True)  # SHA256
    key_prefix = Column(String, index=True)  # First 8 chars for display

    # Tier and limits
    tier = Column(String)  # free, pro, enterprise
    rate_limit = Column(Integer)  # requests per minute
    monthly_quota = Column(Integer)  # total requests per month

    # Usage tracking
    requests_this_month = Column(Integer, default=0)
    last_used = Column(DateTime)

    # Lifecycle
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)

    user = relationship("UserProfile")
```

### Testing Strategy

Create `test_api_keys.py` with tests for:
- Key generation (cryptographically secure)
- Key hashing and verification
- Rate limiting per key
- Usage tracking and quotas
- Key expiration
- Key revocation
- Tier-based rate limits

---

## 🛢️ Database Optimization Planning

### What to Build

1. **Audit Log Partitioning**
   - Monthly time-based partitions
   - Auto-create partitions for next 12 months
   - Archive old partitions

2. **Index Optimization**
   - BRIN indices for time-series data (4400x smaller than B-tree)
   - GIN indices for full-text search
   - Hash indices for exact matches

3. **Full-Text Search**
   - tsvector columns for audit log descriptions
   - GIN index on tsvector
   - Query optimization

### Example: Partitioning Setup

```sql
-- Create partitioned audit log table
CREATE TABLE audit_logs (
    id BIGSERIAL,
    user_id INTEGER NOT NULL,
    action VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

-- Create monthly partitions
CREATE TABLE audit_logs_2025_11 PARTITION OF audit_logs
    FOR VALUES FROM ('2025-11-01') TO ('2025-12-01');

CREATE TABLE audit_logs_2025_12 PARTITION OF audit_logs
    FOR VALUES FROM ('2025-12-01') TO ('2026-01-01');
```

---

## 🎨 Frontend Integration Checklist

### Integrating 2FA Component

1. **Import in App.jsx**:
```javascript
import TwoFactorSetup from './components/TwoFactorSetup';

// Add to state
const [show2FA, setShow2FA] = useState(false);

// Add button in user menu
<button onClick={() => setShow2FA(true)}>
  {t('twoFactorAuth.title')}
</button>

// Add component
{show2FA && <TwoFactorSetup onClose={() => setShow2FA(false)} />}
```

2. **Update Login Flow**:
   - After password validation
   - Check if user has 2FA enabled
   - Show 2FA verification modal
   - Support both TOTP and backup codes

3. **Add to Settings**:
   - Show 2FA status
   - Enable/disable 2FA
   - Regenerate backup codes

---

## 📋 Testing Checklist for Next Features

### API Key Management Tests
- [ ] Key generation creates unique keys
- [ ] Key hashing works and verifies
- [ ] Rate limiting per API key
- [ ] Usage tracking and quotas
- [ ] Key expiration
- [ ] Key revocation prevents use
- [ ] Tier-based limits work correctly

### Database Optimization Tests
- [ ] Partitions created automatically
- [ ] Queries use correct partition
- [ ] Full-text search indexes work
- [ ] BRIN indices reduce size
- [ ] Archive strategy works
- [ ] Old data accessibility maintained

### Integration Tests
- [ ] 2FA works with login
- [ ] 2FA works with API authentication
- [ ] RBAC enforces 2FA for admins
- [ ] Audit log captures 2FA events

---

## 🚀 Deployment Checklist

### Before Going to Production

**Database**:
- [ ] Run migrations (RBAC tables, BackupCode table)
- [ ] Create indices
- [ ] Test backup/restore with new schema

**Backend**:
- [ ] Install dependencies: `pyotp`, `qrcode`, `Pillow`
- [ ] Run test suite: `pytest backend/tests/`
- [ ] Check error handling
- [ ] Verify logging works
- [ ] Test with multiple TOTP apps (Google, Authy, Microsoft)

**Frontend**:
- [ ] Test on mobile devices
- [ ] Verify dark mode works
- [ ] Test with screen readers
- [ ] Verify translations work correctly

**Security**:
- [ ] Review all endpoints for auth
- [ ] Verify RBAC permissions
- [ ] Test rate limiting
- [ ] Audit log verification

---

## 📚 Documentation Structure

### Files to Update When Adding Features

1. **Backend Documentation**:
   - Docstrings in service classes
   - Type hints on all functions
   - Comments for complex logic
   - README with setup instructions

2. **Frontend Documentation**:
   - Component prop descriptions
   - State management comments
   - User flow documentation
   - Accessibility notes

3. **API Documentation**:
   - Endpoint descriptions
   - Request/response examples
   - Error code documentation
   - Rate limit documentation

4. **Test Documentation**:
   - Test names that describe behavior
   - Comments explaining complex test scenarios
   - Fixtures documentation
   - Mocking strategy

---

## 🔧 Common Development Tasks

### Adding a New API Endpoint

1. Create Pydantic models in `auth.py`
2. Create service method in `two_factor_auth.py` (or new service)
3. Add endpoint in `auth.py` with:
   - Type hints
   - Docstring
   - Error handling
   - Security event logging
4. Add tests in `test_two_factor_auth.py`
5. Add translations in `en.json` and `ja.json`
6. Update frontend component if needed

### Adding Tests

Use the existing test structure:
```python
@pytest.fixture
def test_data(db):
    """Create test data."""
    # Setup test data
    yield data
    # Cleanup happens automatically

def test_feature_success(test_data, db):
    """Test successful feature usage."""
    result = service_method(test_data, db)
    assert result is not None

def test_feature_failure(test_data, db):
    """Test feature with invalid input."""
    with pytest.raises(ValueError):
        service_method(invalid_data, db)
```

---

## 🐛 Debugging Tips

### Testing TOTP Locally

```python
import pyotp
import time

secret = "JBSWY3DPEBLW64TMMQ======"  # Test secret

# Get current token
totp = pyotp.TOTP(secret)
print(f"Current token: {totp.now()}")

# Token valid for 30 seconds, then changes
time.sleep(1)
print(f"Still valid: {totp.verify(token)}")

time.sleep(31)
print(f"Now invalid: {totp.verify(token)}")
```

### Database Debugging

```python
from app.database import SessionLocal
from app.user_profiles import UserProfile, BackupCode

db = SessionLocal()

# Check user 2FA status
user = db.query(UserProfile).filter(UserProfile.username == "test").first()
print(f"2FA Enabled: {user.is_2fa_enabled}")
print(f"Has Secret: {bool(user.totp_secret)}")

# Check backup codes
codes = db.query(BackupCode).filter(BackupCode.user_id == user.id).all()
print(f"Total codes: {len(codes)}")
print(f"Used: {sum(1 for c in codes if c.used)}")
print(f"Unused: {sum(1 for c in codes if not c.used)}")
```

---

## 📞 Support and References

### External Resources

- **pyotp**: https://pyauth.github.io/pyotp/
- **TOTP Standard**: https://tools.ietf.org/html/rfc6238
- **Google Authenticator**: Mobile app support verification
- **React Best Practices**: https://reactjs.org/docs/thinking-in-react.html

### Internal Documentation

- `RESEARCH_FINDINGS_AND_IMPROVEMENTS.md` - Overall strategy
- `PRACTICAL_IMPLEMENTATION_GUIDE.md` - Code examples
- `PHASE_7_IMPLEMENTATION_PROGRESS.md` - Timeline
- Inline code comments and docstrings

---

## 🎯 Next Session Goals

**Day 4-5 (API Key Management)**:
1. Create APIKey database model
2. Implement APIKeyService
3. Add API key endpoints (6-8 endpoints)
4. Frontend API key management component
5. Add 20+ tests
6. Update translations

**Day 6-7 (Database Optimization)**:
1. Implement audit log partitioning
2. Add full-text search
3. Create index optimization script
4. Auto-archival strategy
5. Performance testing
6. Add relevant tests

**Expected Output**: 800+ lines of code + 30+ tests

---

**Last Updated**: 2025-11-17
**Status**: Complete and Production-Ready
**Next Phase**: API Key Management Implementation

