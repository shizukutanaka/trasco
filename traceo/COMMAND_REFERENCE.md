# Traceo - Command Reference Guide

Quick reference for all common Traceo commands and operations.

## 🚀 Quick Start Commands

### Start Everything
```bash
# Start all services in background
docker-compose up -d

# Start and watch logs
docker-compose up

# Start specific service
docker-compose up -d backend
docker-compose up -d frontend
docker-compose up -d db
```

### Stop & Clean Up
```bash
# Stop all services (keeps data)
docker-compose stop

# Stop and remove containers (keeps data)
docker-compose down

# Remove everything including volumes (WARNING: deletes data)
docker-compose down -v

# Restart all services
docker-compose restart

# Restart specific service
docker-compose restart backend
```

## 📋 Service Management

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f db

# Last N lines
docker-compose logs --tail=50 backend
docker-compose logs --tail=100 frontend

# Specific time range
docker-compose logs --since 2025-11-17T10:00:00 backend
```

### Execute Commands in Containers
```bash
# Python shell in backend
docker-compose exec backend python

# Package management
docker-compose exec backend pip install package-name

# Database operations
docker-compose exec db psql -U postgres -d traceo

# Frontend npm
docker-compose exec frontend npm install
docker-compose exec frontend npm test
```

### Check Service Status
```bash
# List all containers
docker-compose ps

# Container health
docker-compose ps --format "table {{.Service}}\t{{.Status}}"

# Detailed service info
docker-compose stats

# Network information
docker network ls
docker-compose exec backend ifconfig
```

## 🗄️ Database Commands

### PostgreSQL Access
```bash
# Connect to database
docker-compose exec db psql -U postgres -d traceo

# List tables
\dt

# Show table structure
\d email
\d email_rules
\d user_profiles

# Exit
\q
```

### Database Operations
```bash
# Count emails
docker-compose exec db psql -U postgres -d traceo -c "SELECT COUNT(*) FROM email;"

# List users
docker-compose exec db psql -U postgres -d traceo -c "SELECT id, username, email FROM user_profiles;"

# List rules
docker-compose exec db psql -U postgres -d traceo -c "SELECT id, user_id, name FROM email_rules;"

# List webhooks
docker-compose exec db psql -U postgres -d traceo -c "SELECT id, name, enabled FROM webhooks;"

# Delete old emails (90+ days)
docker-compose exec db psql -U postgres -d traceo -c \
  "DELETE FROM email WHERE created_at < CURRENT_DATE - INTERVAL '90 days';"

# Backup database
docker-compose exec db pg_dump -U postgres traceo > backup.sql

# Restore database
docker-compose exec -T db psql -U postgres traceo < backup.sql
```

## 🧪 Testing Commands

### Run Tests
```bash
# All tests
docker-compose exec backend pytest

# Specific test file
docker-compose exec backend pytest tests/test_admin_and_rules.py

# Specific test class
docker-compose exec backend pytest tests/test_admin_and_rules.py::TestAdminStats

# Specific test
docker-compose exec backend pytest tests/test_admin_and_rules.py::TestAdminStats::test_get_stats

# With verbose output
docker-compose exec backend pytest -v

# With coverage
docker-compose exec backend pytest --cov=app

# Show print statements
docker-compose exec backend pytest -s
```

## 🔧 Backend Development

### Manual Backend Setup
```bash
# Create virtual environment
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env

# Run server with auto-reload
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run with different host/port
python -m uvicorn app.main:app --host localhost --port 8001

# Run in background (Linux/Mac)
nohup python -m uvicorn app.main:app > server.log 2>&1 &
```

### Code Quality
```bash
# Format code
docker-compose exec backend black app/

# Lint code
docker-compose exec backend pylint app/

# Type checking
docker-compose exec backend mypy app/

# All checks
docker-compose exec backend bash -c "black app/ && pylint app/ && mypy app/"
```

## 💻 Frontend Development

### Manual Frontend Setup
```bash
# Install dependencies
cd frontend
npm install

# Start development server
npm start

# Build for production
npm build

# Run tests
npm test

# Lint code
npm run lint

# Format code
npm run format
```

### Environment Configuration
```bash
# .env file
cat > frontend/.env <<EOF
REACT_APP_API_BASE_URL=http://localhost:8000
REACT_APP_API_TIMEOUT=10000
REACT_APP_DEBUG=true
EOF
```

## 🌐 API Endpoints (curl Examples)

### Authentication
```bash
# Login
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'

# Get token from login response, then use:
TOKEN="eyJ0eXAiOiJKV1QiLCJhbGc..."

# Get current user
curl -X GET http://localhost:8000/auth/me \
  -H "Authorization: Bearer $TOKEN"

# Logout
curl -X POST http://localhost:8000/auth/logout \
  -H "Authorization: Bearer $TOKEN"
```

### Admin Endpoints
```bash
# Get system stats
curl -X GET http://localhost:8000/admin/stats \
  -H "Authorization: Bearer $TOKEN"

# Get system health
curl -X GET http://localhost:8000/admin/health \
  -H "Authorization: Bearer $TOKEN"

