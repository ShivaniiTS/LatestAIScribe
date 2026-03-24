# New AI Scribe Enterprise

AI-powered medical scribe pipeline: record encounters → transcribe (WhisperX) → generate clinical notes (Ollama qwen2.5:14b) → MT review → deliver.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Vue 3 + Quasar 2 Frontend  (port 9000)                    │
└────────────────────────┬────────────────────────────────────┘
                         │ REST + WebSocket
┌────────────────────────▼────────────────────────────────────┐
│  FastAPI Single Server  (port 8000)                         │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  LangGraph 6-Node Pipeline                          │    │
│  │  CONTEXT → CAPTURE → TRANSCRIBE → NOTE → REVIEW →  │    │
│  │  DELIVERY                                           │    │
│  └─────────────────────────────────────────────────────┘    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │ WhisperX │ │  Ollama  │ │  EHR     │ │ MedASR   │       │
│  │ (ASR)    │ │  (LLM)   │ │ (Stub)   │ │ (Postpr) │       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
└────────────────────────┬────────────────────────────────────┘
                         │
            ┌────────────▼───────────┐
            │  PostgreSQL 16         │
            │  Local Filesystem      │
            └────────────────────────┘
```

## Quick Start (Local Development)

```bash
# 1. Clone and enter project
cd New-ai-scribe-enterprise-main

# 2. Create Python virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# 3. Install Python dependencies
pip install -e ".[dev]"

# 4. Copy and edit environment config
cp .env.example .env
# Edit .env with your settings

# 5. Start Ollama with the model
ollama pull qwen2.5:14b
ollama serve

# 6. Run the API
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# 7. Install and run frontend
cd frontend
npm install
npx quasar dev
```

## Run Tests

```bash
pytest tests/ -v
```

---

## AWS Ubuntu Staging Deployment Guide

### Prerequisites

- **AWS EC2**: Ubuntu 22.04 LTS, t3.xlarge or better (8 GB RAM minimum)
  - For GPU transcription: g4dn.xlarge (NVIDIA T4 GPU, 16 GB VRAM)
- **Security Group**: Open ports 22 (SSH), 80 (HTTP), 443 (HTTPS), 8000 (API), 9000 (frontend dev)
- **Domain** (optional): Point an A record to the EC2 public IP
- **SSH Access**: Your key pair for the instance

### Step 1: Connect and Update Server

```bash
ssh -i your-key.pem ubuntu@<EC2_PUBLIC_IP>

sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl wget build-essential software-properties-common \
  ffmpeg python3.12 python3.12-venv python3-pip \
  postgresql-16 postgresql-client-16 \
  nginx certbot python3-certbot-nginx
```

### Step 2: Install Node.js 22

```bash
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs
node --version  # Should be v22.x
```

### Step 3: Install Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5:14b

# Enable as a service
sudo systemctl enable ollama
sudo systemctl start ollama

# Verify
curl http://localhost:11434/api/tags
```

### Step 4: (GPU Only) Install NVIDIA Drivers + CUDA

```bash
# Only if using a GPU instance (g4dn, g5, p3, etc.)
sudo apt install -y nvidia-driver-535 nvidia-cuda-toolkit
sudo reboot

# After reboot, verify
nvidia-smi
```

### Step 5: Clone the Project

```bash
cd /opt
sudo mkdir ai-scribe && sudo chown ubuntu:ubuntu ai-scribe
cd ai-scribe

# Transfer your project (SCP, git clone, etc.)
scp -r -i your-key.pem ./New-ai-scribe-enterprise-main ubuntu@<EC2_PUBLIC_IP>:/opt/ai-scribe/

# Or if using git:
# git clone <your-repo-url> New-ai-scribe-enterprise-main
cd New-ai-scribe-enterprise-main
```

### Step 6: Set Up Python Environment

```bash
python3.12 -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
pip install -e ".[dev]"

# For GPU transcription, also install:
# pip install -e ".[gpu]"
```

### Step 7: Configure PostgreSQL

```bash
sudo -u postgres psql <<EOF
CREATE USER aiscribe WITH PASSWORD 'your_secure_password_here';
CREATE DATABASE aiscribe OWNER aiscribe;
GRANT ALL PRIVILEGES ON DATABASE aiscribe TO aiscribe;
EOF
```

### Step 8: Configure Environment

```bash
cp .env.example .env
nano .env
```

Edit the `.env` file:

```env
DATABASE_URL=postgresql+asyncpg://aiscribe:your_secure_password_here@localhost:5432/aiscribe
OLLAMA_URL=http://localhost:11434
HF_TOKEN=hf_your_huggingface_token
STORAGE_ROOT=/opt/ai-scribe/New-ai-scribe-enterprise-main/data
CORS_ORIGINS=http://your-domain.com,https://your-domain.com
SECRET_KEY=generate-a-random-64-char-string
```

