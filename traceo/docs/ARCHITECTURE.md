# Traceo Architecture

## System Overview

Traceo is a containerized, multi-language email phishing detection and auto-reporting system. This document explains its architecture, components, and data flow.

```
┌─────────────────────────────────────────────────────────────────┐
│                     User's Email Client                          │
│            (Outlook, Gmail, Apple Mail, Thunderbird)             │
└────────────┬────────────────────────────────────────────────────┘
             │
             │ Forward suspicious emails
             │
             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    IMAP/SMTP Endpoint                            │
│                  (Email Transfer Layer)                          │
└────────────┬────────────────────────────────────────────────────┘
             │
             │ Fetch emails
             │
             ▼
┌──────────────────────────────────────────────────────────────────┐
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │          Traceo Backend (FastAPI)                        │   │
│  │                                                          │   │
│  │  ┌──────────────────────────────────────────────────┐  │   │
│  │  │  Email Ingestion & Parsing                       │  │   │
│  │  │  - Read IMAP/SMTP                                │  │   │
│  │  │  - Extract headers, URLs, attachments            │  │   │
│  │  │  - Parse MIME structure                          │  │   │
│  │  └──────────────────────────────────────────────────┘  │   │
│  │                          ▼                              │   │
│  │  ┌──────────────────────────────────────────────────┐  │   │
│  │  │  Email Analysis Engine                           │  │   │
│  │  │  - Header analysis (SPF/DKIM/DMARC)             │  │   │
│  │  │  - URL extraction & validation                   │  │   │
│  │  │  - Domain WHOIS lookup                           │  │   │
│  │  │  - Attachment scanning                           │  │   │
│  │  └──────────────────────────────────────────────────┘  │   │
│  │                          ▼                              │   │
│  │  ┌──────────────────────────────────────────────────┐  │   │
│  │  │  Scoring Engine                                  │  │   │
│  │  │  - Risk factor calculation                       │  │   │
│  │  │  - Machine learning model (v2.0+)               │  │   │
│  │  │  - Weighted scoring                              │  │   │
│  │  └──────────────────────────────────────────────────┘  │   │
│  │                          ▼                              │   │
│  │  ┌──────────────────────────────────────────────────┐  │   │
│  │  │  Report Generation & Sending                     │  │   │
│  │  │  - Multi-language template rendering             │  │   │
│  │  │  - WHOIS abuse contact extraction                │  │   │
│  │  │  - SMTP submission to authorities                │  │   │
│  │  └──────────────────────────────────────────────────┘  │   │
│  │                                                          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                   │
│                           │ REST API                             │
│                           │                                       │
└───────────────────────────┼───────────────────────────────────────┘
                            │
                            ▼
              ┌─────────────────────────────┐
              │  Frontend (React + i18next) │
              │                             │
              │  - Email Dashboard          │
              │  - Risk visualization       │
              │  - Manual reporting         │
              │  - Settings management      │
              │  - Language selection       │
              └─────────────────────────────┘
```

## Components

### 1. Email Ingestion Layer

**Location**: `backend/app/main.py` - `ingest_emails()`

**Responsibilities**:
- Monitor IMAP/SMTP endpoint for new emails
- Fetch and parse email messages
- Extract headers, body, and attachments
- Normalize email data into standardized format

**Protocol Support**:
- IMAP (idle, polling)
- SMTP (receive)
- Manual upload (via API)

**Data Model**:
```python
EmailData(
    id: str
    from_addr: str
    to_list: List[str]
    subject: str
    received_date: datetime
    headers: Dict[str, str]
    body: str
    urls: List[str]
    attachments: List[Attachment]
)
```

### 2. Email Analysis Engine

**Location**: `backend/app/analyzer/`

**Subcomponents**:

#### Header Analysis
- Parse `Received:` chain to extract originating IP
- Verify SPF, DKIM, DMARC authentication
- Check for spoofing indicators

#### URL Extraction & Validation
- Extract all URLs from body and HTML
- Identify suspicious TLDs (.top, .click, etc.)
- Decode URL shorteners
- Check against URL blacklists (future: VirusTotal)

#### Domain Analysis
- WHOIS lookup for domain registration details
- Registrar identification
- Abuse contact extraction
- Geolocation of registrant

#### Attachment Scanning
- Identify suspicious MIME types
- Flag known malware signatures (future: ClamAV integration)
- Extract metadata

### 3. Scoring Engine

**Location**: `backend/app/scoring.py`

**Algorithm**:

```
Risk Score = Σ(Factor × Weight)

Factors:
- Domain age < 30 days: +25%
- Suspicious TLD (.top, .click, etc.): +20%
- SPF/DKIM/DMARC fail: +30%
- Cloud hosting IP (GCP, AWS, etc.): +15%
- Known phishing URL: +50%
- Attachment type suspicious: +20%
- Grammar/formatting suspicious: +10%
- [Future] ML model score: ±40%

Final Score: 0-100 (Normalized)
```

**Thresholds**:
- 0-20: Safe (Green)
- 21-50: Suspicious (Yellow)
- 51-80: High Risk (Orange)
- 81-100: Critical (Red)

### 4. Report Generation

