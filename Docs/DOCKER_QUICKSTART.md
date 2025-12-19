# 🚀 Quick Start Guide - Phase 2 (Docker Deployment)

## Prerequisites

- Docker Desktop (Windows/Mac) or Docker Engine (Linux)
- Docker Compose v2+
- Telegram Bot Token from @BotFather
- Supabase Account (optional, for cloud storage)

## 5-Minute Deployment

### Step 1: Clone & Configure

```bash
cd pdfbot

# Copy environment template
cp .env.example .env
```

### Step 2: Edit .env File

```bash
# Required
API_ID=your_telegram_api_id
API_HASH=your_telegram_api_hash
BOT_TOKEN=your_bot_token_from_botfather

# Optional but recommended
SUPABASE_URL=https://xxx.supabase.co/
SUPABASE_KEY=your_supabase_key

# Auto-configured for Docker
REDIS_URL=redis://redis:6379/0

# Optional
LOG_CHANNEL_ID=-1001234567890
```

### Step 3: Deploy

```bash
# Build and start all services
docker-compose up -d

# Watch logs
docker-compose logs -f bot
```

**Expected Output:**
```
✅ Redis connected: redis://redis:6379/0
✅ Using Redis for session storage (distributed)
✅ Health check server started on port 8080
🤖 Bot has started!
```

### Step 4: Verify

```bash
# Check health
curl http://localhost:8080/health

# Expected: {"status":"healthy", ...}

# Check metrics
curl http://localhost:8080/metrics

# View Redis UI (optional)
# Open browser: http://localhost:8081
```

### Step 5: Test

1. Open Telegram
2. Send `/start` to your bot
3. Send an image
4. Bot converts to PDF ✅

**Multi-PDF Test:**
```
/multipdf myfile
[send 3 images]
Click "Done" button
```

## Common Commands

```bash
# View logs
docker-compose logs -f bot
docker-compose logs -f redis

# Restart services
docker-compose restart

# Stop services
docker-compose down

# Stop and remove volumes (fresh start)
docker-compose down -v

# Scale bot instances
docker-compose up -d --scale bot=3

# Update code and restart
docker-compose build bot
docker-compose up -d bot
```

## Monitoring

### Health Check
```bash
# Linux/Mac
watch -n 5 curl -s http://localhost:8080/health | jq

# Windows PowerShell
while ($true) { curl http://localhost:8080/health | ConvertFrom-Json; sleep 5 }
```

### View Redis Data
```bash
# Connect to Redis CLI
docker-compose exec redis redis-cli

# List all sessions
KEYS session:*

# Get session data
GET session:userid_timestamp

# View stats
INFO

# Exit
exit
```

### Redis Commander UI
```bash
# Start with monitoring profile
docker-compose --profile monitoring up -d

# Open browser
http://localhost:8081
```

## Troubleshooting

### Bot Not Starting
```bash
# Check logs
docker-compose logs bot

# Common issues:
# 1. Invalid BOT_TOKEN → Check @BotFather
# 2. Missing .env → cp .env.example .env
# 3. Redis not ready → wait 10 seconds
```

### Redis Connection Failed
```bash
# Check Redis status
docker-compose ps redis

# Should show: Up (healthy)

# If not, restart
docker-compose restart redis
```

### Health Check Failing
```bash
# Test inside container
docker-compose exec bot curl http://localhost:8080/health

# If works inside but not outside:
# Windows Firewall might be blocking port 8080
```

## Production Deployment

### Secure Redis
```yaml
# docker-compose.production.yml
services:
  redis:
    command: >
      redis-server
      --appendonly yes
      --requirepass YOUR_STRONG_PASSWORD
```

Update .env:
```
REDIS_URL=redis://:YOUR_STRONG_PASSWORD@redis:6379/0
```

### Resource Limits
```yaml
services:
  bot:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
```

### Backup Volumes
```bash
# Backup Redis data
docker run --rm -v pdfbot_redis-data:/data -v $(pwd):/backup \
  alpine tar czf /backup/redis-backup-$(date +%Y%m%d).tar.gz /data

# Restore
docker run --rm -v pdfbot_redis-data:/data -v $(pwd):/backup \
  alpine tar xzf /backup/redis-backup-YYYYMMDD.tar.gz -C /
```

## Performance Tuning

### Increase Rate Limits
Edit `Modules/rate_limiter.py`:
```python
pdf_rate_limiter = RateLimiter(max_requests=20, window_seconds=60)
```

### Redis Memory
Edit `docker-compose.yml`:
```yaml
command: redis-server --maxmemory 512mb
```

### Scale Horizontally
```bash
# Run 5 bot instances
docker-compose up -d --scale bot=5

# All share same Redis → seamless scaling!
```

## Uninstall

```bash
# Stop and remove everything
docker-compose down -v

# Remove images
docker rmi pdfbot-bot
docker rmi redis:7-alpine

# Remove network
docker network rm pdfbot_pdfbot-network
```

---

## Next Steps

- ✅ Bot is running with Redis
- ✅ Health checks active
- ✅ Ready for production

**Optional Enhancements:**
- Add SSL/TLS reverse proxy (Nginx/Traefik)
- Deploy to cloud (AWS/Azure/GCP)
- Set up CI/CD pipeline
- Add Prometheus + Grafana monitoring

---

**Support:** Check [PHASE2_COMPLETE.md](PHASE2_COMPLETE.md) for detailed documentation
