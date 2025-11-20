# Quick Start Guide

Welcome to Traceo! This guide will help you get up and running in minutes.

## Table of Contents

- [System Requirements](#system-requirements)
- [Installation](#installation)
  - [One-Click Setup](#one-click-setup)
  - [Manual Setup](#manual-setup)
  - [Docker Setup](#docker-setup)
- [First Steps](#first-steps)
- [Configuration](#configuration)
- [Development Setup](#development-setup)
- [Troubleshooting](#troubleshooting)

## System Requirements

### For Users

- **Windows 10+**, **macOS 10.15+**, or **Linux** (Ubuntu 20.04+)
- **Docker Desktop** (4.0+)
- **2GB RAM** minimum (4GB recommended)
- **2GB disk space** minimum

### For Developers

- **Python 3.11+**
- **Node.js 18+**
- **Docker & Docker Compose**
- **Git**
- **Code editor** (VS Code, PyCharm, etc.)

## Installation

### One-Click Setup

**For Windows:**
1. Download `install.ps1`
2. Right-click and select "Run with PowerShell"
3. Follow the prompts
4. Browser will open to `http://localhost:3000`

**For macOS/Linux:**
1. Open Terminal
2. Run: `bash install.sh`
3. Follow the prompts
4. Browser will open to `http://localhost:3000`

### Manual Setup

#### Step 1: Clone Repository

```bash
git clone https://github.com/yourusername/traceo.git
cd traceo
```

#### Step 2: Copy Environment Configuration

```bash
cp .env.example .env
```

Edit `.env` with your configuration:
- Set email credentials (IMAP/SMTP)
- Set API keys (optional but recommended)
- Adjust database settings if needed

#### Step 3: Start Services

```bash
# Using Docker Compose (Recommended)
docker-compose up -d

# Or using Make
make up

# Or manually
docker-compose -f docker-compose.yml up -d
```

#### Step 4: Access the Application

- **Web UI**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

### Docker Setup

```bash
# Using docker-compose directly
docker-compose up -d

# View logs
docker-compose logs -f backend
docker-compose logs -f frontend

# Stop services
docker-compose down
```

## First Steps

### 1. Access the Web Interface

Visit `http://localhost:3000` and you should see the Traceo dashboard.

### 2. Configure Email Ingestion (Optional)

To automatically fetch emails:

1. Go to **Settings** > **Email Configuration**
2. Enter your IMAP server details:
   - **IMAP Server**: `imap.gmail.com` (for Gmail)
   - **Port**: `993`
   - **Email**: Your email address
   - **App Password**: [Generate app password](#gmail-app-password)
3. Click **Test Connection**
4. Click **Save**

### 3. Test with Demo Data

```bash
# Generate sample phishing emails
python scripts/generate_demo_data.py --count 5

# Or using Make
make demo-data
```

Visit the dashboard to see the demo emails and their risk scores.

### 4. Send Your First Report

1. Find a suspicious email in the dashboard
2. Click **View Details**
3. Review the risk analysis
4. Click **Send Report** to notify authorities
5. Confirm and send

## Configuration

### Environment Variables

Edit `.env` file in the project root:

```bash
# Application
APP_NAME=Traceo
APP_VERSION=1.0.0
DEBUG=false

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/traceo

# Email (IMAP)
IMAP_SERVER=imap.gmail.com
IMAP_PORT=993
IMAP_USER=your-email@gmail.com
IMAP_PASSWORD=your-app-password
IMAP_FOLDER=INBOX

# Email (SMTP)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# Language
DEFAULT_LANGUAGE=en

# Analysis
SCORE_THRESHOLD=50
```

### Gmail App Password

To use Gmail with Traceo:

1. Enable 2-Factor Authentication on Google Account
2. Go to [Google Account Security](https://myaccount.google.com/security)
3. Find "App passwords" (under Security)
4. Select "Mail" and "Windows Computer"
5. Copy the generated password
6. Use in `IMAP_PASSWORD` and `SMTP_PASSWORD`

### API Keys (Optional)

For enhanced functionality:

```bash
# GeoIP Database (free tier)
# Download from: https://www.maxmind.com/en/geolite2
GEOIP_DB_PATH=/app/data/GeoLite2-City.mmdb

# IPInfo.io (optional, for IP reputation)
IPINFO_API_KEY=your_ipinfo_api_key

# AbuseIPDB (optional, for IP reputation)
ABUSEIPDB_API_KEY=your_abuseipdb_api_key
```

## Development Setup

### Prerequisites

```bash
# Python 3.11+
python --version

# Node.js 18+
node --version

# Docker Desktop
docker --version
docker-compose --version
```

### Backend Development

```bash
# Navigate to backend
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements-dev.txt

# Run development server
python -m uvicorn app.main:app --reload

# Run tests
pytest

# Code formatting
black app/
isort app/

# Linting
flake8 app/
mypy app/
```

### Frontend Development

```bash
# Navigate to frontend
cd frontend

# Install dependencies
npm install

# Run development server
npm start

# Run tests
npm test

# Build for production
npm run build
```

### Using Development Docker Compose

```bash
# Start all services with development tools
docker-compose -f docker-compose.dev.yml up -d

# Start with additional tools (pgAdmin, Redis, Adminer)
docker-compose -f docker-compose.dev.yml --profile tools up -d

# Start with API documentation viewer
docker-compose -f docker-compose.dev.yml --profile docs up -d

# View logs
docker-compose -f docker-compose.dev.yml logs -f backend

# Access pgAdmin: http://localhost:5050
# Access Adminer: http://localhost:8080
# Access Swagger UI: http://localhost:8081
```

### Using Make Commands

```bash
# Install dependencies
make install

# Start development servers
make dev

# Run tests
make test

# Run linting
make lint

# Format code
make format

# View all available commands
make help
```

## Common Tasks

### Fetch Emails Manually

```bash
# Using CLI
python backend/app/cli.py connect

# Using API
curl -X POST http://localhost:8000/emails/sync
```

### View Database

**Development with pgAdmin:**
1. Visit http://localhost:5050
2. Login with credentials from `.env`
3. Connect to PostgreSQL server
4. Browse database

**Development with Adminer:**
1. Visit http://localhost:8080
2. Select PostgreSQL
3. Enter connection details
4. Browse database

### Generate Reports

```bash
# CLI
python backend/app/cli.py report --email-id email123

# API
curl -X POST http://localhost:8000/report \
  -H "Content-Type: application/json" \
  -d '{"email_id": "email123"}'
```

### View API Documentation

- Interactive: http://localhost:8000/docs (Swagger UI)
- Alternative: http://localhost:8000/redoc (ReDoc)
- OpenAPI JSON: http://localhost:8000/openapi.json

## Troubleshooting

### Docker Services Won't Start

```bash
# Check if ports are in use
lsof -i :3000  # Frontend
lsof -i :8000  # Backend
lsof -i :5432  # Database

# Force remove containers
docker-compose down -v

# Rebuild and start
docker-compose up --build
```

### Database Connection Error

```bash
# Check database health
docker-compose logs postgres

# Verify DATABASE_URL in .env
# Format: postgresql://user:password@host:port/database

# Reset database
docker-compose down -v
docker-compose up -d postgres
```

### IMAP Connection Fails

1. Check IMAP server address in `.env`
2. Verify email and password (or app password for Gmail)
3. Enable "Less secure apps" for Gmail (if not using app password)
4. Check firewall isn't blocking port 993
5. Test with: `make health-check`

### Frontend Won't Load

```bash
# Check if backend is running
curl http://localhost:8000/health

# Check frontend logs
docker-compose logs frontend

# Clear npm cache
rm -rf frontend/node_modules
cd frontend && npm install
```

### Permission Denied on Linux/Mac

```bash
# Make scripts executable
chmod +x install.sh
chmod +x scripts/*.py
chmod +x backend/app/cli.py

# Run with sudo if needed
sudo bash install.sh
```

## Next Steps

- Read [Implementation Guide](./IMPLEMENTATION.md) for architecture details
- Check [Contributing Guide](./CONTRIBUTING.md) to contribute
- Review [Production Checklist](./PRODUCTION_CHECKLIST.md) before deploying
- Join our community on GitHub Discussions

## Getting Help

- **Issues**: https://github.com/yourusername/traceo/issues
- **Discussions**: https://github.com/yourusername/traceo/discussions
- **Email**: support@traceo.local
- **Documentation**: https://traceo.readthedocs.io

---

**Happy Phishing Detection! 🎣🚫**
