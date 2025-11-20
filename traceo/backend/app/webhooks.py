"""
Webhook and notification system for Traceo.
Allows sending notifications to external services when events occur.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
import httpx
import json
from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy.orm import Session
from sqlalchemy import Column, String, Integer, Boolean, JSON, DateTime, desc

from app.database import get_db, Base
from app.security import get_current_user


router = APIRouter(prefix="/webhooks", tags=["webhooks"])


# ===== Database Models =====

class Webhook(Base):
    """Webhook configuration database model"""
    __tablename__ = "webhooks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    name = Column(String, index=True)
    url = Column(String, nullable=False)

    # Event triggers
    events = Column(JSON, default=list)  # ['rule_triggered', 'email_flagged', 'high_risk_detected']

    # Configuration
    enabled = Column(Boolean, default=True)
    secret = Column(String, nullable=True)  # For HMAC signing
    retry_count = Column(Integer, default=3)
    timeout_seconds = Column(Integer, default=10)

    # Statistics
    successful_deliveries = Column(Integer, default=0)
    failed_deliveries = Column(Integer, default=0)
    last_delivery = Column(DateTime, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class WebhookEvent(Base):
    """Webhook event delivery log"""
    __tablename__ = "webhook_events"

    id = Column(Integer, primary_key=True, index=True)
    webhook_id = Column(Integer, index=True)
    event_type = Column(String, index=True)
    payload = Column(JSON)
    status_code = Column(Integer, nullable=True)
    response = Column(String, nullable=True)
    retry_count = Column(Integer, default=0)
    success = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


# ===== Enums =====

class WebhookEvent(str, Enum):
    """Supported webhook events"""
    RULE_TRIGGERED = "rule_triggered"
    HIGH_RISK_DETECTED = "high_risk_detected"
    EMAIL_FLAGGED = "email_flagged"
    EMAIL_REPORTED = "email_reported"
    SYSTEM_ALERT = "system_alert"


# ===== Pydantic Models =====

class WebhookCreate(BaseModel):
    """Create webhook"""
    name: str = Field(..., min_length=1, max_length=100)
    url: HttpUrl
    events: List[str] = Field(default_factory=lambda: [WebhookEvent.RULE_TRIGGERED])
    enabled: bool = True
    secret: Optional[str] = None
    retry_count: int = Field(default=3, ge=0, le=10)
    timeout_seconds: int = Field(default=10, ge=5, le=60)


class WebhookUpdate(BaseModel):
    """Update webhook"""
    name: Optional[str] = None
    url: Optional[HttpUrl] = None
    events: Optional[List[str]] = None
    enabled: Optional[bool] = None
    secret: Optional[str] = None
    retry_count: Optional[int] = None
    timeout_seconds: Optional[int] = None


class WebhookResponse(BaseModel):
    """Webhook response"""
    id: int
    name: str
    url: str
    events: List[str]
    enabled: bool
    retry_count: int
    timeout_seconds: int
    successful_deliveries: int
    failed_deliveries: int
    last_delivery: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WebhookPayload(BaseModel):
    """Webhook event payload"""
    event: str
    timestamp: datetime
    user_id: int
    data: Dict[str, Any]


# ===== Webhook Service =====

class WebhookService:
    """Service for sending webhook events"""

    @staticmethod
    async def send_webhook(
        webhook: "Webhook",
        event_type: str,
        payload: Dict[str, Any],
        db: Session
    ) -> bool:
        """
        Send webhook event with retry logic.

        Args:
            webhook: Webhook configuration
            event_type: Type of event
            payload: Event payload
            db: Database session

        Returns:
            True if successful, False otherwise
        """
        if not webhook.enabled or event_type not in webhook.events:
            return False

        # Prepare request
        webhook_payload = {
            "event": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "data": payload
        }

        # Prepare headers
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Traceo/1.0"
        }

        # Add signature if secret is configured
        if webhook.secret:
            import hmac
            import hashlib
            message = json.dumps(webhook_payload)
            signature = hmac.new(
                webhook.secret.encode(),
                message.encode(),
                hashlib.sha256
            ).hexdigest()
            headers["X-Webhook-Signature"] = f"sha256={signature}"

        # Send with retries
        for attempt in range(webhook.retry_count + 1):
            try:
                async with httpx.AsyncClient(
                    timeout=webhook.timeout_seconds
                ) as client:
                    response = await client.post(
                        str(webhook.url),
                        json=webhook_payload,
                        headers=headers
                    )

                    # Log event
                    WebhookService._log_event(
                        webhook_id=webhook.id,
                        event_type=event_type,
                        payload=webhook_payload,
                        status_code=response.status_code,
                        response=response.text if response.status_code >= 400 else None,
                        retry_count=attempt,
                        success=response.status_code < 400,
                        db=db
                    )

                    if response.status_code < 400:
                        # Success
                        webhook.successful_deliveries += 1
                        webhook.last_delivery = datetime.utcnow()
                        db.add(webhook)
                        db.commit()
                        return True

            except httpx.TimeoutException:
                if attempt == webhook.retry_count:
                    webhook.failed_deliveries += 1
                    db.add(webhook)
                    db.commit()
                continue

            except Exception as e:
                if attempt == webhook.retry_count:
                    webhook.failed_deliveries += 1
                    db.add(webhook)
                    db.commit()
                    # Log event
                    WebhookService._log_event(
                        webhook_id=webhook.id,
                        event_type=event_type,
                        payload=webhook_payload,
                        status_code=None,
                        response=str(e),
                        retry_count=attempt,
                        success=False,
                        db=db
                    )
                continue

        return False

    @staticmethod
    def _log_event(
        webhook_id: int,
        event_type: str,
        payload: Dict[str, Any],
        status_code: Optional[int],
        response: Optional[str],
        retry_count: int,
        success: bool,
        db: Session
    ):
        """Log webhook event delivery"""
        event = WebhookEvent(
            webhook_id=webhook_id,
            event_type=event_type,
            payload=payload,
            status_code=status_code,
            response=response,
            retry_count=retry_count,
            success=success
        )
        db.add(event)
        db.commit()


# ===== API Routes =====

@router.get("/", response_model=List[WebhookResponse])
async def list_webhooks(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
    enabled_only: bool = Query(False),
):
    """List all webhooks for current user"""
    query = db.query(Webhook).filter(Webhook.user_id == current_user.id)

    if enabled_only:
        query = query.filter(Webhook.enabled == True)

    webhooks = query.order_by(Webhook.created_at.desc()).all()
    return webhooks


@router.post("/", response_model=WebhookResponse, status_code=status.HTTP_201_CREATED)
async def create_webhook(
    current_user = Depends(get_current_user),
    webhook_data: WebhookCreate = None,
    db: Session = Depends(get_db),
):
    """Create a new webhook"""
    webhook = Webhook(
        user_id=current_user.id,
        name=webhook_data.name,
        url=str(webhook_data.url),
        events=webhook_data.events,
        enabled=webhook_data.enabled,
        secret=webhook_data.secret,
        retry_count=webhook_data.retry_count,
        timeout_seconds=webhook_data.timeout_seconds,
    )

    db.add(webhook)
    db.commit()
    db.refresh(webhook)

    return webhook


@router.get("/{webhook_id}", response_model=WebhookResponse)
async def get_webhook(
    webhook_id: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a specific webhook"""
    webhook = db.query(Webhook).filter(
        Webhook.id == webhook_id,
        Webhook.user_id == current_user.id
    ).first()

    if not webhook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook not found"
        )

    return webhook