**Location**: `backend/app/reporter.py`

**Steps**:
1. Load template for selected language
2. Extract abuse contact from WHOIS
3. Fill template with email details
4. Send via SMTP to:
   - Domain registrar (abuse@...)
   - Cloudflare (if detected)
   - JPCERT/IPA (for Japan)
   - User-configured addresses

**Template System**:
- Located in `backend/app/templates/abuse/`
- One file per language: `en.md`, `ja.md`, etc.
- Variable substitution: `{{domain}}`, `{{url}}`, etc.
- Markdown format for readability

### 5. Frontend Dashboard

**Location**: `frontend/src/`

**Technologies**:
- React 18 with Hooks
- i18next for translations
- Axios for API calls
- TailwindCSS for styling

**Pages**:
- **Email List**: Table of analyzed emails with scores
- **Email Details**: Modal with full analysis results
- **Settings**: Language, auto-report configuration
- **Reports**: History of submitted reports

**Real-time Updates**:
- Polling every 30 seconds (can be optimized with WebSockets)
- User-triggered refresh

## Data Flow

### Email Submission
```
1. User forwards email to reports@traceo.local
2. IMAP/SMTP endpoint receives
3. Email parsed and stored
4. API returns email ID
5. Frontend polls and displays in dashboard
```

### Automatic Reporting
```
1. Email analyzed and scored
2. If score >= threshold:
   a. Load appropriate language template
   b. Extract WHOIS abuse contact
   c. Fill template with details
   d. Send SMTP to registrar + JPCERT
   e. Mark as "reported" in database
3. Frontend shows status update
```

### User Manual Report
```
1. User clicks "Report to Authorities"
2. API generates report with selected language
3. API sends via SMTP
4. Returns confirmation to frontend
5. Email marked as "reported"
```

## Database Schema

**Current**: In-memory (PoC)
**Planned** (v1.0+): PostgreSQL

```sql
CREATE TABLE emails (
    id UUID PRIMARY KEY,
    from_addr VARCHAR(255),
    subject TEXT,
    received_date TIMESTAMP,
    score INT (0-100),
    status ENUM(pending, analyzed, reported, false_positive),
    raw_headers TEXT,
    extracted_urls JSON,
    domain_info JSON,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE reports (
    id UUID PRIMARY KEY,
    email_id UUID REFERENCES emails(id),
    recipient TEXT (abuse@..., report@jpcert, etc),
    language VARCHAR(10),
    content TEXT,
    status ENUM(sent, failed, pending),
    sent_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE users (
    id UUID PRIMARY KEY,
    username VARCHAR(255) UNIQUE,
    password_hash VARCHAR(255),
    language VARCHAR(10),
    auto_report BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);
```

## Security Architecture

### Data Protection
- All email data stored locally (option to encrypt at rest)
- No external data transmission except abuse reports
- TLS 1.3 for all network communication
- CORS properly configured

### Authentication (Future)
- JWT-based API authentication
- OAuth2 for email provider integration
- Role-based access control (RBAC)

### Audit Trail
- All actions logged
- Report history maintained
- Failed send attempts tracked

## Scalability Considerations

### Current (PoC)
- Single container per service
- In-memory email storage
- Suitable for single user/small team

### Future (v1.0+)
- Horizontal scaling with Docker Swarm/Kubernetes
- PostgreSQL for persistence
- Redis for caching and queue
- Separate workers for email processing
- Message queue (RabbitMQ/Celery) for async reporting

## Deployment Models

### Local (Current)
```
User Machine
└── Docker Compose
    ├── FastAPI Backend
    ├── React Frontend
    └── [Optional] PostgreSQL
```

### Docker Swarm
```
Swarm Manager
├── Backend Service (replicas=3)
├── Frontend Service (replicas=2)
├── PostgreSQL (persistent volume)
└── Redis Cache
```

### Kubernetes (Future)
```
K8s Cluster
├── Backend Deployment (HPA enabled)
├── Frontend Deployment
├── PostgreSQL StatefulSet
├── Redis Pod
└── Ingress Controller
```

## Error Handling

**Email Parsing Errors**: Logged, user notified, email marked as "parse_error"

**SMTP Failures**: Retry with exponential backoff, max 3 attempts

**WHOIS Lookup Failures**: Skip sending to registrar, alert user

**API Errors**: Return appropriate HTTP status codes with error details

## Logging & Monitoring

**Log Levels**:
- DEBUG: Detailed diagnostic info
- INFO: General information
- WARNING: Warning messages
- ERROR: Error messages
- CRITICAL: Critical failures

**Monitoring** (Future):
- Prometheus metrics
- Grafana dashboards
- Health check endpoints
- Error rate tracking

## Future Enhancements

1. **Gmail API Integration** - Direct Gmail read access (v0.2)
2. **VirusTotal/URLScan** - External URL scanning (v0.2)
3. **ML-based Scoring** - Tensorflow model (v1.0)
4. **Email Add-ins** - Outlook/Thunderbird plugins (v1.0)
5. **Multi-tenant SaaS** - Hosted version (v1.x)
6. **Passive DNS** - Historical DNS resolution (v1.0)
7. **Image OCR** - Phishing in images (v1.x)
