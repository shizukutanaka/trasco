# Traceo - Complete Feature Showcase

**A production-grade email phishing detection and auto-reporting system**

## 📊 System Overview

Traceo is built with a complete architecture spanning 4 phases of development:

```
Phase 1: Core System (Email Analysis)
    ↓
Phase 2: Production Infrastructure (Docker, K8s, CI/CD)
    ↓
Phase 3: Enterprise Features (Auth, Users, Export)
    ↓
Phase 4: Advanced Features (Admin Dashboard, Rules, Webhooks)
```

## 🎯 Key Features

### 1. **Intelligent Email Analysis**

#### Risk Scoring Algorithm (0-100 Scale)
Analyzes emails using 5 weighted factors:

| Factor | Weight | Checks |
|--------|--------|--------|
| Header Analysis | 35% | SPF, DKIM, DMARC, Cloud Provider Detection |
| URL Analysis | 30% | Suspicious TLDs, URL patterns, Domain validation |
| Domain Info | 15% | Domain age, Registrar reputation, Cloudflare nameservers |
| Attachments | 10% | File type analysis, Suspicious extensions |
| Content | 10% | Phishing phrases, Urgency keywords, Impersonation |

**Example**: Email with DMARC failure + malicious domain + urgent language = 82 points (High Risk)

#### Threat Intelligence Integration
- WHOIS API with RDAP fallback
- IP geolocation and reputation scoring
- Cloud provider identification (Google Cloud, AWS, Azure)
- Registrar abuse contact extraction
- Reverse DNS lookups
- 15+ suspicious TLD detection

**Suspicious TLDs**: .top, .click, .download, .win, .bank, .info, .stream, .cricket, .loan, etc.

### 2. **User Authentication & Management**

#### JWT-Based Authentication
```
Login → Access Token (30 min) + Refresh Token (7 days)
        ↓
        Secure API access with bcrypt password hashing
```

Features:
- Secure token refresh mechanism
- Rate limiting (5 login attempts/minute per IP)
- Password strength validation
- Email verification
- Session tracking
- Audit logging

#### User Profiles & Preferences

**Profile Settings**:
- Full name, email, timezone, language
- Activity tracking (last login, created date)

**Notification Preferences**:
- Email notifications (on/off)
- Push notifications (on/off)
- Digest frequency (daily/weekly/never)

**Analysis Preferences**:
- Risk score threshold (0-100)
- Auto-report settings
- Report recipient emails

**Security Preferences**:
- Blocked senders list
- Trusted domains list
- Two-factor authentication (ready for implementation)

### 3. **Email Rules Engine**

#### Rule Builder with Conditions

Create sophisticated filtering rules with ANY combination of conditions:

**Available Fields**:
- Sender address
- Email subject
- Domain
- Risk score
- URL count
- Email status

**Available Operators**:
- Equals, Contains, Starts with, Ends with
- Greater than, Less than
- In (list matching)
- Regex (pattern matching)

**Example Rule**:
```json
{
  "name": "Block Payment Phishing",
  "conditions": [
    { "field": "subject", "operator": "contains", "value": "verify payment" },
    { "field": "score", "operator": "greater_than", "value": 60 }
  ],
  "actions": ["auto_report", "mark_status"],
  "priority": 80,
  "enabled": true
}
```

#### Automatic Actions

When rule conditions match, execute multiple actions:

1. **Mark Status**: Change email status (reported, pending, analyzed, false_positive)
2. **Auto Report**: Automatically report to authorities
3. **Flag for Review**: Flag suspicious emails
4. **Delete Email**: Remove email from inbox
5. **Add Label**: Tag email with label
6. **Block Sender**: Add to blocked senders list
7. **Trust Domain**: Add domain to trusted list

**Rule Statistics**:
- Track how many times each rule triggered
- Monitor rule effectiveness
- Test rules against emails before enabling

### 4. **Admin Dashboard**

#### System Monitoring

**Overview Tab**:
```
┌─────────────────────────────────────────┐
│ Total Emails: 234    High Risk: 46      │
│ Reports Pending: 8   Avg Risk Score: 45 │
│                                         │
│ Email Distribution:                     │
│ Pending: 45  Analyzed: 156  Reported: 25│
│                                         │
│ Risk Distribution: [|||||||||||||||||||]│
│ Critical: 12  High: 34  Medium: 78  Low:110
└─────────────────────────────────────────┘
```