@router.put("/{webhook_id}", response_model=WebhookResponse)
async def update_webhook(
    webhook_id: int,
    current_user = Depends(get_current_user),
    webhook_data: WebhookUpdate = None,
    db: Session = Depends(get_db),
):
    """Update a webhook"""
    webhook = db.query(Webhook).filter(
        Webhook.id == webhook_id,
        Webhook.user_id == current_user.id
    ).first()

    if not webhook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook not found"
        )

    # Update fields
    if webhook_data.name:
        webhook.name = webhook_data.name
    if webhook_data.url:
        webhook.url = str(webhook_data.url)
    if webhook_data.events:
        webhook.events = webhook_data.events
    if webhook_data.enabled is not None:
        webhook.enabled = webhook_data.enabled
    if webhook_data.secret is not None:
        webhook.secret = webhook_data.secret
    if webhook_data.retry_count is not None:
        webhook.retry_count = webhook_data.retry_count
    if webhook_data.timeout_seconds is not None:
        webhook.timeout_seconds = webhook_data.timeout_seconds

    webhook.updated_at = datetime.utcnow()

    db.add(webhook)
    db.commit()
    db.refresh(webhook)

    return webhook


@router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook(
    webhook_id: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a webhook"""
    webhook = db.query(Webhook).filter(
        Webhook.id == webhook_id,
        Webhook.user_id == current_user.id
    ).first()

    if not webhook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook not found"
        )

    db.delete(webhook)
    db.commit()


@router.post("/{webhook_id}/test")
async def test_webhook(
    webhook_id: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Test a webhook with sample payload"""
    import asyncio

    webhook = db.query(Webhook).filter(
        Webhook.id == webhook_id,
        Webhook.user_id == current_user.id
    ).first()

    if not webhook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook not found"
        )

    # Send test payload
    test_payload = {
        "test": True,
        "message": "This is a test webhook delivery"
    }

    # Run async operation
    success = asyncio.run(
        WebhookService.send_webhook(
            webhook,
            "test_event",
            test_payload,
            db
        )
    )

    return {
        "webhook_id": webhook_id,
        "success": success,
        "message": "Test webhook sent successfully" if success else "Test failed"
    }


