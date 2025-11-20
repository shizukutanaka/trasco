# Traceo - Practical Implementation Guide
**Production-Ready Code Examples for Phase 7 Features**

Generated: 2025-11-17
Scope: 2FA, Encryption, API Keys, ML Detection, Database Optimization

---

## 📦 All Required Libraries

```bash
# 2FA & Authentication
pip install pyotp==2.9.0
pip install qrcode[pil]==7.4.2
pip install Pillow==10.0.0

# Encryption
pip install cryptography==41.0.7

# API Key Management
pip install redis==5.0.1

# ML Phishing Detection
pip install scikit-learn==1.3.2
pip install xgboost==2.0.3
pip install pandas==2.1.4
pip install numpy==1.26.2
pip install joblib==1.3.2
pip install nltk==3.8.1
pip install tldextract==5.1.1

# Core dependencies
pip install SQLAlchemy==2.0.23
pip install psycopg2-binary==2.9.9
pip install fastapi==0.104.1
pip install uvicorn==0.24.0
pip install python-dotenv==1.0.0
```

---

## 1️⃣ 2FA Implementation (TOTP)

### Database Schema
```python
# Models to add to app/models.py

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True)
    email = Column(String(120), unique=True)
    password_hash = Column(String(255))

    # 2FA fields
    totp_secret = Column(String(32), nullable=True)
    is_2fa_enabled = Column(Boolean, default=False)

    # Relationships
    backup_codes = relationship("BackupCode", back_populates="user")

class BackupCode(Base):
    __tablename__ = 'backup_codes'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    code_hash = Column(String(255), nullable=False, unique=True)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    used_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="backup_codes")
```

### 2FA Service
```python
# Create: app/two_factor_auth.py

import pyotp
import qrcode
import io
import base64
from hashlib import sha256
import secrets
from datetime import datetime

class TwoFactorAuthService:
    """2FA management service"""

    @staticmethod
    def generate_secret():
        """Generate TOTP secret"""
        return pyotp.random_base32()

    @staticmethod
    def get_provisioning_uri(email, secret, issuer="Traceo"):
        """Get QR code provisioning URI"""
        totp = pyotp.TOTP(secret)
        return totp.provisioning_uri(name=email, issuer_name=issuer)

    @staticmethod
    def generate_qr_code(uri):
        """Generate QR code as base64"""
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(uri)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        return f"data:image/png;base64,{img_str}"

    @staticmethod
    def verify_totp(secret, token):
        """Verify TOTP token"""
        totp = pyotp.TOTP(secret)
        return totp.verify(token, valid_window=1)

    @staticmethod
    def generate_backup_codes(count=10):
        """Generate backup codes"""
        return [secrets.token_urlsafe(6) for _ in range(count)]

    @staticmethod
    def hash_backup_code(code):
        """Hash backup code"""
        return sha256(code.encode()).hexdigest()

    @staticmethod
    def verify_backup_code(code, stored_hash):
        """Verify backup code"""
        return secrets.compare_digest(
            sha256(code.encode()).hexdigest(),
            stored_hash
        )
```