**Health Tab**:
```
System Status: ✓ Healthy
- Database: ✓ Healthy (Connected)
- Tables: ✓ Healthy (Accessible)
- API: ✓ Healthy (Responding)
Last Check: 2025-11-17 14:32:15 UTC
```

**Threats Tab**:
```
Top Senders by Frequency:
1. phisher@malicious.com - 23 emails (Avg Risk: 82)
2. another@phishing.top - 18 emails (Avg Risk: 74)
3. spam@dangerous.click - 15 emails (Avg Risk: 68)

Top Domains:
1. malicious.com - 42 emails (Avg: 85, Max: 95)
2. phishing.top - 31 emails (Avg: 72, Max: 89)
3. dangerous.click - 28 emails (Avg: 68, Max: 92)
```

**Maintenance Tab**:
```
Database Maintenance
├─ Rebuild Indices (Optimize performance)
└─ Cleanup Old Data
   ├─ Delete 30+ days
   ├─ Delete 90+ days
   └─ Delete 180+ days
```

### 5. **Data Export**

#### Multiple Export Formats

**CSV Export** (Basic & Detailed):
```
id,from_addr,subject,score,status
1,phisher@malicious.com,Verify Account,85,reported
2,another@phishing.top,Payment Confirm,72,analyzed
```

**JSON Export** (With Metadata):
```json
{
  "metadata": {
    "exported_at": "2025-11-17T14:32:15",
    "count": 234
  },
  "emails": [
    {
      "id": "1",
      "from": "phisher@malicious.com",
      "score": 85,
      "status": "reported",
      "urls": ["http://malicious.com/verify"]
    }
  ]
}
```

**PDF Export** (Formatted Report):
```
═══════════════════════════════════════
Email Analysis Report
Exported: 2025-11-17 14:32:15 UTC
═══════════════════════════════════════

Total Emails: 234
Critical (80+): 12
High (60-79): 34
Medium (40-59): 78
Low (<40): 110

[Email Details Table with formatting]
```

**Query Filtering**:
```
GET /export/emails/csv?
  status_filter=reported&
  min_score=60&
  max_score=100&
  detailed=true
```

### 6. **Multi-Language Support**

Currently Available: English, Japanese
Structure prepared for: 50+ languages

**Translation Keys** (250+ strings):
```
├─ common (navigation, buttons)
├─ emails (email-related UI)
├─ status (status labels)
├─ risk (risk level labels)
├─ settings (configuration)
├─ dashboard (statistics)
├─ adminDashboard (admin UI)
├─ emailRules (rules UI)
├─ export (export UI)
├─ auth (authentication)
├─ profile (user profile)
├─ messages (notifications)
└─ validation (error messages)
```

**Language Switching**: Real-time UI update with localStorage persistence

### 7. **Webhook & Notification System** (Phase 5 - Ready)

#### Event Triggering

Configure webhooks to receive notifications for:
- Rule triggered
- High-risk email detected
- Email flagged
- Email reported
- System alerts

#### Webhook Configuration

```json
{
  "name": "Slack Notifications",
  "url": "https://hooks.slack.com/services/...",
  "events": ["high_risk_detected", "rule_triggered"],
  "enabled": true,
  "secret": "webhook-secret-key",
  "retry_count": 3,
  "timeout_seconds": 10
}
```

#### Webhook Security

- HMAC-SHA256 signature verification
- Configurable retry logic (0-10 attempts)
- Event delivery logging
- Success/failure statistics

### 8. **Security Features**

#### Authentication & Authorization
- JWT token-based authentication
- bcrypt password hashing
- User isolation (each user sees own data)
- Role-based access control (ready for implementation)

#### Input Validation
- Pydantic model validation
- Type checking and bounds validation
- Email format validation
- SQL injection prevention via ORM

#### Rate Limiting
```
/auth/login: 5 requests/minute per IP
/reports/send: 10 requests/minute per IP
General API: 100 requests/minute per IP
```

#### Security Headers
```
Content-Security-Policy: default-src 'self'
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
Strict-Transport-Security: max-age=31536000
```

#### Audit Logging
- Login/logout events
- Profile changes
- Settings updates
- Security preference changes
- Admin operations
- Data deletion (GDPR)

### 9. **Performance & Scalability**

#### Backend Performance
- Email analysis: <500ms per email
- WHOIS lookup: 1-2s (with caching)
- Database query: <100ms
- API response time: <200ms average