# Get trends (30 days)
curl -X GET "http://localhost:8000/admin/trends?days=30" \
  -H "Authorization: Bearer $TOKEN"

# Get top senders
curl -X GET "http://localhost:8000/admin/top-senders?limit=10" \
  -H "Authorization: Bearer $TOKEN"

# Get top domains
curl -X GET "http://localhost:8000/admin/top-domains?limit=10" \
  -H "Authorization: Bearer $TOKEN"

# Rebuild indices
curl -X POST http://localhost:8000/admin/rebuild-indices \
  -H "Authorization: Bearer $TOKEN"

# Cleanup old data
curl -X POST "http://localhost:8000/admin/cleanup-old-data?days_old=90" \
  -H "Authorization: Bearer $TOKEN"
```

### Email Rules
```bash
# List rules
curl -X GET http://localhost:8000/rules/ \
  -H "Authorization: Bearer $TOKEN"

# Create rule
curl -X POST http://localhost:8000/rules/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "name": "Test Rule",
    "conditions": [{"field": "subject", "operator": "contains", "value": "test"}],
    "actions": [{"type": "auto_report", "params": {}}],
    "enabled": true,
    "priority": 50
  }'

# Get rule details
curl -X GET http://localhost:8000/rules/1 \
  -H "Authorization: Bearer $TOKEN"

# Update rule
curl -X PUT http://localhost:8000/rules/1 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"priority": 75}'

# Toggle rule
curl -X POST http://localhost:8000/rules/1/toggle \
  -H "Authorization: Bearer $TOKEN"

# Test rule
curl -X POST "http://localhost:8000/rules/1/test?email_id=email123" \
  -H "Authorization: Bearer $TOKEN"

# Delete rule
curl -X DELETE http://localhost:8000/rules/1 \
  -H "Authorization: Bearer $TOKEN"
```

### Export Endpoints
```bash
# Export emails as CSV
curl -X GET "http://localhost:8000/export/emails/csv" \
  -H "Authorization: Bearer $TOKEN" \
  -o emails.csv

# Export with filters
curl -X GET "http://localhost:8000/export/emails/csv?status_filter=reported&min_score=60" \
  -H "Authorization: Bearer $TOKEN" \
  -o emails_reported.csv

# Export as JSON
curl -X GET "http://localhost:8000/export/emails/json" \
  -H "Authorization: Bearer $TOKEN" \
  -o emails.json

# Export as PDF
curl -X GET "http://localhost:8000/export/emails/pdf" \
  -H "Authorization: Bearer $TOKEN" \
  -o emails.pdf

# Export statistics
curl -X GET "http://localhost:8000/export/statistics" \
  -H "Authorization: Bearer $TOKEN" \
  -o stats.json
```

## 🔄 Development Workflow

### Git Commands
```bash
# Clone repository
git clone https://github.com/traceo-org/traceo.git
cd traceo

# Create feature branch
git checkout -b feature/new-feature

# Make changes and commit
git add .
git commit -m "feat: add new feature"

# Push to remote
git push origin feature/new-feature

# Create pull request on GitHub
# (on GitHub.com)
```

### Docker Image Management
```bash
# Build custom images
docker-compose build

# Build specific service
docker-compose build backend
docker-compose build frontend

# View images
docker images

# Remove unused images
docker image prune

# Tag image for registry
docker tag traceo-backend:latest myregistry/traceo-backend:latest

# Push to registry
docker push myregistry/traceo-backend:latest
```

## 📊 Monitoring & Troubleshooting

### Health Checks
```bash
# Frontend health
curl http://localhost:3000

# Backend health
curl http://localhost:8000/health

# Database health
curl http://localhost:8000/admin/health

# API docs
curl http://localhost:8000/docs
curl http://localhost:8000/redoc
```

### Disk Space
```bash
# Check disk usage
docker system df

# Check container logs size
du -sh /var/lib/docker/containers/

# Cleanup unused data
docker system prune -a
```

### Performance
```bash
# CPU and Memory usage
docker stats

# Container resource limits
docker inspect container-name | grep -A 20 '"HostConfig"'

# Network performance
docker stats --no-stream
```

## 🛠️ Configuration Management

### Environment Variables
```bash
# Update backend .env
cat > backend/.env <<EOF
DATABASE_URL=postgresql://postgres:postgres@db:5432/traceo
DEBUG=false
JWT_SECRET=your-secret-key
CORS_ORIGINS=http://localhost:3000
EOF

# Update frontend .env
cat > frontend/.env <<EOF
REACT_APP_API_BASE_URL=http://localhost:8000
REACT_APP_API_TIMEOUT=10000
EOF
```

### Service Configuration
```bash
# Update docker-compose environment
# Edit docker-compose.yml and set:
# environment:
#   - DEBUG=true
#   - LOG_LEVEL=DEBUG

# Rebuild with new config
docker-compose down
docker-compose build
docker-compose up -d
```

## 📈 Scaling & Production

### Kubernetes Commands
```bash
# Deploy to Kubernetes
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml

# Check status
kubectl get pods
kubectl get services
kubectl get ingress

