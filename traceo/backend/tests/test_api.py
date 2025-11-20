"""
Integration tests for FastAPI endpoints
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import Base, engine, SessionLocal
from app.models import Email as EmailModel, EmailStatus
from datetime import datetime


@pytest.fixture(scope="function")
def setup_test_db():
    """Setup test database"""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(setup_test_db):
    """Create test client"""
    return TestClient(app)


def test_health_check(client):
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_get_config(client):
    """Test config endpoint"""
    response = client.get("/config")
    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert "version" in data


def test_get_translations(client):
    """Test translations endpoint"""
    response = client.get("/translations/en")
    assert response.status_code == 200
    assert isinstance(response.json(), dict)


def test_get_translations_invalid_lang(client):
    """Test invalid language"""
    response = client.get("/translations/invalid")
    assert response.status_code == 404


def test_list_emails_empty(client):
    """Test list emails when empty"""
    response = client.get("/emails")
    assert response.status_code == 200
    assert response.json() == []


def test_list_emails_with_data(client):
    """Test list emails with data"""
    db = SessionLocal()

    # Create test email
    email = EmailModel(
        id="test-123",
        from_addr="test@example.com",
        to_addrs=["user@example.com"],
        subject="Test Email",
        received_date=datetime.utcnow(),
        score=50,
        status=EmailStatus.PENDING,
        raw_headers="",
        body="Test body",
        urls=["https://example.com"],
    )
    db.add(email)
    db.commit()

    response = client.get("/emails")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["id"] == "test-123"


def test_get_email(client):
    """Test get single email"""
    db = SessionLocal()

    email = EmailModel(
        id="test-456",
        from_addr="sender@example.com",
        to_addrs=["recipient@example.com"],
        subject="Test Email",
        received_date=datetime.utcnow(),
        score=75,
        status=EmailStatus.ANALYZED,
        raw_headers="",
        body="Test body",
        urls=["https://example.com"],
    )
    db.add(email)
    db.commit()

    response = client.get("/emails/test-456")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "test-456"
    assert data["score"] == 75
    assert data["status"] == "analyzed"


def test_get_email_not_found(client):
    """Test get non-existent email"""
    response = client.get("/emails/nonexistent")
    assert response.status_code == 404


def test_delete_email(client):
    """Test delete email"""
    db = SessionLocal()

    email = EmailModel(
        id="test-delete",
        from_addr="test@example.com",
        to_addrs=["user@example.com"],
        subject="To Delete",
        received_date=datetime.utcnow(),
        score=0,
        status=EmailStatus.PENDING,
        raw_headers="",
        body="Delete me",
        urls=[],
    )
    db.add(email)
    db.commit()

    response = client.delete("/emails/test-delete")
    assert response.status_code == 200
    assert response.json()["status"] == "deleted"

    # Verify deletion
    response = client.get("/emails/test-delete")
    assert response.status_code == 404


def test_get_admin_stats(client):
    """Test admin stats endpoint"""
    response = client.get("/admin/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_emails" in data
    assert "analyzed" in data
    assert "reported" in data
