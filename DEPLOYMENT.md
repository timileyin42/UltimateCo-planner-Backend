# Deployment Guide - Contabo Server

## 🚀 Quick Setup

### 1. **Server Preparation**

SSH into your Contabo server:
```bash
ssh root@84.247.168.225
```

Install Docker and Docker Compose:
```bash
# Update system
apt update && apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Install Docker Compose
apt install docker-compose-plugin -y

# Verify installation
docker --version
docker compose version
```

### 2. **Clone Repository**

```bash
# Create deployment directory
mkdir -p /root/planetal-backend
cd /root/planetal-backend

# Clone your repository
git clone https://github.com/timileyin42/UltimateCo-planner-Backend.git .

# Or if already cloned, pull latest
git pull origin main
```

### 3. **Setup Environment Variables**

```bash
# Copy production template
cp .env.production .env

# Edit with your actual values
nano .env
```

**Required Changes:**
- `POSTGRES_PASSWORD` - Strong database password
- `SECRET_KEY` - Generate with: `openssl rand -hex 32`
- All API keys (Google, OpenAI, Termii, Firebase, Stripe, etc.)
- Domain URLs (replace localhost with your actual domain)

### 4. **Setup Credentials**

```bash
# Create credentials directory
mkdir -p credentials

# Upload your credential files
# - credentials/gcp-service-account.json
# - credentials/firebase-service-account.json
```

**From your local machine:**
```powershell
# Upload GCP credentials
scp credentials/gcp-service-account.json root@84.247.168.225:/root/planetal-backend/credentials/

# Upload Firebase credentials
scp credentials/firebase-service-account.json root@84.247.168.225:/root/planetal-backend/credentials/
```

### 5. **Deploy Application**

```bash
# Build and start all services
docker compose up -d --build

# View logs
docker compose logs -f

# Check running services
docker compose ps
```

Expected services:
- ✅ `planetal-db` (PostgreSQL)
- ✅ `planetal-redis` (Redis)
- ✅ `planetal-api` (FastAPI)
- ✅ `planetal-celery-worker` (Background tasks)
- ✅ `planetal-celery-beat` (Scheduled tasks)

### 6. **Verify Deployment**

```bash
# Check API health
curl http://localhost:8000/api/v1/health

# Check database
docker exec planetal-db psql -U planetal -d planetal -c "SELECT version();"

# Check Redis
docker exec planetal-redis redis-cli ping

# Check Celery worker
docker exec planetal-celery-worker celery -A app.tasks.celery_app inspect active
```

---

## 🔄 GitHub Actions Setup (Automated Deployment)

### 1. **Add GitHub Secrets**

Go to your GitHub repository: `Settings → Secrets and variables → Actions`

Add these secrets:

| Secret Name | Value | Description |
|-------------|-------|-------------|
| `SERVER_HOST` | `84.247.168.225` | Your Contabo server IP |
| `SERVER_USER` | `root` | SSH user |
| `SSH_PRIVATE_KEY` | Your private key | Content of `~/.ssh/id_ed25519` |
| `SERVER_PORT` | `22` | SSH port (optional, defaults to 22) |
| `DEPLOY_PATH` | `/root/planetal-backend` | Deployment directory |

### 2. **Get Your SSH Private Key**

On your local machine:
```powershell
# Display private key
Get-Content $env:USERPROFILE\.ssh\id_ed25519

# Copy entire output including:
# -----BEGIN OPENSSH PRIVATE KEY-----
# ... key content ...
# -----END OPENSSH PRIVATE KEY-----
```

### 3. **Add Public Key to Server**

```bash
# On server
mkdir -p ~/.ssh
nano ~/.ssh/authorized_keys
# Paste your public key: ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIIu7nlWWVZzAxgC3Yd03sfmjy+WPSlO0eRImb7JH0tEv planetal-mobile-backend

# Set permissions
chmod 700 ~/.ssh
chmod 600 ~/.ssh/authorized_keys
```

### 4. **Test Automated Deployment**

```bash
# Push to main branch triggers deployment
git add .
git commit -m "Deploy to production"
git push origin main
```

Monitor deployment at: `https://github.com/timileyin42/UltimateCo-planner-Backend/actions`

---

## 🔐 Security Hardening

### 1. **Setup Firewall**