Generate a random secret key:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### Step 9: Initialize Database

```bash
source .venv/bin/activate
python -c "
import asyncio
from db.models import init_db
asyncio.run(init_db())
print('Database initialized')
"
```

### Step 10: Build Frontend

```bash
cd frontend
npm install
npx quasar build

# The built files will be in frontend/dist/spa/
cd ..
```

### Step 11: Create Systemd Service for API

```bash
sudo tee /etc/systemd/system/ai-scribe-api.service > /dev/null <<EOF
[Unit]
Description=AI Scribe Enterprise API
After=network.target postgresql.service ollama.service
Wants=postgresql.service ollama.service

[Service]
Type=simple
User=ubuntu
Group=ubuntu
WorkingDirectory=/opt/ai-scribe/New-ai-scribe-enterprise-main
EnvironmentFile=/opt/ai-scribe/New-ai-scribe-enterprise-main/.env
ExecStart=/opt/ai-scribe/New-ai-scribe-enterprise-main/.venv/bin/uvicorn \
  api.main:app \
  --host 127.0.0.1 \
  --port 8000 \
  --workers 1 \
  --log-level info
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable ai-scribe-api
sudo systemctl start ai-scribe-api

# Check status
sudo systemctl status ai-scribe-api
sudo journalctl -u ai-scribe-api -f
```

### Step 12: Configure Nginx Reverse Proxy

```bash
sudo tee /etc/nginx/sites-available/ai-scribe > /dev/null <<'EOF'
server {
    listen 80;
    server_name your-domain.com;  # Or use _ for IP-based access

    # Frontend (built Quasar SPA)
    location / {
        root /opt/ai-scribe/New-ai-scribe-enterprise-main/frontend/dist/spa;
        try_files $uri $uri/ /index.html;
    }

    # API proxy
    location /api/ {
        rewrite ^/api/(.*) /$1 break;
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        client_max_body_size 200M;
    }

    # WebSocket proxy
    location /ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 86400;
    }

    # Health check (direct pass-through)
    location /health {
        proxy_pass http://127.0.0.1:8000;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/ai-scribe /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

### Step 13: (Optional) Enable HTTPS with Let's Encrypt

```bash
sudo certbot --nginx -d your-domain.com
# Follow the prompts — certbot auto-configures SSL in nginx

# Auto-renewal is set up automatically. Verify:
sudo certbot renew --dry-run
```

### Step 14: Configure Firewall

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
sudo ufw status
```

### Step 15: Run Tests on Server

```bash
cd /opt/ai-scribe/New-ai-scribe-enterprise-main
source .venv/bin/activate
pytest tests/ -v
```

### Step 16: Verify Deployment

```bash
# Health check
curl http://localhost:8000/health
# Expected: {"status":"ok"}

# Readiness check
curl http://localhost:8000/health/ready
# Expected: {"status":"ready","checks":{"ollama":"ok","database":"ok"}}

# Frontend (from browser)
# Navigate to http://your-domain.com or http://<EC2_PUBLIC_IP>
```

### Deployment Checklist

- [ ] PostgreSQL running and database created
- [ ] Ollama running with `qwen2.5:14b` pulled
- [ ] `.env` configured with secure passwords and correct URLs
- [ ] Database tables initialized
- [ ] Frontend built (`npx quasar build`)
- [ ] Systemd service running (`sudo systemctl status ai-scribe-api`)
- [ ] Nginx configured and reloaded
- [ ] Firewall configured (UFW)
- [ ] Health check returns `{"status":"ok"}`  
- [ ] Frontend loads in browser
- [ ] (Optional) SSL certificate installed

### Monitoring & Logs

```bash
# API logs
sudo journalctl -u ai-scribe-api -f --no-pager

# Nginx access/error logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log

# Ollama logs
sudo journalctl -u ollama -f

# PostgreSQL logs
sudo tail -f /var/log/postgresql/postgresql-16-main.log
```

### Updating the Application

```bash
cd /opt/ai-scribe/New-ai-scribe-enterprise-main

# Pull latest code
# git pull origin main

# Update Python deps
source .venv/bin/activate
pip install -e ".[dev]"

# Rebuild frontend
cd frontend && npm install && npx quasar build && cd ..

# Restart API
sudo systemctl restart ai-scribe-api
```

---

## Docker Deployment (Alternative)

If you prefer Docker:

```bash
# Build and start everything
docker compose up -d

# Check status
docker compose ps
docker compose logs -f api
```

This starts PostgreSQL, Ollama, and the API+Frontend in containers.