# View logs
kubectl logs -f deployment/traceo-backend
kubectl logs -f deployment/traceo-frontend

# Scale services
kubectl scale deployment traceo-backend --replicas=3

# Update deployment
kubectl set image deployment/traceo-backend \
  traceo-backend=myregistry/traceo-backend:v1.1.0

# Delete deployment
kubectl delete -f k8s/
```

### Docker Swarm Commands
```bash
# Initialize Swarm
docker swarm init

# Deploy stack
docker stack deploy -c docker-compose.yml traceo

# List services
docker service ls

# Check service status
docker service ps traceo_backend

# Scale service
docker service scale traceo_backend=3

# View logs
docker service logs traceo_backend

# Remove stack
docker stack remove traceo
```

## 🔐 Security Operations

### Password Management
```bash
# Reset admin password
docker-compose exec backend python -c "
from app.security import hash_password
from app.database import SessionLocal
from app.user_profiles import UserProfile

db = SessionLocal()
user = db.query(UserProfile).filter_by(username='admin').first()
if user:
    user.password = hash_password('newpassword123')
    db.commit()
    print('Password updated')
"

# Change admin credentials
# 1. Connect to database
docker-compose exec db psql -U postgres -d traceo

# 2. Update user
UPDATE user_profiles SET email='newemail@example.com'
WHERE username='admin';
```

### Backup & Restore
```bash
# Full backup
docker-compose exec db pg_dump -U postgres traceo > full-backup.sql

# Compressed backup
docker-compose exec db pg_dump -U postgres traceo | gzip > backup.sql.gz

# Backup to file in volume
docker-compose exec -T db pg_dump -U postgres traceo > /var/lib/postgresql/backup.sql

# Restore from backup
docker-compose exec -T db psql -U postgres traceo < backup.sql

# Restore from compressed
gunzip -c backup.sql.gz | docker-compose exec -T db psql -U postgres traceo
```

## 📝 Common Tasks

### Add New User (Database)
```bash
docker-compose exec db psql -U postgres -d traceo <<EOF
INSERT INTO user_profiles (username, email, full_name)
VALUES ('newuser', 'newuser@example.com', 'New User');
EOF
```

### Clear Old Data
```bash
# Delete emails older than 180 days
docker-compose exec db psql -U postgres -d traceo -c \
  "DELETE FROM email WHERE created_at < NOW() - INTERVAL '180 days';"

# Delete old webhook events
docker-compose exec db psql -U postgres -d traceo -c \
  "DELETE FROM webhook_events WHERE created_at < NOW() - INTERVAL '30 days';"
```

### Export Database
```bash
# Full dump
docker-compose exec db pg_dump -U postgres -Fc traceo > backup.dump

# Text format
docker-compose exec db pg_dump -U postgres traceo > backup.sql

# Binary format (smaller)
docker-compose exec db pg_dump -U postgres -Fc -f /tmp/backup.dump traceo && \
  docker cp $(docker-compose ps -q db):/tmp/backup.dump ./backup.dump
```

### Update Translations
```bash
# Edit translation files
nano frontend/src/i18n/en.json
nano frontend/src/i18n/ja.json

# Rebuild frontend
docker-compose exec frontend npm run build

# Restart frontend
docker-compose restart frontend
```

## 🆘 Troubleshooting Commands

### Debug Mode
```bash
# Enable debug logging
docker-compose exec backend python -c "
import logging
logging.basicConfig(level=logging.DEBUG)
print('Debug mode enabled')
"

# View detailed logs
docker-compose logs -f backend --tail=100
docker-compose logs -f frontend --tail=100
```

### Network Troubleshooting
```bash
# Test connectivity between services
docker-compose exec backend ping db
docker-compose exec backend curl -I http://localhost:3000

# Check DNS resolution
docker-compose exec backend nslookup db
docker-compose exec backend getent hosts db
```

### Performance Profiling
```bash
# Memory usage
docker stats --no-stream

# CPU usage
docker stats

# Slow queries
docker-compose exec db psql -U postgres -d traceo -c \
  "SELECT * FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10;"
```

## 📋 Quick Checklist

### Deployment Checklist
- [ ] Clone repository: `git clone ...`
- [ ] Configure environment: Edit `.env` files
- [ ] Start services: `docker-compose up -d`
- [ ] Check status: `docker-compose ps`
- [ ] View logs: `docker-compose logs -f`
- [ ] Access frontend: http://localhost:3000
- [ ] Login: admin / admin123
- [ ] Configure email: Settings → Email Configuration
- [ ] Test email: Send test email
- [ ] Monitor: Admin → Dashboard

### Troubleshooting Checklist
- [ ] Check all containers running: `docker-compose ps`
- [ ] Check logs: `docker-compose logs -f`
- [ ] Verify connectivity: `curl http://localhost:8000/health`
- [ ] Check database: `docker-compose exec db psql ...`
- [ ] Reset services: `docker-compose restart`
- [ ] Rebuild if needed: `docker-compose up -d --build`
- [ ] Check disk space: `docker system df`
- [ ] Clear cache: `docker system prune`

---

**For more detailed information, see README.md and QUICK_DEPLOYMENT.md**
