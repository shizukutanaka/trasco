# Traceo v0.2+ Implementation Guide

This document describes the complete implementation of Traceo with IMAP integration, email analysis, and auto-reporting.

## What's New in v0.2+

- ✅ **IMAP Email Fetching** - Connect to any IMAP server
- ✅ **Comprehensive Email Analysis** - SPF/DKIM/DMARC, URL, domain, content
- ✅ **WHOIS/RDAP Lookup** - Get domain registration details
- ✅ **IP Geolocation** - Reverse DNS, GeoIP, ASN lookup
- ✅ **Auto-Reporting** - Send reports to authorities
- ✅ **PostgreSQL Database** - Persistent storage with Docker
- ✅ **CLI Tool** - Command-line interface for automation
- ✅ **Unit & Integration Tests** - Comprehensive test suite
- ✅ **50+ Language Support** - Placeholder translations ready

## Architecture

### Core Components

1. **Email Ingestion** (`email_ingestion.py`)
   - IMAP server connection
   - Email parsing and extraction
   - Database persistence

2. **Email Analyzer** (`email_analyzer.py`)
   - Risk scoring algorithm (0-100)
   - SPF/DKIM/DMARC verification
   - URL and domain analysis
   - Content scanning

3. **Domain Lookup** (`domain_info.py`)
   - WHOIS API queries
   - RDAP fallback
   - Registrar and abuse contact extraction

4. **IP Lookup** (`ip_info.py`)
   - Reverse DNS resolution
   - GeoIP database queries
   - Cloud provider detection
   - Abuse scoring

5. **Reporter** (`reporter.py`)
   - Multi-language report templates
   - SMTP sending via aiosmtplib
   - Recipient determination

### Database Schema

**emails table:**
- id, from_addr, to_addrs, subject, received_date
- score, status (pending/analyzed/reported)
- raw_headers, body, urls, attachments
- domain_info (JSON), created_at, analyzed_at

**reports table:**
- id, email_id, recipient_email, recipient_type
- language, content, status (pending/sent/failed)
- created_at, sent_at

## Scoring Algorithm

**Risk Score (0-100):**

1. Header Analysis (35%)
   - SPF fail: +30
   - DKIM fail: +25
   - DMARC fail: +35
   - Cloud IP: +15

2. URL Analysis (30%)
   - Suspicious TLD: +20
   - Domain pattern: +15

3. Domain Analysis (15%)
   - New domain: +25
   - Suspicious registrar: +20
   - Suspicious country: +15
   - Cloudflare: +10

4. Attachment Analysis (10%)
   - Suspicious type: +20

5. Content Analysis (10%)
   - Phishing phrases: +5 each
   - Unusual formatting: +5

**Risk Levels:**
- 0-20: Safe (Green)
- 21-50: Suspicious (Yellow)
- 51-80: High Risk (Orange)
- 81-100: Critical (Red)

## API Endpoints

### Health & Config
```
GET /health                  Health check
GET /config                  API configuration
GET /translations/{lang}     UI translations
```

### Email Operations
```
GET /emails                  List emails (paginated)
GET /emails/{id}             Get email details
POST /emails/analyze         Analyze pending emails
DELETE /emails/{id}          Delete email
```

### Reporting
```
POST /report                 Send phishing report
GET /reports                 List sent reports
```

### Admin
```
GET /admin/stats             System statistics
POST /admin/ingest           Trigger IMAP ingestion
```

## CLI Commands

```bash
# Email ingestion
traceo-cli connect --server imap.gmail.com --user user@example.com --password <pass>

# Analyze emails
traceo-cli analyze

# List emails
traceo-cli list-emails [--filter pending] [--limit 10]

# Show details
traceo-cli show-email <email-id>

# Send report
traceo-cli report <email-id> [--lang en]

# Statistics
traceo-cli stats

# Health
traceo-cli health
```

## Database Models

Located in `backend/app/models.py`:

- `Email` - Email records with analysis
- `Report` - Abuse report tracking
- `User` - User accounts (future)
- `Configuration` - System settings

## Testing

Run tests with pytest:

```bash
# Unit tests
pytest backend/tests/test_email_analyzer.py -v

# Integration tests
pytest backend/tests/test_api.py -v

# All tests with coverage
pytest --cov=app backend/tests/
```

Test files included:
- `test_email_analyzer.py` - Analyzer unit tests
- `test_api.py` - API endpoint tests
- `conftest.py` - Pytest fixtures

## Deployment

### Docker Compose

```yaml
services:
  postgres:      # PostgreSQL 15
  backend:       # FastAPI
  frontend:      # React
```