#### Horizontal Scaling
```
Load Balancer
    ↓
[Backend 1] [Backend 2] [Backend 3]
    ↓         ↓           ↓
    └─────┬───┬───────────┘
          ↓
   PostgreSQL with connection pooling
```

#### Caching Strategy
- Domain lookup results cached
- User preferences cached in memory
- Rule evaluation optimized
- Frequently accessed stats cached

### 10. **Database Schema**

#### Main Tables (4 + 2 optional)

**Email** (Core)
```
- id, from_addr, to_addrs, subject
- body, raw_headers
- score (0-100), status
- urls[], analysis (JSON)
- domain_info, ip_info
- received_date, created_at, updated_at
- reported_at, flagged, deleted
```

**Report** (Core)
```
- id, email_id
- recipient_email, status
- created_at, sent_at
- delivery_status, error_message
```

**UserProfile** (Core)
```
- id, username, email, full_name
- language, theme, timezone
- Notification preferences (JSON)
- Analysis preferences (JSON)
- Security preferences (JSON)
- Custom rules (JSON)
- created_at, updated_at, last_login
```

**EmailRule** (Core)
```
- id, user_id, name, description
- conditions[] (JSON), actions[] (JSON)
- enabled, priority, matched_count
- created_at, updated_at
```

**Webhook** (Optional)
```
- id, user_id, name, url
- events[], enabled, secret
- retry_count, timeout_seconds
- successful_deliveries, failed_deliveries, last_delivery
- created_at, updated_at
```

**WebhookEvent** (Optional - Logging)
```
- id, webhook_id, event_type
- payload (JSON), status_code, response
- retry_count, success
- created_at
```

## 🚀 Deployment Architectures

### Single Server (Development)
```
Server
├─ Docker Container (Backend)
├─ Docker Container (Frontend)
└─ Docker Container (PostgreSQL)
```

### Load Balanced (Production)
```
Load Balancer (nginx/HAProxy)
├─ Backend Server 1
├─ Backend Server 2
├─ Backend Server 3
├─ Frontend Server 1
├─ Frontend Server 2
└─ PostgreSQL (Primary + Replicas)
```

### Kubernetes (Cloud)
```
Kubernetes Cluster
├─ Backend Deployment (3 replicas)
├─ Frontend Deployment (2 replicas)
├─ PostgreSQL StatefulSet
├─ Redis Cache (optional)
└─ Ingress (nginx)
```

## 📈 API Endpoints Summary

### Authentication (7 endpoints)
- POST /auth/login
- POST /auth/token/refresh
- POST /auth/logout
- GET /auth/me
- POST /auth/change-password
- POST /auth/verify-email
- GET /auth/health-check

### User Management (8 endpoints)
- GET /users/me/profile
- PUT /users/me/profile
- PUT /users/me/preferences
- POST /users/me/preferences/notifications
- POST /users/me/preferences/analysis
- POST /users/me/preferences/security
- GET /users/me/activity
- DELETE /users/me/data

### Export (7 endpoints)
- GET /export/emails/csv
- GET /export/emails/json
- GET /export/emails/pdf
- GET /export/reports/csv
- GET /export/reports/json
- GET /export/statistics
- GET /export/summary

### Admin Dashboard (9 endpoints)
- GET /admin/stats
- GET /admin/health
- GET /admin/trends
- GET /admin/top-senders
- GET /admin/top-domains
- POST /admin/rebuild-indices
- POST /admin/cleanup-old-data
- POST /admin/rescan-email/{email_id}
- GET /admin/dashboard-summary

### Email Rules (8 endpoints)
- GET /rules/
- POST /rules/
- GET /rules/{rule_id}
- PUT /rules/{rule_id}
- DELETE /rules/{rule_id}
- POST /rules/{rule_id}/toggle
- POST /rules/{rule_id}/test
- GET /rules/stats/summary

### Webhooks (6 endpoints)
- GET /webhooks/
- POST /webhooks/
- GET /webhooks/{webhook_id}
- PUT /webhooks/{webhook_id}
- DELETE /webhooks/{webhook_id}
- POST /webhooks/{webhook_id}/test
- GET /webhooks/{webhook_id}/events
- GET /webhooks/stats/summary

**Total: 45+ API endpoints**

## 🔄 Workflow Examples

### Example 1: High-Risk Email Detection & Auto-Report

