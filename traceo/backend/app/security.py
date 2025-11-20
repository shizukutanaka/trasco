"""
Security module for Traceo backend.
Handles authentication, authorization, rate limiting, and security headers.
"""

import os
import hmac
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from functools import wraps
from collections import defaultdict
import secrets

from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext


# Security Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# HTTP Bearer security
security = HTTPBearer()


class TokenData:
    """Token payload data"""
    def __init__(self, username: str, scopes: list[str] = None):
        self.username = username
        self.scopes = scopes or []


class User:
    """User model for authentication"""
    def __init__(self, username: str, email: str, disabled: bool = False):
        self.username = username
        self.email = email
        self.disabled = disabled


# Rate Limiter
class RateLimiter:
    """Simple in-memory rate limiter"""

    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.requests: Dict[str, list] = defaultdict()

    def is_allowed(self, client_id: str) -> bool:
        """Check if client is within rate limit"""
        now = datetime.utcnow()
        cutoff = now - timedelta(minutes=1)

        if client_id not in self.requests:
            self.requests[client_id] = []

        # Clean old requests
        self.requests[client_id] = [
            req_time for req_time in self.requests[client_id]
            if req_time > cutoff
        ]

        # Check limit
        if len(self.requests[client_id]) >= self.requests_per_minute:
            return False

        self.requests[client_id].append(now)
        return True

    def get_remaining(self, client_id: str) -> int:
        """Get remaining requests for client"""
        now = datetime.utcnow()
        cutoff = now - timedelta(minutes=1)

        if client_id not in self.requests:
            return self.requests_per_minute

        active = [
            req_time for req_time in self.requests[client_id]
            if req_time > cutoff
        ]

        return max(0, self.requests_per_minute - len(active))


# Global rate limiters
general_limiter = RateLimiter(requests_per_minute=100)
report_limiter = RateLimiter(requests_per_minute=10)
auth_limiter = RateLimiter(requests_per_minute=5)


# Password Functions
def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    return pwd_context.verify(plain_password, hashed_password)


# Token Functions
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, SECRET_KEY, algorithm=ALGORITHM
    )
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """Create JWT refresh token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(
        to_encode, SECRET_KEY, algorithm=ALGORITHM
    )
    return encoded_jwt


def verify_token(token: str) -> TokenData:
    """Verify JWT token and extract user data"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")

        if username is None:
            raise credentials_exception

        token_scopes = payload.get("scopes", [])
        token_data = TokenData(scopes=token_scopes, username=username)

    except JWTError:
        raise credentials_exception

    return token_data


# Dependency Functions
async def get_current_user(
    credentials: HTTPAuthCredentials = Depends(security),
) -> User:
    """Get current authenticated user from token"""
    token = credentials.credentials
    token_data = verify_token(token)

    return User(username=token_data.username)


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Get current active user"""
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


# Rate Limiting Dependency
async def check_rate_limit(client_id: str, limiter: RateLimiter = general_limiter):
    """Check rate limit for client"""
    if not limiter.is_allowed(client_id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded"
        )


# CORS Configuration
def get_cors_config() -> Dict[str, Any]:
    """Get CORS configuration"""
    allowed_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

    return {
        "allow_origins": allowed_origins,
        "allow_credentials": True,
        "allow_methods": ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        "allow_headers": [
            "Content-Type",
            "Authorization",
            "X-Requested-With",
            "Accept",
            "Origin",
        ],
        "expose_headers": [
            "Content-Length",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
        ],
        "max_age": 600,
    }


# Security Headers
def get_security_headers() -> Dict[str, str]:
    """Get security response headers"""
    return {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    }


# API Key Management
class APIKeyManager:
    """Manage API keys for external access"""

    def __init__(self, storage_path: str = "api_keys.json"):
        self.storage_path = storage_path
        self._load_keys()

    def _load_keys(self):
        """Load API keys from storage"""
        import json
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, 'r') as f:
                    self.keys = json.load(f)
            except Exception as e:
                print(f"Error loading API keys: {e}")
                self.keys = {}
        else:
            self.keys = {}

    def _save_keys(self):
        """Save API keys to storage"""
        import json
        try:
            with open(self.storage_path, 'w') as f:
                json.dump(self.keys, f, indent=2)
        except Exception as e:
            print(f"Error saving API keys: {e}")

    def generate_key(self, name: str, scopes: list[str] = None) -> str:
        """Generate new API key"""
        key = f"sk_{secrets.token_urlsafe(32)}"
        key_hash = hashlib.sha256(key.encode()).hexdigest()

        self.keys[key_hash] = {
            "name": name,
            "scopes": scopes or [],
            "created_at": datetime.utcnow().isoformat(),
            "last_used": None,
            "active": True
        }

        self._save_keys()
        return key

    def verify_key(self, key: str) -> tuple[bool, Optional[Dict]]:
        """Verify API key and return metadata"""
        key_hash = hashlib.sha256(key.encode()).hexdigest()

        if key_hash not in self.keys:
            return False, None

        key_data = self.keys[key_hash]

        if not key_data.get("active", False):
            return False, None

        # Update last used
        key_data["last_used"] = datetime.utcnow().isoformat()
        self._save_keys()

        return True, key_data

    def revoke_key(self, key: str) -> bool:
        """Revoke API key"""
        key_hash = hashlib.sha256(key.encode()).hexdigest()

        if key_hash in self.keys:
            self.keys[key_hash]["active"] = False
            self._save_keys()
            return True

        return False


# Input Validation
def sanitize_input(text: str, max_length: int = 1000) -> str:
    """Sanitize user input"""
    if not isinstance(text, str):
        raise ValueError("Input must be string")

    if len(text) > max_length:
        raise ValueError(f"Input exceeds maximum length of {max_length}")

    # Remove potentially dangerous characters
    dangerous_chars = ['<', '>', '{', '}', '\\', '"', "'"]
    for char in dangerous_chars:
        text = text.replace(char, '')

    return text.strip()


def validate_email(email: str) -> bool:
    """Validate email format"""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


# Security Utilities
def get_client_ip(request) -> str:
    """Extract client IP from request"""
    if request.client:
        return request.client.host
    return "unknown"


def log_security_event(event_type: str, details: Dict[str, Any], severity: str = "INFO"):
    """Log security events"""
    timestamp = datetime.utcnow().isoformat()
    message = f"[{timestamp}] {severity} - {event_type}: {details}"
    print(message)  # In production, use proper logging


# Demo credentials for development
DEMO_CREDENTIALS = {
    "admin": hash_password("admin123"),
    "user": hash_password("user123"),
}


def authenticate_user(username: str, password: str) -> Optional[User]:
    """Authenticate user with credentials"""
    if username not in DEMO_CREDENTIALS:
        return None

    if not verify_password(password, DEMO_CREDENTIALS[username]):
        return None

    return User(username=username, email=f"{username}@traceo.local")