Start with:
```bash
docker-compose up -d
```

Access at:
- Frontend: http://localhost:3000
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs

### Environment Variables

```env
DATABASE_URL=postgresql://user:pass@postgres:5432/traceo
IMAP_SERVER=imap.gmail.com
IMAP_USER=your@email.com
IMAP_PASSWORD=app_password

SMTP_SERVER=smtp.gmail.com
SMTP_USER=your@email.com
SMTP_PASSWORD=app_password

DEFAULT_LANG=en
LOG_LEVEL=INFO
```

## Configuration Files

- `.env` - Environment variables
- `docker-compose.yml` - Service orchestration
- `pytest.ini` - Test configuration
- `backend/app/settings.py` - Application settings

## Translation System

Supports 50+ languages:

```
backend/app/locales/
├─ en.json, ja.json, ... (50 files)

frontend/src/i18n/
├─ en.json, ja.json, ... (50 files)

backend/app/templates/abuse/
├─ en.md, ja.md, ... (50+ templates)
```

Generate placeholder translations:
```bash
python scripts/generate_translations.py
```

## Performance Tips

1. **Database Indexing**
   ```sql
   CREATE INDEX idx_emails_status ON emails(status);
   CREATE INDEX idx_emails_score ON emails(score);
   CREATE INDEX idx_emails_received ON emails(received_date DESC);
   ```

2. **Caching**
   - IP lookups cached in memory
   - Translation files loaded at startup
   - WHOIS results cached per deployment

3. **Async Processing**
   - Background email analysis
   - Async SMTP sending
   - Parallel enrichment

## Security Checklist

- [ ] Change default DB password
- [ ] Set strong SMTP credentials
- [ ] Enable HTTPS/TLS
- [ ] Configure CORS properly
- [ ] Set up database backups
- [ ] Enable audit logging
- [ ] Restrict admin endpoints
- [ ] Use strong JWT secrets (when auth added)

## Troubleshooting

### IMAP Connection Failed
- Verify server address and port
- Check username and password
- Ensure app password (not account password)

### No Emails in Dashboard
- Check IMAP ingestion started
- Verify email forwarding configured
- Check logs: `docker-compose logs backend`

### Report Sending Failed
- Verify SMTP configuration
- Check abuse@registrar validity
- Review error message in logs

### Database Issues
- Check PostgreSQL running: `docker-compose logs postgres`
- Reset database: `docker-compose down -v && docker-compose up -d`
- Check connection string in .env

## File Structure

```
traceo/
├─ docker-compose.yml          # Services
├─ install.sh / install.ps1    # 1-click setup
├─ README.md                   # Overview
├─ IMPLEMENTATION.md           # This file
├─ backend/
│  ├─ app/
│  │  ├─ main.py               # FastAPI app
│  │  ├─ models.py             # SQLAlchemy models
│  │  ├─ settings.py           # Configuration
│  │  ├─ database.py           # DB connection
│  │  ├─ email_ingestion.py    # IMAP client
│  │  ├─ email_analyzer.py     # Scoring algorithm
│  │  ├─ domain_info.py        # WHOIS/RDAP
│  │  ├─ ip_info.py            # GeoIP/reverse DNS
│  │  ├─ reporter.py           # SMTP reporter
│  │  ├─ cli.py                # CLI commands
│  │  ├─ locales/              # Translations
│  │  └─ templates/            # Report templates
│  ├─ tests/                   # Test suite
│  ├─ requirements.txt
│  └─ Dockerfile
├─ frontend/
│  ├─ src/
│  │  ├─ App.jsx               # React app
│  │  ├─ i18n/                 # Translations
│  │  └─ components/           # UI components
│  └─ Dockerfile
└─ scripts/
   └─ generate_translations.py
```

## Next Steps

1. **Deploy to Cloud**
   - AWS ECS, Google Cloud Run, Azure Container Instances
   - See `docs/DEPLOYMENT.md`

2. **Add More Languages**
   - Run translation script
   - Update translation files
   - Submit PR

3. **Integrate with Email Services**
   - Gmail API support (v0.3)
   - Microsoft 365 native (v0.3)
   - Webhook support (v1.x)

4. **Enhance Analysis**
   - VirusTotal/URLScan (v0.3)
   - Machine learning (v1.0)
   - Image OCR for phishing (v1.x)

## Support

- 📖 Documentation: See `docs/` folder
- 🐛 Issues: GitHub Issues
- 💬 Discussions: GitHub Discussions
- 🤝 Contributing: See CONTRIBUTING.md