```
1. Email arrives via IMAP
   ↓
2. Traceo analyzes email
   - Header checks: DMARC failed ✓
   - URL analysis: malicious domain ✓
   - Domain lookup: 1-day-old ✓
   - Result: 82 risk score (HIGH)
   ↓
3. Rule evaluation
   - Rule: "Auto-report emails > 70"
   - Conditions match: YES
   ↓
4. Rule actions execute
   - Mark as "reported"
   - Send to authorities
   - Add to blocked senders
   ↓
5. Admin sees statistics
   - Top threats dashboard
   - Rule match count increases
```

### Example 2: Custom Filtering Rule

```
Admin creates rule:
├─ Name: "Block Payment Phishing"
├─ Condition 1: Subject contains "verify payment"
├─ Condition 2: Risk score > 60
└─ Action: Auto-report + Mark as reported

When matching email arrives:
1. Both conditions evaluated
2. Email matches pattern
3. Actions execute immediately
4. Report sent to authorities
5. Statistics updated
```

### Example 3: Data Export Workflow

```
User clicks "Export" button
   ↓
Selects format (CSV/JSON/PDF)
   ↓
Applies filters (high-risk emails only)
   ↓
System generates file
   ↓
Browser downloads file
   ↓
User imports to analysis tool
```

## 🔐 Security Architecture

```
API Gateway
    ↓
Rate Limiter (5/min per IP)
    ↓
Authentication (JWT validation)
    ↓
Authorization (User isolation)
    ↓
Input Validation (Pydantic)
    ↓
Database (ORM protection)
    ↓
HTTPS/TLS encryption
    ↓
Audit Logging
```

## 📊 Monitoring & Metrics

### System Metrics
- CPU usage
- Memory usage
- Disk space
- Database connection pool
- API response times
- Error rates
- Cache hit rates

### Application Metrics
- Total emails processed
- Average risk score
- High-risk email count
- Report delivery success rate
- User count
- Rule match count
- Webhook delivery statistics

### Health Checks
- Database connectivity
- Table accessibility
- API responsiveness
- External service availability
- Disk space availability

## 🎯 Testing Coverage

### Unit Tests
- Email analysis algorithm
- Risk score calculation
- Rule condition evaluation
- Password hashing
- Token generation

### Integration Tests
- API endpoint functionality
- Database operations
- Email ingestion pipeline
- Report tracking
- User authentication flow
- Rule execution

### Test Cases (50+ total)
- Happy path scenarios
- Error conditions
- Edge cases
- Boundary values
- Concurrent operations

## 📦 Technology Stack

### Backend
```
FastAPI (async web framework)
SQLAlchemy (ORM)
PostgreSQL (primary database)
SQLite (dev/testing)
Pydantic (validation)
JWT (authentication)
Loguru (structured logging)
```

### Frontend
```
React 18 (UI framework)
Axios (HTTP client)
react-i18next (internationalization)
CSS3 (styling)
```

### Infrastructure
```
Docker (containerization)
Docker Compose (development)
Kubernetes (orchestration)
PostgreSQL (production DB)
Redis (optional caching)
```

### DevOps
```
GitHub Actions (CI/CD)
pytest (testing)
Prometheus (monitoring)
Sentry (error tracking)
```

## 🚀 Getting Started

### Quick Start (5 minutes)
```bash
git clone https://github.com/traceo-org/traceo.git
cd traceo
docker-compose up -d
# Access http://localhost:3000
# Login: admin / admin123
```

### First Setup Steps
1. Configure IMAP in Settings
2. Test email connection
3. Create first rule
4. Monitor in Admin dashboard
5. Export test data

## 🔮 Future Enhancements

### Ready for Implementation
1. **Webhook System** (Code written)
2. **Two-Factor Authentication**
3. **Role-Based Access Control**
4. **Machine Learning Detection**
5. **Advanced Analytics**
6. **Mobile App**
7. **API Rate Limiting Tiers**
8. **Email Client Plugins**

### Planned Features
1. Support for more email providers (OAuth)
2. Calendar integration
3. Bulk operations
4. Custom report templates
5. SIEM integration
6. Threat intelligence feeds
7. Automated threat response
8. Multi-tenant support

## 📞 Support

- **Documentation**: See PHASE1_SUMMARY.md through PHASE4_SUMMARY.md
- **Quick Start**: See QUICK_DEPLOYMENT.md
- **GitHub**: https://github.com/traceo-org/traceo
- **Issues**: https://github.com/traceo-org/traceo/issues

---

**Traceo: Complete Email Phishing Detection & Auto-Reporting System** ✨

Built with ❤️ for email security | MIT License | Open Source