### 2FA API Endpoints
```python
# Add to: app/auth.py

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.two_factor_auth import TwoFactorAuthService
from app.models import User, BackupCode
from app.database import get_db
from app.security import get_current_user

router = APIRouter(prefix="/auth/2fa", tags=["2fa"])

class Setup2FARequest(BaseModel):
    password: str  # Verify password before enabling 2FA

class Verify2FARequest(BaseModel):
    token: str  # 6-digit TOTP code

class DisableSecurity(BaseModel):
    password: str
    backup_code: str

@router.post("/setup")
async def setup_2fa(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generate TOTP secret and QR code"""

    # Check if already enabled
    if current_user.is_2fa_enabled:
        raise HTTPException(
            status_code=400,
            detail="2FA already enabled"
        )

    # Generate secret
    secret = TwoFactorAuthService.generate_secret()
    uri = TwoFactorAuthService.get_provisioning_uri(current_user.email, secret)
    qr_code = TwoFactorAuthService.generate_qr_code(uri)

    # Generate backup codes
    backup_codes = TwoFactorAuthService.generate_backup_codes(10)
    backup_codes_hashed = [
        TwoFactorAuthService.hash_backup_code(code)
        for code in backup_codes
    ]

    # Store secret temporarily (not enabled yet)
    current_user.totp_secret = secret
    db.commit()

    return {
        'qr_code': qr_code,
        'secret': secret,  # Show once
        'backup_codes': backup_codes  # Show once
    }

@router.post("/confirm")
async def confirm_2fa(
    request: Verify2FARequest,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Confirm 2FA with TOTP token"""

    if not current_user.totp_secret:
        raise HTTPException(
            status_code=400,
            detail="No pending 2FA setup"
        )

    # Verify token
    if not TwoFactorAuthService.verify_totp(current_user.totp_secret, request.token):
        raise HTTPException(
            status_code=400,
            detail="Invalid verification code"
        )

    # Generate and store backup codes
    backup_codes = TwoFactorAuthService.generate_backup_codes(10)

    for code in backup_codes:
        backup_code = BackupCode(
            user_id=current_user.id,
            code_hash=TwoFactorAuthService.hash_backup_code(code)
        )
        db.add(backup_code)

    # Enable 2FA
    current_user.is_2fa_enabled = True
    db.commit()

    return {
        'message': '2FA enabled successfully',
        'backup_codes': backup_codes  # Return once
    }

@router.post("/verify")
async def verify_2fa_login(
    request: Verify2FARequest,
    username: str,
    db: Session = Depends(get_db)
):
    """Verify 2FA during login"""

    user = db.query(User).filter(User.username == username).first()

    if not user or not user.is_2fa_enabled:
        raise HTTPException(status_code=400, detail="2FA not enabled")

    # Try TOTP
    if TwoFactorAuthService.verify_totp(user.totp_secret, request.token):
        return {'verified': True}

    # Try backup code
    backup_codes = db.query(BackupCode).filter(
        BackupCode.user_id == user.id,
        BackupCode.used == False
    ).all()

    for backup_code in backup_codes:
        if TwoFactorAuthService.verify_backup_code(request.token, backup_code.code_hash):
            backup_code.used = True
            backup_code.used_at = datetime.utcnow()
            db.commit()
            return {'verified': True, 'backup_code_used': True}

    raise HTTPException(status_code=401, detail="Invalid 2FA code")

@router.post("/disable")
async def disable_2fa(
    request: DisableSecurity,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Disable 2FA (requires password or backup code)"""

    # Verify password
    if not verify_password(request.password, current_user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid password")

    # Disable 2FA
    current_user.is_2fa_enabled = False
    current_user.totp_secret = None

    # Delete backup codes
    db.query(BackupCode).filter(BackupCode.user_id == current_user.id).delete()

    db.commit()

    return {'message': '2FA disabled'}
```

---

## 2️⃣ Encryption Implementation

### Create: app/encryption.py

```python
from cryptography.fernet import Fernet
import os
import base64

class EncryptionService:
    """Field-level encryption service"""

    def __init__(self):
        key = os.environ.get('FERNET_KEY')
        if not key:
            raise ValueError("FERNET_KEY environment variable not set")
        self.cipher = Fernet(key.encode())

    def encrypt(self, value: str) -> str:
        """Encrypt string"""
        if value is None:
            return None
        return self.cipher.encrypt(value.encode()).decode()

    def decrypt(self, encrypted_value: str) -> str:
        """Decrypt string"""
        if encrypted_value is None:
            return None
        return self.cipher.decrypt(encrypted_value.encode()).decode()

# SQLAlchemy TypeDecorator for transparent encryption
from sqlalchemy.types import TypeDecorator, String

class EncryptedString(TypeDecorator):
    """Encrypted string column type"""
    impl = String
    cache_ok = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.service = EncryptionService()

    def process_bind_param(self, value, dialect):
        """Encrypt before storing"""
        if value is not None:
            return self.service.encrypt(value)
        return value

    def process_result_value(self, value, dialect):
        """Decrypt when retrieving"""
        if value is not None:
            return self.service.decrypt(value)
        return value
```

