# Traceo Deployment Guide

This guide covers various deployment scenarios for Traceo.

## Table of Contents

1. [Local Development](#local-development)
2. [Docker Compose (Recommended)](#docker-compose)
3. [Manual Installation](#manual-installation)
4. [Docker Swarm](#docker-swarm)
5. [Kubernetes](#kubernetes)
6. [Cloud Platforms](#cloud-platforms)

---

## Local Development

### Requirements
- Python 3.11+
- Node.js 20+
- Git

### Backend Setup

```bash
# Clone repository
git clone https://github.com/traceo-org/traceo.git
cd traceo

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r backend/requirements.txt

# Run development server
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

Server runs at `http://localhost:8000`

API docs available at `http://localhost:8000/docs`

### Frontend Setup

```bash
# In another terminal
cd frontend

# Install dependencies
npm install

# Start development server
npm start
```

Frontend runs at `http://localhost:3000`

---

## Docker Compose (Recommended)

### Requirements
- Docker 20.10+
- Docker Compose 2.0+

### Quick Start

```bash
# 1. Clone repository
git clone https://github.com/traceo-org/traceo.git
cd traceo

# 2. Run installer (Linux/Mac)
bash install.sh

# Or on Windows (PowerShell as Administrator)
.\install.ps1
```

### Manual Docker Compose Start

```bash
# Build and start services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Clean up volumes
docker-compose down -v
```

### Customization

Create `.env` file in root directory:

```env
# Default UI language
DEFAULT_LANG=en

# Backend settings
BACKEND_PORT=8000
BACKEND_HOST=0.0.0.0

# Frontend settings
FRONTEND_PORT=3000

# Database (optional, for future versions)
DB_HOST=postgres
DB_NAME=traceo
DB_USER=traceo
DB_PASSWORD=secure_password_here
```

### Access Services

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

---

## Manual Installation

### Requirements
- Python 3.11+
- Node.js 20+
- Nginx or Apache (optional, for reverse proxy)

### Backend Installation

```bash
# Create app directory
mkdir -p /opt/traceo
cd /opt/traceo

# Clone repository
git clone https://github.com/traceo-org/traceo.git .

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt

# Create systemd service
sudo tee /etc/systemd/system/traceo-backend.service > /dev/null <<EOF
[Unit]
Description=Traceo Backend
After=network.target

[Service]
Type=notify
User=www-data
WorkingDirectory=/opt/traceo
ExecStart=/opt/traceo/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000

[Install]
WantedBy=multi-user.target
EOF

# Start service
sudo systemctl daemon-reload
sudo systemctl start traceo-backend
sudo systemctl enable traceo-backend
```

### Frontend Installation

```bash
cd /opt/traceo/frontend

# Install dependencies
npm install

# Build for production
npm run build

# Copy to web server directory
sudo cp -r build/* /var/www/traceo/

# Configure Nginx
sudo tee /etc/nginx/sites-available/traceo > /dev/null <<'EOF'
server {
    listen 80;
    server_name traceo.example.com;

    root /var/www/traceo;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://localhost:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
EOF

# Enable site
sudo ln -s /etc/nginx/sites-available/traceo /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

---

## Docker Swarm

### Initialize Swarm

```bash
# On manager node
docker swarm init

# Get join token for workers
docker swarm join-token worker
```

### Deploy Stack

```bash
# Create production compose file
docker-compose -f docker-compose.yml -f docker-compose.swarm.yml config > swarm-stack.yml

# Deploy stack
docker stack deploy -c swarm-stack.yml traceo
```

### Monitor

```bash
# View services
docker service ls

# View replicas
docker service ps traceo_backend

# Scale service
docker service scale traceo_backend=3
```

---

## Kubernetes

### Requirements
- kubectl 1.24+
- Helm 3.0+ (optional but recommended)

### Helm Chart

```bash
# Add Traceo Helm repo (future)
helm repo add traceo https://traceo-org.github.io/helm-charts

# Install
helm install traceo traceo/traceo \
  --set frontend.replicas=2 \
  --set backend.replicas=3
```

### Manual Kubernetes Deployment

```bash
# Create namespace
kubectl create namespace traceo

# Create ConfigMap for configuration
kubectl create configmap traceo-config \
  --from-literal=DEFAULT_LANG=en \
  -n traceo

# Apply deployments
kubectl apply -f k8s/backend-deployment.yaml -n traceo
kubectl apply -f k8s/frontend-deployment.yaml -n traceo
kubectl apply -f k8s/service.yaml -n traceo
kubectl apply -f k8s/ingress.yaml -n traceo

# Check status
kubectl get pods -n traceo
kubectl get svc -n traceo
```

### Scaling

```bash
# Scale backend to 5 replicas
kubectl scale deployment/traceo-backend --replicas=5 -n traceo

# Auto-scale based on CPU
kubectl autoscale deployment traceo-backend \
  --min=2 --max=10 --cpu-percent=80 -n traceo
```

---

## Cloud Platforms

### AWS ECS/Fargate

```bash
# Create ECR repositories
aws ecr create-repository --repository-name traceo/backend
aws ecr create-repository --repository-name traceo/frontend

# Build and push images
docker build -t traceo/backend:latest ./backend
docker tag traceo/backend:latest [ACCOUNT].dkr.ecr.[REGION].amazonaws.com/traceo/backend:latest
docker push [ACCOUNT].dkr.ecr.[REGION].amazonaws.com/traceo/backend:latest

# Deploy with CloudFormation or Terraform
```

### Google Cloud Run

```bash
# Build image
gcloud builds submit --tag gcr.io/[PROJECT]/traceo-backend ./backend

# Deploy
gcloud run deploy traceo-backend \
  --image gcr.io/[PROJECT]/traceo-backend \
  --platform managed \
  --region us-central1 \
  --port 8000

# Set environment variables
gcloud run services update traceo-backend \
  --update-env-vars DEFAULT_LANG=en
```

### Azure Container Instances

```bash
# Build image
az acr build --registry [REGISTRY] --image traceo:latest ./backend

# Deploy
az container create \
  --resource-group traceo \
  --name traceo-backend \
  --image [REGISTRY].azurecr.io/traceo:latest \
  --ports 8000 \
  --cpu 1 \
  --memory 1
```

### Docker Hub

```bash
# Build image
docker build -t [DOCKERHUB]/traceo:latest .

# Push to registry
docker login
docker push [DOCKERHUB]/traceo:latest

# Run
docker run -d -p 8000:8000 [DOCKERHUB]/traceo:latest
```

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DEFAULT_LANG` | Default UI language | `en` |
| `BACKEND_PORT` | Backend port | `8000` |
| `FRONTEND_PORT` | Frontend port | `3000` |
| `SMTP_SERVER` | SMTP server for notifications | - |
| `SMTP_PORT` | SMTP port | `587` |
| `SMTP_USER` | SMTP username | - |
| `SMTP_PASS` | SMTP password | - |
| `LOG_LEVEL` | Logging level | `info` |
| `WORKERS` | Uvicorn workers | `4` |

---

## Reverse Proxy Configuration

### Nginx

```nginx
server {
    listen 80;
    server_name traceo.example.com;

    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /api/ {
        proxy_pass http://localhost:8000/;
        proxy_set_header Host $host;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### Apache

```apache
<VirtualHost *:80>
    ServerName traceo.example.com
    DocumentRoot /var/www/traceo

    ProxyPreserveHost On
    ProxyPass / http://localhost:3000/
    ProxyPassReverse / http://localhost:3000/

    ProxyPass /api/ http://localhost:8000/
    ProxyPassReverse /api/ http://localhost:8000/
</VirtualHost>
```

---

## SSL/TLS Certificate

### Let's Encrypt with Certbot

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Get certificate
sudo certbot certonly --nginx -d traceo.example.com

# Auto-renew
sudo systemctl enable certbot.timer
sudo systemctl start certbot.timer
```

### Self-Signed Certificate (Development Only)

```bash
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365
```

---

## Troubleshooting

### Services won't start

```bash
# Check logs
docker-compose logs backend
docker-compose logs frontend

# Verify ports are not in use
lsof -i :8000
lsof -i :3000

# Rebuild images
docker-compose build --no-cache
docker-compose up -d
```

### High CPU/Memory usage

- Scale to multiple replicas
- Optimize database queries
- Check for memory leaks in logs
- Monitor with `docker stats`

### Network issues

- Verify DNS resolution: `nslookup traceo.example.com`
- Check firewall rules: `sudo ufw status`
- Test connectivity: `curl http://localhost:8000/health`

---

## Backup & Recovery

### Volume Backup

```bash
# Backup database volume
docker run --rm \
  -v traceo_db:/dbdata \
  -v /backup:/backup \
  ubuntu tar czf /backup/db-backup.tar.gz -C /dbdata .

# Restore from backup
docker run --rm \
  -v traceo_db:/dbdata \
  -v /backup:/backup \
  ubuntu tar xzf /backup/db-backup.tar.gz -C /dbdata
```

---

## Performance Tuning

### Database
- Enable query caching
- Index frequently queried columns
- Regular VACUUM on PostgreSQL

### Backend
- Increase uvicorn workers
- Enable gzip compression
- Use Redis for caching

### Frontend
- Minify and bundle assets
- Enable CDN
- Use lazy loading for images