```bash
# Install UFW
apt install ufw -y

# Allow SSH
ufw allow 22/tcp

# Allow HTTP/HTTPS (for your reverse proxy)
ufw allow 80/tcp
ufw allow 443/tcp

# Allow your API port (if exposing directly)
ufw allow 8000/tcp

# Enable firewall
ufw enable
ufw status
```

### 2. **Setup SSL/TLS (Recommended)**

Use Nginx or Caddy as reverse proxy with Let's Encrypt:

```bash
# Install Caddy (easiest option)
apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
apt update
apt install caddy

# Create Caddyfile
nano /etc/caddy/Caddyfile
```

**Caddyfile content:**
```
api.yourdomain.com {
    reverse_proxy localhost:8000
    encode gzip
    
    # WebSocket support
    @websockets {
        header Connection *Upgrade*
        header Upgrade websocket
    }
    reverse_proxy @websockets localhost:8000
}
```

```bash
# Reload Caddy
systemctl reload caddy
```

### 3. **Database Backups**

```bash
# Create backup script
nano /root/backup-db.sh
```

**backup-db.sh:**
```bash
#!/bin/bash
BACKUP_DIR="/root/planetal-backend/backups"
DATE=$(date +%Y%m%d_%H%M%S)
FILENAME="planetal_$DATE.sql"

docker exec planetal-db pg_dump -U planetal planetal > $BACKUP_DIR/$FILENAME
gzip $BACKUP_DIR/$FILENAME

# Keep only last 7 days of backups
find $BACKUP_DIR -name "*.gz" -mtime +7 -delete

echo "Backup completed: $FILENAME.gz"
```

```bash
# Make executable
chmod +x /root/backup-db.sh

# Add to crontab (daily at 2 AM)
crontab -e
# Add line:
0 2 * * * /root/backup-db.sh >> /var/log/planetal-backup.log 2>&1
```

---

## 📊 Monitoring Commands

```bash
# View all logs
docker compose logs -f

# View specific service logs
docker compose logs -f api
docker compose logs -f celery-worker
docker compose logs -f db

# Check resource usage
docker stats

# Check disk space
df -h

# Restart services
docker compose restart api
docker compose restart celery-worker

# Update and redeploy
git pull origin main
docker compose up -d --build

# Clean up old images/containers
docker system prune -af
```

---

## 🐛 Troubleshooting

### Database Connection Issues
```bash
# Check if database is running
docker compose ps db

# Check database logs
docker compose logs db

# Access database directly
docker exec -it planetal-db psql -U planetal -d planetal
```

### Redis Connection Issues
```bash
# Check Redis
docker exec planetal-redis redis-cli ping

# View Redis info
docker exec planetal-redis redis-cli info
```

### API Not Responding
```bash
# Check API logs
docker compose logs api --tail=100

# Check if port is open
netstat -tulpn | grep 8000

# Restart API
docker compose restart api
```

### Celery Worker Not Processing Tasks
```bash
# Check worker status
docker exec planetal-celery-worker celery -A app.tasks.celery_app inspect active

# Check registered tasks
docker exec planetal-celery-worker celery -A app.tasks.celery_app inspect registered

# Restart worker
docker compose restart celery-worker
```

---

## 🔄 Update Application

```bash
# Pull latest code
cd /root/planetal-backend
git pull origin main

# Rebuild and restart
docker compose up -d --build

# Check logs
docker compose logs -f api
```

---

## 📈 Performance Tuning

Edit `.env` to adjust:

```bash
# Increase API workers for more traffic
UVICORN_WORKERS=8

# Increase Celery workers
CELERY_WORKER_CONCURRENCY=8

# Increase Redis memory
REDIS_MAX_MEMORY=1gb
```

Then restart:
```bash
docker compose up -d
```

---

## 🆘 Emergency Procedures

### Complete Reset
```bash
# Stop everything
docker compose down

# Remove all data (⚠️ DESTRUCTIVE)
docker compose down -v

# Rebuild from scratch
docker compose up -d --build
```

### Restore Database Backup
```bash
# Stop API to prevent writes
docker compose stop api celery-worker

# Restore from backup
gunzip < backups/planetal_20231207_020000.sql.gz | docker exec -i planetal-db psql -U planetal planetal

# Restart services
docker compose start api celery-worker
```