### Update models to use encryption:

```python
# In app/models.py

from app.encryption import EncryptedString

class User(Base):
    # ... other fields ...

    # Encrypt sensitive fields
    totp_secret = Column(EncryptedString(32), nullable=True)
    phone_number = Column(EncryptedString(20), nullable=True)
    ssn = Column(EncryptedString(20), nullable=True)

class APIKey(Base):
    # ... other fields ...

    # Store hashed, not encrypted (we don't need to decrypt)
    key_hash = Column(String(64), unique=True, nullable=False)
```

### Setup encryption key:

```bash
# Generate key:
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Add to .env:
FERNET_KEY=your_generated_key_here
```

---

## 3️⃣ API Key Management

### Database Schema

```python
# Add to app/models.py

class APIKey(Base):
    __tablename__ = 'api_keys'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    key_hash = Column(String(64), unique=True, nullable=False, index=True)
    key_prefix = Column(String(12), nullable=False)
    name = Column(String(100), nullable=False)
    tier = Column(String(20), default='free')

    rate_limit_per_minute = Column(Integer, default=60)
    rate_limit_per_hour = Column(Integer, default=1000)
    rate_limit_per_day = Column(Integer, default=10000)

    is_active = Column(Boolean, default=True)
    last_used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)

class APIKeyUsage(Base):
    __tablename__ = 'api_key_usage'

    id = Column(Integer, primary_key=True)
    api_key_id = Column(Integer, ForeignKey('api_keys.id'), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    endpoint = Column(String(255), nullable=False)
    status_code = Column(Integer, nullable=False)
    response_time_ms = Column(Integer, nullable=False)
```

### API Key Service

```python
# Create: app/api_key_service.py

import secrets
import hashlib
from datetime import datetime, timedelta

class APIKeyService:

    @staticmethod
    def generate_key():
        """Generate cryptographically secure API key"""
        prefix = "sk_live_" if os.environ.get('ENV') == 'production' else "sk_test_"
        key = secrets.token_urlsafe(32)
        full_key = prefix + key

        key_hash = hashlib.sha256(full_key.encode()).hexdigest()
        key_prefix = full_key[:12]

        return full_key, key_hash, key_prefix

    @staticmethod
    def hash_key(key):
        return hashlib.sha256(key.encode()).hexdigest()

    @staticmethod
    def verify_key(provided_key, stored_hash):
        return secrets.compare_digest(
            APIKeyService.hash_key(provided_key),
            stored_hash
        )

    @staticmethod
    def create_key(user_id, name, tier='free', db=None):
        """Create new API key"""
        full_key, key_hash, key_prefix = APIKeyService.generate_key()

        limits = {
            'free': {'minute': 60, 'hour': 1000, 'day': 10000},
            'pro': {'minute': 300, 'hour': 10000, 'day': 100000},
            'enterprise': {'minute': 1000, 'hour': 50000, 'day': 1000000}
        }
        tier_limits = limits.get(tier, limits['free'])

        api_key = APIKey(
            user_id=user_id,
            key_hash=key_hash,
            key_prefix=key_prefix,
            name=name,
            tier=tier,
            rate_limit_per_minute=tier_limits['minute'],
            rate_limit_per_hour=tier_limits['hour'],
            rate_limit_per_day=tier_limits['day']
        )

        if db:
            db.add(api_key)
            db.commit()

        return {
            'key': full_key,  # Show once!
            'prefix': key_prefix,
            'tier': tier,
            'limits': tier_limits
        }
```

### Rate Limiting with Redis

