"""
Integration tests for Admin Dashboard and Email Rules features.
Tests all admin and rules API endpoints.
"""

import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.database import get_db, Base, engine
from app.models import Email, EmailStatus
from app.user_profiles import UserProfile
from app.email_rules import EmailRule


# Test fixtures
@pytest.fixture
def db_session():
    """Create test database session"""
    Base.metadata.create_all(bind=engine)
    session = next(get_db())
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db_session):
    """Create test client with database session"""
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(db_session):
    """Create authenticated user and return auth headers"""
    # Create test user
    user = UserProfile(
        username="testuser",
        email="test@example.com",
        full_name="Test User"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    # Mock token (in real app, use actual JWT)
    return {"Authorization": "Bearer test-token"}


@pytest.fixture
def test_emails(db_session):
    """Create test emails"""
    emails = [
        Email(
            from_addr="phisher@malicious.com",
            to_addrs=["user@example.com"],
            subject="Verify Your Account",
            body="Click here to verify",
            score=85,
            status=EmailStatus.ANALYZED,
            urls=["http://malicious.com/verify"],
            received_date=datetime.utcnow() - timedelta(days=2)
        ),
        Email(
            from_addr="another@phishing.top",
            to_addrs=["user@example.com"],
            subject="Payment Confirmation",
            body="Your payment",
            score=72,
            status=EmailStatus.ANALYZED,
            urls=["http://phishing.top/pay"],
            received_date=datetime.utcnow() - timedelta(days=1)
        ),
        Email(
            from_addr="legitimate@company.com",
            to_addrs=["user@example.com"],
            subject="Meeting Tomorrow",
            body="Don't forget",
            score=15,
            status=EmailStatus.PENDING,
            urls=[],
            received_date=datetime.utcnow()
        ),
    ]
    db_session.add_all(emails)
    db_session.commit()
    for email in emails:
        db_session.refresh(email)
    return emails


# ===== Admin Dashboard Tests =====

class TestAdminStats:
    """Test admin statistics endpoint"""

    def test_get_stats(self, client, db_session, test_emails, auth_headers):
        """Test getting system statistics"""
        response = client.get("/admin/stats", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert data["total_emails"] == 3
        assert "emails_by_status" in data
        assert "emails_by_risk_level" in data
        assert "average_risk_score" in data
        assert "total_reports" in data
        assert "reports_by_status" in data
        assert "total_users" in data
        assert "active_users" in data

    def test_stats_empty_database(self, client, auth_headers):
        """Test statistics with empty database"""
        response = client.get("/admin/stats", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert data["total_emails"] == 0
        assert data["average_risk_score"] == 0.0

    def test_risk_level_distribution(self, client, db_session, test_emails, auth_headers):
        """Test risk level distribution calculation"""
        response = client.get("/admin/stats", headers=auth_headers)
        data = response.json()

        risk_levels = data["emails_by_risk_level"]
        assert risk_levels["critical"] == 1  # score >= 80
        assert risk_levels["high"] == 1      # 60-79
        assert risk_levels["medium"] == 0    # 40-59
        assert risk_levels["low"] == 1       # < 40


class TestAdminHealth:
    """Test admin health check endpoint"""

    def test_get_health(self, client, auth_headers):
        """Test getting system health status"""
        response = client.get("/admin/health", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert data["status"] in ["healthy", "degraded", "unhealthy"]
        assert "database" in data
        assert "api" in data
        assert "timestamp" in data
        assert "checks" in data

    def test_health_checks_detail(self, client, auth_headers):
        """Test health check details"""
        response = client.get("/admin/health", headers=auth_headers)
        data = response.json()

        assert "database" in data["checks"]
        assert "status" in data["checks"]["database"]


class TestAdminTrends:
    """Test email trends endpoint"""

    def test_get_trends_default(self, client, db_session, test_emails, auth_headers):
        """Test getting trends with default period"""
        response = client.get("/admin/trends", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert "trends" in data
        assert isinstance(data["trends"], list)
        assert len(data["trends"]) > 0

    def test_trends_structure(self, client, db_session, test_emails, auth_headers):
        """Test trend data structure"""
        response = client.get("/admin/trends?days=30", headers=auth_headers)
        data = response.json()

        trends = data["trends"]
        for trend in trends:
            assert "date" in trend
            assert "count" in trend
            assert "high_risk_count" in trend
            assert "average_score" in trend

    def test_trends_custom_period(self, client, db_session, test_emails, auth_headers):
        """Test trends with custom period"""
        response = client.get("/admin/trends?days=7", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data["trends"]) == 7

    def test_trends_invalid_days(self, client, auth_headers):
        """Test trends with invalid days parameter"""
        response = client.get("/admin/trends?days=366", headers=auth_headers)
        assert response.status_code == 422  # Validation error


class TestAdminTopSenders:
    """Test top senders endpoint"""

    def test_get_top_senders(self, client, db_session, test_emails, auth_headers):
        """Test getting top email senders"""
        response = client.get("/admin/top-senders", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert "top_senders" in data
        assert isinstance(data["top_senders"], list)
        assert len(data["top_senders"]) > 0

    def test_senders_structure(self, client, db_session, test_emails, auth_headers):
        """Test top senders data structure"""
        response = client.get("/admin/top-senders?limit=5", headers=auth_headers)
        data = response.json()

        senders = data["top_senders"]
        for sender in senders:
            assert "sender" in sender
            assert "count" in sender
            assert "average_risk_score" in sender

    def test_senders_limit(self, client, db_session, test_emails, auth_headers):
        """Test limit parameter"""
        response = client.get("/admin/top-senders?limit=1", headers=auth_headers)
        data = response.json()
        assert len(data["top_senders"]) <= 1


class TestAdminTopDomains:
    """Test top domains endpoint"""

    def test_get_top_domains(self, client, db_session, test_emails, auth_headers):
        """Test getting top domains"""
        response = client.get("/admin/top-domains", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert "top_domains" in data
        assert isinstance(data["top_domains"], list)

    def test_domains_structure(self, client, db_session, test_emails, auth_headers):
        """Test top domains data structure"""
        response = client.get("/admin/top-domains?limit=10", headers=auth_headers)
        data = response.json()

        domains = data["top_domains"]
        for domain in domains:
            assert "domain" in domain
            assert "count" in domain
            assert "average_risk_score" in domain
            assert "max_risk_score" in domain

    def test_domains_sorting(self, client, db_session, test_emails, auth_headers):
        """Test domains are sorted by count"""
        response = client.get("/admin/top-domains", headers=auth_headers)
        data = response.json()

        domains = data["top_domains"]
        if len(domains) > 1:
            for i in range(len(domains) - 1):
                assert domains[i]["count"] >= domains[i + 1]["count"]


class TestAdminMaintenance:
    """Test admin maintenance endpoints"""

    def test_rebuild_indices(self, client, auth_headers):
        """Test rebuild indices endpoint"""
        response = client.post("/admin/rebuild-indices", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert "message" in data
        assert "timestamp" in data

    def test_cleanup_old_data(self, client, db_session, test_emails, auth_headers):
        """Test cleanup old data endpoint"""
        response = client.post("/admin/cleanup-old-data?days_old=90", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert "message" in data
        assert "deleted_emails" in data
        assert "deleted_reports" in data
        assert "cutoff_date" in data

    def test_cleanup_old_data_removes_old_emails(self, client, db_session, auth_headers):
        """Test that cleanup actually removes old emails"""
        # Create old email
        old_email = Email(
            from_addr="old@example.com",
            to_addrs=["user@example.com"],
            subject="Old email",
            body="Old",
            score=50,
            status=EmailStatus.PENDING,
            received_date=datetime.utcnow() - timedelta(days=180)
        )
        db_session.add(old_email)
        db_session.commit()

        # Cleanup 90+ days
        response = client.post("/admin/cleanup-old-data?days_old=90", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["deleted_emails"] >= 1

    def test_rescan_email(self, client, db_session, test_emails, auth_headers):
        """Test rescan email endpoint"""
        email_id = test_emails[0].id
        response = client.post(f"/admin/rescan-email/{email_id}", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert "message" in data
        assert "email_id" in data

    def test_rescan_nonexistent_email(self, client, auth_headers):
        """Test rescan nonexistent email"""
        response = client.post("/admin/rescan-email/nonexistent", headers=auth_headers)
        assert response.status_code == 404


class TestAdminDashboardSummary:
    """Test admin dashboard summary endpoint"""

    def test_get_dashboard_summary(self, client, db_session, test_emails, auth_headers):
        """Test getting complete dashboard summary"""
        response = client.get("/admin/dashboard-summary", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert "timestamp" in data
        assert "summary" in data
        assert "health" in data
        assert "top_threats" in data
        assert "statistics" in data

    def test_summary_structure(self, client, db_session, test_emails, auth_headers):
        """Test summary data structure"""
        response = client.get("/admin/dashboard-summary", headers=auth_headers)
        data = response.json()

        summary = data["summary"]
        assert "total_emails" in summary
        assert "high_risk_emails" in summary
        assert "reports_pending" in summary
        assert "total_users" in summary
        assert "average_risk_score" in summary


# ===== Email Rules Tests =====

class TestEmailRulesCreate:
    """Test email rule creation"""

    def test_create_rule(self, client, db_session, auth_headers):
        """Test creating a new rule"""
        rule_data = {
            "name": "Block Phishing",
            "description": "Auto-report phishing emails",
            "conditions": [
                {
                    "field": "subject",
                    "operator": "contains",
                    "value": "verify account"
                }
            ],
            "actions": [
                {
                    "type": "auto_report",
                    "params": {}
                }
            ],
            "enabled": True,
            "priority": 50
        }

        response = client.post("/rules/", json=rule_data, headers=auth_headers)
        assert response.status_code == 201

        data = response.json()
        assert data["name"] == "Block Phishing"
        assert data["enabled"] is True
        assert data["priority"] == 50
        assert len(data["conditions"]) == 1
        assert len(data["actions"]) == 1

    def test_create_rule_missing_name(self, client, auth_headers):
        """Test creating rule without name"""
        rule_data = {
            "conditions": [{"field": "subject", "operator": "contains", "value": "test"}],
            "actions": [{"type": "auto_report", "params": {}}],
        }

        response = client.post("/rules/", json=rule_data, headers=auth_headers)
        assert response.status_code == 422

    def test_create_rule_no_conditions(self, client, auth_headers):
        """Test creating rule without conditions"""
        rule_data = {
            "name": "Test",
            "conditions": [],
            "actions": [{"type": "auto_report", "params": {}}],
        }

        response = client.post("/rules/", json=rule_data, headers=auth_headers)
        assert response.status_code == 400
        assert "condition" in response.json()["detail"].lower()

    def test_create_rule_no_actions(self, client, auth_headers):
        """Test creating rule without actions"""
        rule_data = {
            "name": "Test",
            "conditions": [{"field": "subject", "operator": "contains", "value": "test"}],
            "actions": [],
        }

        response = client.post("/rules/", json=rule_data, headers=auth_headers)
        assert response.status_code == 400
        assert "action" in response.json()["detail"].lower()

    def test_create_rule_duplicate_name(self, client, db_session, auth_headers):
        """Test creating rule with duplicate name"""
        rule1 = {
            "name": "Test Rule",
            "conditions": [{"field": "subject", "operator": "contains", "value": "test"}],
            "actions": [{"type": "auto_report", "params": {}}],
        }

        # Create first rule
        response1 = client.post("/rules/", json=rule1, headers=auth_headers)
        assert response1.status_code == 201

        # Try to create duplicate
        response2 = client.post("/rules/", json=rule1, headers=auth_headers)
        assert response2.status_code == 400


class TestEmailRulesRead:
    """Test email rule reading"""

    def test_list_rules(self, client, db_session, auth_headers):
        """Test listing all rules"""
        # Create test rule
        rule_data = {
            "name": "Test Rule",
            "conditions": [{"field": "subject", "operator": "contains", "value": "test"}],
            "actions": [{"type": "auto_report", "params": {}}],
        }
        client.post("/rules/", json=rule_data, headers=auth_headers)

        response = client.get("/rules/", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_get_rule(self, client, db_session, auth_headers):
        """Test getting a specific rule"""
        rule_data = {
            "name": "Test Rule",
            "conditions": [{"field": "subject", "operator": "contains", "value": "test"}],
            "actions": [{"type": "auto_report", "params": {}}],
        }
        response = client.post("/rules/", json=rule_data, headers=auth_headers)
        rule_id = response.json()["id"]

        response = client.get(f"/rules/{rule_id}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["name"] == "Test Rule"

    def test_get_nonexistent_rule(self, client, auth_headers):
        """Test getting nonexistent rule"""
        response = client.get("/rules/999", headers=auth_headers)
        assert response.status_code == 404


class TestEmailRulesUpdate:
    """Test email rule updates"""

    def test_update_rule(self, client, db_session, auth_headers):
        """Test updating a rule"""
        # Create rule
        rule_data = {
            "name": "Original Name",
            "conditions": [{"field": "subject", "operator": "contains", "value": "test"}],
            "actions": [{"type": "auto_report", "params": {}}],
        }
        response = client.post("/rules/", json=rule_data, headers=auth_headers)
        rule_id = response.json()["id"]

        # Update rule
        update_data = {
            "name": "Updated Name",
            "priority": 75,
        }
        response = client.put(f"/rules/{rule_id}", json=update_data, headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["name"] == "Updated Name"
        assert response.json()["priority"] == 75

    def test_toggle_rule(self, client, db_session, auth_headers):
        """Test toggling rule enabled status"""
        # Create rule
        rule_data = {
            "name": "Test Rule",
            "conditions": [{"field": "subject", "operator": "contains", "value": "test"}],
            "actions": [{"type": "auto_report", "params": {}}],
            "enabled": True,
        }
        response = client.post("/rules/", json=rule_data, headers=auth_headers)
        rule_id = response.json()["id"]

        # Toggle off
        response = client.post(f"/rules/{rule_id}/toggle", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["enabled"] is False

        # Toggle on
        response = client.post(f"/rules/{rule_id}/toggle", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["enabled"] is True


class TestEmailRulesDelete:
    """Test email rule deletion"""

    def test_delete_rule(self, client, db_session, auth_headers):
        """Test deleting a rule"""
        # Create rule
        rule_data = {
            "name": "Test Rule",
            "conditions": [{"field": "subject", "operator": "contains", "value": "test"}],
            "actions": [{"type": "auto_report", "params": {}}],
        }
        response = client.post("/rules/", json=rule_data, headers=auth_headers)
        rule_id = response.json()["id"]

        # Delete rule
        response = client.delete(f"/rules/{rule_id}", headers=auth_headers)
        assert response.status_code == 204

        # Verify deleted
        response = client.get(f"/rules/{rule_id}", headers=auth_headers)
        assert response.status_code == 404


class TestEmailRulesTesting:
    """Test email rule testing functionality"""

    def test_test_rule_matching(self, client, db_session, test_emails, auth_headers):
        """Test rule evaluation"""
        # Create rule that matches high-score emails
        rule_data = {
            "name": "High Risk Rule",
            "conditions": [
                {
                    "field": "score",
                    "operator": "greater_than",
                    "value": 70
                }
            ],
            "actions": [{"type": "auto_report", "params": {}}],
        }
        response = client.post("/rules/", json=rule_data, headers=auth_headers)
        rule_id = response.json()["id"]

        # Test against high-score email
        email_id = test_emails[0].id  # score=85
        response = client.post(
            f"/rules/{rule_id}/test?email_id={email_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["matches"] is True
        assert data["rule_id"] == rule_id

    def test_test_rule_not_matching(self, client, db_session, test_emails, auth_headers):
        """Test rule not matching"""
        # Create rule that doesn't match low-score emails
        rule_data = {
            "name": "High Risk Only",
            "conditions": [
                {
                    "field": "score",
                    "operator": "greater_than",
                    "value": 80
                }
            ],
            "actions": [{"type": "auto_report", "params": {}}],
        }
        response = client.post("/rules/", json=rule_data, headers=auth_headers)
        rule_id = response.json()["id"]

        # Test against low-score email
        email_id = test_emails[2].id  # score=15
        response = client.post(
            f"/rules/{rule_id}/test?email_id={email_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["matches"] is False


# ===== Webhooks Tests =====

class TestWebhooksCreate:
    """Test webhook creation"""

    def test_create_webhook(self, client, db_session, auth_headers):
        """Test creating a webhook"""
        webhook_data = {
            "name": "Test Webhook",
            "url": "https://hooks.slack.com/services/test",
            "events": ["rule_triggered", "high_risk_detected"],
            "enabled": True,
            "retry_count": 3,
            "timeout_seconds": 10,
        }
        response = client.post("/webhooks/", json=webhook_data, headers=auth_headers)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Webhook"
        assert data["url"] == "https://hooks.slack.com/services/test"
        assert "rule_triggered" in data["events"]
        assert data["enabled"] is True

    def test_create_webhook_with_secret(self, client, db_session, auth_headers):
        """Test creating webhook with HMAC secret"""
        webhook_data = {
            "name": "Secure Webhook",
            "url": "https://example.com/webhook",
            "events": ["rule_triggered"],
            "secret": "my-secret-key",
            "retry_count": 5,
            "timeout_seconds": 15,
        }
        response = client.post("/webhooks/", json=webhook_data, headers=auth_headers)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Secure Webhook"

    def test_create_webhook_invalid_url(self, client, db_session, auth_headers):
        """Test creating webhook with invalid URL"""
        webhook_data = {
            "name": "Invalid Webhook",
            "url": "not-a-valid-url",
            "events": ["rule_triggered"],
        }
        response = client.post("/webhooks/", json=webhook_data, headers=auth_headers)
        assert response.status_code == 422

    def test_create_webhook_missing_name(self, client, db_session, auth_headers):
        """Test creating webhook without name"""
        webhook_data = {
            "url": "https://example.com/webhook",
            "events": ["rule_triggered"],
        }
        response = client.post("/webhooks/", json=webhook_data, headers=auth_headers)
        assert response.status_code == 422


class TestWebhooksRetrieval:
    """Test webhook retrieval"""

    def test_list_webhooks(self, client, db_session, auth_headers):
        """Test listing webhooks"""
        # Create webhooks
        for i in range(3):
            webhook_data = {
                "name": f"Webhook {i+1}",
                "url": f"https://example.com/webhook{i+1}",
                "events": ["rule_triggered"],
            }
            client.post("/webhooks/", json=webhook_data, headers=auth_headers)

        # List webhooks
        response = client.get("/webhooks/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        assert data[0]["name"] == "Webhook 1" or data[0]["name"] == "Webhook 3"

    def test_list_webhooks_enabled_only(self, client, db_session, auth_headers):
        """Test listing only enabled webhooks"""
        # Create webhooks
        webhook_data_1 = {
            "name": "Enabled Webhook",
            "url": "https://example.com/webhook1",
            "events": ["rule_triggered"],
            "enabled": True,
        }
        response = client.post("/webhooks/", json=webhook_data_1, headers=auth_headers)
        webhook_id_1 = response.json()["id"]

        webhook_data_2 = {
            "name": "Disabled Webhook",
            "url": "https://example.com/webhook2",
            "events": ["rule_triggered"],
            "enabled": False,
        }
        client.post("/webhooks/", json=webhook_data_2, headers=auth_headers)

        # List enabled only
        response = client.get("/webhooks/?enabled_only=true", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == webhook_id_1

    def test_get_webhook(self, client, db_session, auth_headers):
        """Test retrieving a specific webhook"""
        # Create webhook
        webhook_data = {
            "name": "Test Webhook",
            "url": "https://example.com/webhook",
            "events": ["rule_triggered"],
        }
        response = client.post("/webhooks/", json=webhook_data, headers=auth_headers)
        webhook_id = response.json()["id"]

        # Get webhook
        response = client.get(f"/webhooks/{webhook_id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == webhook_id
        assert data["name"] == "Test Webhook"

    def test_get_nonexistent_webhook(self, client, db_session, auth_headers):
        """Test getting non-existent webhook"""
        response = client.get("/webhooks/9999", headers=auth_headers)
        assert response.status_code == 404


class TestWebhooksUpdate:
    """Test webhook updates"""

    def test_update_webhook(self, client, db_session, auth_headers):
        """Test updating a webhook"""
        # Create webhook
        webhook_data = {
            "name": "Original Name",
            "url": "https://example.com/webhook",
            "events": ["rule_triggered"],
            "retry_count": 3,
        }
        response = client.post("/webhooks/", json=webhook_data, headers=auth_headers)
        webhook_id = response.json()["id"]

        # Update webhook
        update_data = {
            "name": "Updated Name",
            "retry_count": 5,
        }
        response = client.put(f"/webhooks/{webhook_id}", json=update_data, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["retry_count"] == 5

    def test_update_webhook_events(self, client, db_session, auth_headers):
        """Test updating webhook events"""
        # Create webhook
        webhook_data = {
            "name": "Test Webhook",
            "url": "https://example.com/webhook",
            "events": ["rule_triggered"],
        }
        response = client.post("/webhooks/", json=webhook_data, headers=auth_headers)
        webhook_id = response.json()["id"]

        # Update events
        update_data = {
            "events": ["rule_triggered", "high_risk_detected", "email_reported"],
        }
        response = client.put(f"/webhooks/{webhook_id}", json=update_data, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data["events"]) == 3
        assert "email_reported" in data["events"]


class TestWebhooksDelete:
    """Test webhook deletion"""

    def test_delete_webhook(self, client, db_session, auth_headers):
        """Test deleting a webhook"""
        # Create webhook
        webhook_data = {
            "name": "Test Webhook",
            "url": "https://example.com/webhook",
            "events": ["rule_triggered"],
        }
        response = client.post("/webhooks/", json=webhook_data, headers=auth_headers)
        webhook_id = response.json()["id"]

        # Delete webhook
        response = client.delete(f"/webhooks/{webhook_id}", headers=auth_headers)
        assert response.status_code == 204

        # Verify deleted
        response = client.get(f"/webhooks/{webhook_id}", headers=auth_headers)
        assert response.status_code == 404

    def test_delete_nonexistent_webhook(self, client, db_session, auth_headers):
        """Test deleting non-existent webhook"""
        response = client.delete("/webhooks/9999", headers=auth_headers)
        assert response.status_code == 404


class TestWebhooksStatistics:
    """Test webhook statistics"""

    def test_webhooks_stats_summary(self, client, db_session, auth_headers):
        """Test getting webhooks statistics"""
        # Create webhooks
        for i in range(2):
            webhook_data = {
                "name": f"Webhook {i+1}",
                "url": f"https://example.com/webhook{i+1}",
                "events": ["rule_triggered"],
                "enabled": i == 0,
            }
            client.post("/webhooks/", json=webhook_data, headers=auth_headers)

        # Get stats
        response = client.get("/webhooks/stats/summary", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total_webhooks"] == 2
        assert data["enabled_webhooks"] == 1
        assert "success_rate" in data
        assert "webhooks" in data


# ===== Audit Logging Tests =====

class TestAuditLogging:
    """Test audit logging functionality"""

    def test_list_audit_logs(self, client, db_session, auth_headers):
        """Test listing audit logs"""
        response = client.get("/audit/logs", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_list_audit_logs_with_filters(self, client, db_session, auth_headers):
        """Test listing audit logs with filters"""
        # Create some test logs by making API calls
        response = client.get(
            "/audit/logs?action=login&resource_type=user",
            headers=auth_headers
        )
        assert response.status_code == 200

    def test_get_audit_stats(self, client, db_session, auth_headers):
        """Test getting audit statistics"""
        response = client.get("/audit/logs/stats?days=30", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert "period_days" in data
        assert "total_events" in data
        assert "successful" in data
        assert "errors" in data
        assert "warnings" in data
        assert "success_rate" in data

    def test_get_audit_timeline(self, client, db_session, auth_headers):
        """Test getting audit timeline"""
        response = client.get("/audit/logs/timeline?days=30", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert "period_days" in data
        assert "total_events" in data
        assert "timeline" in data

    def test_search_audit_logs(self, client, db_session, auth_headers):
        """Test searching audit logs"""
        response = client.get(
            "/audit/logs/search?query=test",
            headers=auth_headers
        )
        assert response.status_code == 200

        data = response.json()
        assert "query" in data
        assert "total_results" in data
        assert "results" in data

    def test_export_audit_logs_json(self, client, db_session, auth_headers):
        """Test exporting audit logs as JSON"""
        response = client.get(
            "/audit/logs/export?format=json&days=30",
            headers=auth_headers
        )
        assert response.status_code == 200

        data = response.json()
        assert "exported_at" in data
        assert "user_id" in data
        assert "period_days" in data
        assert "total_events" in data
        assert "logs" in data

    def test_export_audit_logs_csv(self, client, db_session, auth_headers):
        """Test exporting audit logs as CSV"""
        response = client.get(
            "/audit/logs/export?format=csv&days=30",
            headers=auth_headers
        )
        assert response.status_code == 200

        data = response.json()
        assert "format" in data
        assert data["format"] == "csv"
        assert "data" in data

    def test_cleanup_old_audit_logs(self, client, db_session, auth_headers):
        """Test cleaning up old audit logs"""
        response = client.delete(
            "/audit/logs/cleanup?days_old=90",
            headers=auth_headers
        )
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "success"
        assert "deleted_count" in data
        assert "cutoff_date" in data


class TestEmailRulesStatistics:
    """Test email rules statistics"""

    def test_rules_summary(self, client, db_session, auth_headers):
        """Test getting rules statistics"""
        response = client.get("/rules/stats/summary", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert "total_rules" in data
        assert "enabled_rules" in data
        assert "total_matches" in data
        assert "rules" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