@router.get("/{webhook_id}/events")
async def get_webhook_events(
    webhook_id: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=500),
    success_only: bool = Query(False),
):
    """Get webhook delivery history"""
    webhook = db.query(Webhook).filter(
        Webhook.id == webhook_id,
        Webhook.user_id == current_user.id
    ).first()

    if not webhook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook not found"
        )

    query = db.query(WebhookEvent).filter(WebhookEvent.webhook_id == webhook_id)

    if success_only:
        query = query.filter(WebhookEvent.success == True)

    events = query.order_by(WebhookEvent.created_at.desc()).limit(limit).all()

    return {
        "webhook_id": webhook_id,
        "total_events": len(events),
        "events": [
            {
                "id": e.id,
                "event_type": e.event_type,
                "success": e.success,
                "status_code": e.status_code,
                "retry_count": e.retry_count,
                "created_at": e.created_at.isoformat(),
            }
            for e in events
        ]
    }


@router.get("/stats/summary")
async def get_webhooks_stats(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get webhook statistics"""
    webhooks = db.query(Webhook).filter(Webhook.user_id == current_user.id).all()

    total_successful = sum(w.successful_deliveries for w in webhooks)
    total_failed = sum(w.failed_deliveries for w in webhooks)

    return {
        "total_webhooks": len(webhooks),
        "enabled_webhooks": sum(1 for w in webhooks if w.enabled),
        "total_successful_deliveries": total_successful,
        "total_failed_deliveries": total_failed,
        "success_rate": (
            (total_successful / (total_successful + total_failed) * 100)
            if (total_successful + total_failed) > 0
            else 0
        ),
        "webhooks": [
            {
                "id": w.id,
                "name": w.name,
                "enabled": w.enabled,
                "successful": w.successful_deliveries,
                "failed": w.failed_deliveries,
                "last_delivery": w.last_delivery.isoformat() if w.last_delivery else None,
            }
            for w in webhooks
        ]
    }