```python
# Create: app/rate_limiter.py

import redis
import time

class RateLimiter:
    """Token bucket rate limiter"""

    def __init__(self, redis_url='redis://localhost:6379'):
        self.redis = redis.from_url(redis_url, decode_responses=True)

    def check_limit(self, key_hash, max_requests, window_seconds):
        """Check if request allowed"""
        bucket_key = f"rate_limit:{key_hash}:{window_seconds}"

        current_time = time.time()
        window_key = f"{bucket_key}:requests"

        # Remove old requests outside window
        self.redis.zremrangebyscore(
            window_key,
            0,
            current_time - window_seconds
        )

        # Count requests in current window
        request_count = self.redis.zcard(window_key)

        if request_count < max_requests:
            # Add current request
            self.redis.zadd(window_key, {current_time: current_time})
            self.redis.expire(window_key, window_seconds * 2)

            return {
                'allowed': True,
                'remaining': max_requests - request_count - 1,
                'reset_at': int(current_time + window_seconds)
            }
        else:
            return {
                'allowed': False,
                'remaining': 0,
                'reset_at': int(current_time + window_seconds)
            }

# FastAPI dependency
from fastapi import Header, HTTPException, Depends

rate_limiter = RateLimiter()

async def verify_api_key(x_api_key: str = Header(...), db: Session = Depends(get_db)):
    """Verify API key and check rate limits"""

    key_hash = APIKeyService.hash_key(x_api_key)
    api_key = db.query(APIKey).filter_by(key_hash=key_hash, is_active=True).first()

    if not api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Check rate limits
    for max_reqs, window in [
        (api_key.rate_limit_per_minute, 60),
        (api_key.rate_limit_per_hour, 3600),
        (api_key.rate_limit_per_day, 86400)
    ]:
        result = rate_limiter.check_limit(key_hash, max_reqs, window)
        if not result['allowed']:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")

    # Update last used
    api_key.last_used_at = datetime.utcnow()
    db.commit()

    return api_key
```

---

## 4️⃣ Implementation Timeline

### Week 1 (Nov 17-23)
- [ ] Day 1-2: 2FA implementation (TOTP + backup codes)
- [ ] Day 2-3: Encryption service (AES-256-GCM)
- [ ] Day 3-4: API Key management (generation + hashing)
- [ ] Day 5: Rate limiting integration (Redis)
- [ ] Day 5: Testing (50+ test cases)

### Week 2 (Nov 24-30)
- [ ] ML model training setup
- [ ] Database partitioning
- [ ] Full-text search implementation
- [ ] Performance testing

---

## 📚 Documentation & Setup

### .env Configuration
```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/traceo

# Encryption
FERNET_KEY=<output from: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">

# Redis (for rate limiting)
REDIS_URL=redis://localhost:6379/0

# Environment
ENV=development  # or production

# Security
JWT_SECRET=<generate strong secret>
```

### Database Migrations
```bash
# Generate migration for new 2FA fields
alembic revision --autogenerate -m "Add 2FA fields"

# Apply migration
alembic upgrade head

# For API Keys
alembic revision --autogenerate -m "Add API key tables"
alembic upgrade head
```

### Testing Setup
```python
# tests/test_2fa.py

import pytest
from app.two_factor_auth import TwoFactorAuthService

def test_totp_generation():
    secret = TwoFactorAuthService.generate_secret()
    assert len(secret) == 32

def test_totp_verification():
    secret = TwoFactorAuthService.generate_secret()
    totp = pyotp.TOTP(secret)
    token = totp.now()
    assert TwoFactorAuthService.verify_totp(secret, token)

def test_backup_codes():
    codes = TwoFactorAuthService.generate_backup_codes(10)
    assert len(codes) == 10
    assert all(len(c) > 0 for c in codes)
```

---

## ✅ Success Criteria

By end of Week 1:
- ✅ 2FA fully operational (TOTP + backup codes)
- ✅ All sensitive fields encrypted
- ✅ API key system with rate limiting
- ✅ 50+ new test cases passing
- ✅ Documentation complete

---

**Status**: Ready for implementation
**Next**: Start with 2FA service (Day 1)
