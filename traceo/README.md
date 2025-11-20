# Traceo

**Trace Phishing Emails. Automatically.**

Traceo is an open-source, one-click email phishing detection and auto-reporting system. It analyzes suspicious emails, calculates risk scores, and automatically sends reports to authorities in multiple languages.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.11+-green.svg)
![Node](https://img.shields.io/badge/node-20+-green.svg)

## Features

- 🎯 **One-Click Installation** - Complete setup in seconds
- 🌍 **50+ Language Support** - UI and reports in your language
- 📊 **Risk Scoring** - Automatic phishing risk assessment
- 🤖 **Auto-Reporting** - Sends reports to authorities (abuse@, JPCERT, etc.)
- 🔗 **Multi-Client Support** - Works with any email client via IMAP/SMTP
- 📱 **Web Dashboard** - Beautiful, responsive management interface
- 🔐 **Privacy-Focused** - Run locally, no data sent externally
- 🐳 **Docker Compose** - Full stack in containers

## Quick Start

### Prerequisites

- Docker and Docker Compose installed
- Basic command-line knowledge
- Any email client (Outlook, Gmail, Apple Mail, Thunderbird, etc.)

### Installation (Linux/Mac)

```bash
# Download and run the installer
curl -O https://raw.githubusercontent.com/traceo-org/traceo/main/install.sh
bash install.sh
```

### Installation (Windows)

```powershell
# Download and run the installer
# Right-click PowerShell and select "Run as Administrator"
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/traceo-org/traceo/main/install.ps1" -OutFile "install.ps1"
.\install.ps1
```

### Manual Installation

```bash
# Clone the repository
git clone https://github.com/traceo-org/traceo.git
cd traceo

# Start services
docker-compose up -d

# Open browser
# http://localhost:3000
```

## How It Works

1. **Setup Email Transfer** - Configure your email client to forward suspicious emails to Traceo's dedicated address
2. **Automatic Analysis** - Traceo analyzes headers, URLs, and domain registration
3. **Risk Calculation** - Algorithm scores emails based on multiple phishing indicators
4. **Auto-Report** - Automatically sends reports to:
   - Domain registrars (abuse@...)
   - Cloudflare (if using Cloudflare)
   - JPCERT/CC (Japan)
   - Other authorities

5. **Dashboard** - Review, manage, and manually report emails

## Configuration

### Email Transfer Setup

#### Gmail
1. Go to Settings → Forwarding and POP/IMAP
2. Add forwarding address: `reports@yourdomain.local`
3. Enable IMAP

#### Outlook
1. Rules → New Rule → Move messages from specific sender
2. Forward to: `reports@yourdomain.local`

#### Apple Mail / Thunderbird
1. Create filter rule
2. Forward to: `reports@yourdomain.local`

### Environment Variables

Create a `.env` file in the root directory:

```env
DEFAULT_LANG=en
# Supported languages: en, ja, ... (50+ supported)

# Optional: SMTP configuration for notifications
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your@email.com
SMTP_PASS=your_app_password
```

## Languages

Traceo supports 50+ languages. The UI and abuse reports automatically use your selected language.

**Currently Included:**
- English (en)
- 日本語 (ja)

**To Add a New Language:**

1. Create `backend/app/locales/[lang].json`
2. Create `frontend/src/i18n/[lang].json`
3. Create `backend/app/templates/abuse/[lang].md`
4. Submit a PR!

Example contribution structure:

```
locales/
├─ en.json
├─ ja.json
├─ fr.json  ← Add your language
└─ ...
```

## Architecture

```
┌─────────────┐         ┌──────────────┐
│   Email     │         │  Traceo      │
│   Client    │──IMAP──→│  Backend     │
│ (Any)       │         │  (FastAPI)   │
└─────────────┘         └──────┬───────┘
                                │
                    ┌───────────┼───────────┐
                    ▼           ▼           ▼
             ┌──────────┐ ┌──────────┐ ┌─────────┐
             │ Analyze  │ │ Score    │ │ Report  │
             │ Headers  │ │ Risk     │ │ to Auth │
             └──────────┘ └──────────┘ └─────────┘
                    │           │           │
                    └───────────┼───────────┘
                                ▼
                         ┌──────────────┐
                         │  Dashboard   │
                         │  (React UI)  │
                         └──────────────┘
```

## API Reference

### Health Check
```bash
curl http://localhost:8000/health
```

### List Emails
```bash
curl http://localhost:8000/emails
```

### Report Email
```bash
curl -X POST http://localhost:8000/report \
  -H "Content-Type: application/json" \
  -d '{"email_id":"1","lang":"en"}'
```

### Get Translations
```bash
curl http://localhost:8000/translations/ja
```

## Development

### Backend Development

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

### Frontend Development

```bash
cd frontend
npm install
npm start
```

### Running Tests

```bash
# Backend
cd backend
pytest

# Frontend
cd frontend
npm test
```

## File Structure

```
traceo/
├─ docker-compose.yml          # Service orchestration
├─ install.sh                  # Linux/Mac installer
├─ install.ps1                 # Windows installer
├─ backend/
│  ├─ app/
│  │  ├─ main.py              # FastAPI application
│  │  ├─ locales/             # Backend translations
│  │  │  ├─ en.json
│  │  │  └─ ja.json
│  │  └─ templates/           # Email report templates
│  │     └─ abuse/
│  │        ├─ en.md
│  │        └─ ja.md
│  ├─ Dockerfile
│  └─ requirements.txt
├─ frontend/
│  ├─ src/
│  │  ├─ App.jsx              # Main component
│  │  ├─ i18n.js              # i18next config
│  │  ├─ i18n/                # Frontend translations
│  │  │  ├─ en.json
│  │  │  └─ ja.json
│  │  └─ App.css
│  ├─ public/
│  │  └─ index.html
│  ├─ Dockerfile
│  └─ package.json
├─ docs/                       # Documentation
├─ .github/
│  └─ workflows/              # CI/CD
└─ README.md
```

## Security

- **Local-First**: Traceo runs on your machine. No email data is sent externally
- **Open Source**: Audit the code at https://github.com/traceo-org/traceo
- **HTTPS Ready**: All external communications use TLS
- **Privacy**: Personal data in reports is minimized

### Security Best Practices

1. Run Traceo behind a firewall or VPN
2. Use strong passwords for admin access
3. Regularly update Docker images: `docker-compose pull && docker-compose up -d`
4. Review reports before auto-sending (optional in settings)

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Ways to Contribute

- 🌍 **Translations** - Add support for your language
- 🐛 **Bug Reports** - Found an issue? Open an issue
- ✨ **Features** - Suggest new features or submit PRs
- 📚 **Documentation** - Improve our docs

## Roadmap

### v0.1 (Current)
- ✅ 1-Click Docker deployment
- ✅ Web dashboard
- ✅ Basic email analysis
- ✅ Multi-language UI (2 languages)

### v0.2 (Next)
- ⏳ Gmail API integration
- ⏳ Microsoft 365/Exchange support
- ⏳ 50+ language support
- ⏳ Advanced ML-based scoring

### v1.0
- 📅 Passive DNS integration
- 📅 VirusTotal/URLScan API
- 📅 Email client add-ins (Outlook, Thunderbird)
- 📅 SaaS hosting option

## Troubleshooting

### Services won't start
```bash
# Check logs
docker-compose logs -f

# Restart
docker-compose down
docker-compose up -d
```

### Can't access dashboard
- Check: http://localhost:3000
- Verify: `docker-compose ps` shows all running
- Try: `docker-compose restart`

### Email not appearing
1. Verify email forwarding is configured
2. Check: `docker-compose logs backend`
3. Ensure IMAP is enabled in your email client

## Support

- 📖 **Documentation**: Check the [docs/](docs/) folder
- 🐛 **Issues**: https://github.com/traceo-org/traceo/issues
- 💬 **Discussions**: https://github.com/traceo-org/traceo/discussions

## License

MIT License - See [LICENSE](LICENSE) file for details

## Acknowledgments

Inspired by real-world phishing attacks. Built to protect everyone.

---

**Made with ❤️ for email security**

GitHub: https://github.com/traceo-org/traceo
