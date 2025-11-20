# Traceo - Quick Deployment Guide

**Get Traceo running in 5 minutes** on your local machine or server.

## Prerequisites

- **Docker & Docker Compose** (recommended)
  - [Install Docker Desktop](https://www.docker.com/products/docker-desktop)
  - Includes both Docker and Docker Compose

- **OR** manual setup:
  - Python 3.9+
  - Node.js 16+
  - PostgreSQL 12+

## Option 1: Docker Compose (Easiest) ⚡

### 1. Clone the Repository

```bash
git clone https://github.com/traceo-org/traceo.git
cd traceo
```

### 2. Configure Environment

```bash
# Copy configuration templates
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env

# Edit if needed (optional - defaults work for local development)
nano backend/.env
nano frontend/.env
```

### 3. Start Services

```bash
# Start all services in the background
docker-compose up -d

# Or view logs while starting
docker-compose up

# View logs for a specific service
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f db
```

### 4. Access Application

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

### 5. First Login

```
Username: admin
Password: admin123
```

## Option 2: Manual Setup (Advanced)

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env

# Initialize database
python -m app.database

# Run server
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Create .env file
cp .env.example .env

# Set API URL
echo "REACT_APP_API_BASE_URL=http://localhost:8000" >> .env

# Start development server
npm start
```

Access at http://localhost:3000

## Verification Checklist

After deployment, verify everything works:

```bash
# Check backend health
curl http://localhost:8000/health
# Expected: {"status":"ok","service":"traceo",...}

# Check frontend (should return HTML)
curl http://localhost:3000
# Should return HTML content

# Check database connection (login required)
curl -X GET http://localhost:8000/admin/stats \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## First-Time Setup Wizard

### 1. Access the Application
Open http://localhost:3000 in your browser

### 2. Configure Email Settings
1. Click **⚙️ Settings** in the header
2. Go to **Email Configuration** tab
3. Configure IMAP settings:
   - Server: `imap.gmail.com` (for Gmail)
   - Port: `993`
   - Username: Your email
   - Password: [App-specific password](https://support.google.com/accounts/answer/185833)
4. Click **Test Connection** to verify
5. Click **Save**

### 3. Create Your First Rule (Optional)
1. Click **📋 Rules** in the header
2. Click **Create First Rule**
3. Example rule:
   - Name: "Block Payment Phishing"
   - Condition: Subject contains "verify payment"
   - Action: Auto Report
4. Save rule

### 4. Monitor System
1. Click **📊 Admin** to view:
   - Total emails and statistics
   - System health status
   - Top phishing sources
   - Database information

## Common Tasks

### Restart Services

```bash
# Restart all services
docker-compose restart

# Restart specific service
docker-compose restart backend
docker-compose restart frontend
```

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service (last 100 lines)
docker-compose logs --tail=100 backend

# In real-time
docker-compose logs -f frontend
```

### Stop Services

```bash
# Stop all services (data persists)
docker-compose stop

# Stop and remove containers (data persists)
docker-compose down

# Remove everything including volumes (WARNING: deletes data)
docker-compose down -v
```

### Access Database

```bash
# PostgreSQL container
docker-compose exec db psql -U postgres -d traceo

# Useful SQL commands
SELECT COUNT(*) FROM email;
SELECT * FROM user_profiles;
SELECT * FROM email_rules WHERE user_id = 1;
```

### View File Structure

```bash
traceo/
├── backend/           # FastAPI application
│   └── app/
│       ├── main.py    # FastAPI app entry
│       ├── models.py  # Database models
│       ├── admin.py   # Admin dashboard
│       └── email_rules.py  # Rules engine
├── frontend/          # React application
│   └── src/
│       ├── components/
│       │   ├── AdminDashboard.jsx
│       │   └── EmailRules.jsx
│       └── App.jsx
├── docker-compose.yml # Services configuration
└── README.md         # Full documentation
```

## Troubleshooting

### Port Already in Use

```bash
# Find what's using port 3000
lsof -i :3000

# Use different ports in docker-compose.yml
# Change:
#   - "3000:3000"  → "3001:3000"
#   - "8000:8000"  → "8001:8000"
```

### Database Connection Error

```bash
# Check database container
docker-compose ps

# Check database logs
docker-compose logs db

# Reinitialize database
docker-compose down
docker-compose up -d

# Or manually create tables
docker-compose exec db psql -U postgres -d traceo -f /init.sql
```

### Cannot Login

```bash
# Reset admin password
docker-compose exec backend python -c "
from app.database import get_db
from app.security import hash_password
from app.user_profiles import UserProfile

db = next(get_db())
user = db.query(UserProfile).filter_by(username='admin').first()
if user:
    user.password = hash_password('admin123')
    db.commit()
"
```

### Email not appearing

1. Check IMAP settings in Settings tab
2. Verify email provider allows IMAP access
3. View backend logs: `docker-compose logs -f backend`
4. Check IMAP inbox is configured correctly

### Rules not executing

1. Verify rule is enabled (toggle in Rules list)
2. Test rule manually: Open Rules > Select rule > Test button
3. Check rule conditions and values
4. View rule match statistics in Rules dashboard

## Performance Tuning

### For Development

```yaml
# docker-compose.yml - Development settings
environment:
  - DEBUG=true
  - DATABASE_POOL_SIZE=5
  - LOG_LEVEL=DEBUG
```

### For Production

```yaml
# Set environment variables
environment:
  - DEBUG=false
  - DATABASE_POOL_SIZE=20
  - LOG_LEVEL=WARNING
  - CORS_ORIGINS=yourdomain.com

# Increase resource limits
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G
```

### Database Optimization

```bash
# Clear old data (older than 180 days)
docker-compose exec backend python -c "
from datetime import datetime, timedelta
from app.database import get_db
from app.models import Email

db = next(get_db())
cutoff = datetime.utcnow() - timedelta(days=180)
count = db.query(Email).filter(Email.created_at < cutoff).delete()
db.commit()
print(f'Deleted {count} old emails')
"

# Rebuild indices
docker-compose exec backend python -c "
from sqlalchemy import text
from app.database import get_db

db = next(get_db())
db.execute(text('REINDEX DATABASE traceo'))
db.commit()
print('Indices rebuilt')
"
```

## Backup & Restore

### Backup Database

```bash
# Backup to SQL file
docker-compose exec db pg_dump -U postgres traceo > backup.sql

# Backup to compressed archive
docker-compose exec db pg_dump -U postgres traceo | gzip > backup.sql.gz

# Backup complete (with volumes)
docker run --rm \
  -v traceo_postgres_data:/data \
  -v $(pwd):/backup \
  postgres:14 \
  tar czf /backup/backup.tar.gz /data
```

### Restore Database

```bash
# From SQL file
docker-compose exec -T db psql -U postgres traceo < backup.sql

# From compressed archive
gunzip -c backup.sql.gz | docker-compose exec -T db psql -U postgres traceo

# From volume backup
docker run --rm \
  -v traceo_postgres_data:/data \
  -v $(pwd):/backup \
  postgres:14 \
  tar xzf /backup/backup.tar.gz -C /
```

## Environment Variables

### Backend (.env)

```
# Database
DATABASE_URL=postgresql://postgres:postgres@db:5432/traceo

# API
API_TITLE=Traceo
API_VERSION=1.0.0
DEBUG=false

# Security
JWT_SECRET=your-secret-key-here
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# CORS
CORS_ORIGINS=http://localhost:3000,yourdomain.com

# Logging
LOG_LEVEL=INFO
```

### Frontend (.env)

```
REACT_APP_API_BASE_URL=http://localhost:8000
REACT_APP_API_TIMEOUT=10000
```

## Deployment Checklist

Before going to production:

- [ ] Change all default passwords
- [ ] Update JWT_SECRET with strong random key
- [ ] Set DEBUG=false
- [ ] Configure CORS_ORIGINS for your domain
- [ ] Set up SSL/TLS certificates
- [ ] Enable database backups
- [ ] Configure logging and monitoring
- [ ] Test email ingestion
- [ ] Verify all API endpoints
- [ ] Load test with expected traffic
- [ ] Document any customizations
- [ ] Set up alerting for errors
- [ ] Create disaster recovery plan

## Production Deployment

### Using Kubernetes

```bash
# Deploy to Kubernetes
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml

# Check status
kubectl get pods
kubectl get services

# View logs
kubectl logs -f deployment/traceo-backend
kubectl logs -f deployment/traceo-frontend
```

### Using Docker Swarm

```bash
# Initialize swarm
docker swarm init

# Deploy stack
docker stack deploy -c docker-compose.yml traceo

# Check services
docker service ls
docker service ps traceo_backend

# Scale services
docker service scale traceo_backend=3
```

### Using Cloud Platforms

**AWS**: Use ECS Fargate with RDS
**GCP**: Use Cloud Run with Cloud SQL
**Azure**: Use Container Instances with Azure Database

## Support & Resources

- **Documentation**: https://github.com/traceo-org/traceo
- **Issues**: https://github.com/traceo-org/traceo/issues
- **Discussions**: https://github.com/traceo-org/traceo/discussions
- **Email**: support@traceo-org (if applicable)

## Next Steps

1. **Configure email integration** (IMAP/SMTP)
2. **Create filtering rules** for common phishing patterns
3. **Set up backups** for your database
4. **Configure monitoring** for production use
5. **Review security settings** in Settings tab
6. **Train users** on how to use Traceo

---

**Ready to deploy? Start with Docker Compose above! 🚀**

For detailed documentation, see [README.md](README.md)
