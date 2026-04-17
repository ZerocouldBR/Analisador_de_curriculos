#!/bin/bash
set -euo pipefail

# ================================================================
# Analisador de Curriculos - Script de Deploy Completo para VPS
# Ubuntu 22.04+ | Docker + Docker Compose
# ================================================================

echo "============================================"
echo "  Analisador de Curriculos - Deploy VPS"
echo "============================================"

# ---- Configuration ----
APP_DIR="/opt/analisador-curriculos"
DOMAIN="${DOMAIN:-curriculos.seudominio.com.br}"

# ---- 1. System Update & Dependencies ----
echo ""
echo "[1/8] Atualizando sistema e instalando dependencias..."
sudo apt-get update -y
sudo apt-get upgrade -y
sudo apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    ufw \
    fail2ban \
    unattended-upgrades

# ---- 2. Install Docker ----
echo ""
echo "[2/8] Instalando Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sudo sh
    sudo usermod -aG docker $USER
    sudo systemctl enable docker
    sudo systemctl start docker
    echo "  Docker instalado com sucesso."
else
    echo "  Docker ja esta instalado."
fi

# Install Docker Compose plugin
if ! docker compose version &> /dev/null; then
    sudo apt-get install -y docker-compose-plugin
    echo "  Docker Compose plugin instalado."
else
    echo "  Docker Compose ja esta instalado."
fi

# ---- 3. Firewall Configuration ----
echo ""
echo "[3/8] Configurando firewall (UFW)..."
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable
echo "  Firewall configurado: SSH, HTTP, HTTPS permitidos."

# ---- 4. Fail2Ban Configuration ----
echo ""
echo "[4/8] Configurando Fail2Ban..."
sudo tee /etc/fail2ban/jail.local > /dev/null <<'FAIL2BAN'
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5

[sshd]
enabled = true
port = ssh
filter = sshd
logpath = /var/log/auth.log
maxretry = 3
FAIL2BAN
sudo systemctl enable fail2ban
sudo systemctl restart fail2ban
echo "  Fail2Ban configurado."

# ---- 5. Create Application Directory ----
echo ""
echo "[5/8] Configurando diretorio da aplicacao..."
sudo mkdir -p "$APP_DIR"
sudo chown $USER:$USER "$APP_DIR"

# Copy project files (assumes git clone or rsync already done)
if [ -d ".git" ]; then
    echo "  Copiando arquivos do projeto..."
    rsync -av --exclude='.git' --exclude='node_modules' --exclude='__pycache__' --exclude='.venv' . "$APP_DIR/"
fi

cd "$APP_DIR"

# ---- 6. Environment Configuration ----
echo ""
echo "[6/8] Configurando variaveis de ambiente..."

if [ ! -f "$APP_DIR/backend/.env" ]; then
    # Generate secure secrets
    SECRET_KEY=$(openssl rand -hex 32)
    DB_PASSWORD=$(openssl rand -base64 24 | tr -d '/+=')
    REDIS_PASSWORD=$(openssl rand -base64 24 | tr -d '/+=')
    GRAFANA_PASSWORD=$(openssl rand -base64 16 | tr -d '/+=')
    FLOWER_PASSWORD=$(openssl rand -base64 16 | tr -d '/+=')

    cat > "$APP_DIR/backend/.env" <<EOF
# ================================================================
# Analisador de Curriculos - Configuracao de Producao
# Gerado automaticamente em $(date)
# ================================================================

# Aplicacao
APP_VERSION=0.3.0
LOG_LEVEL=warning
DEBUG=false

# Banco de Dados
DATABASE_URL=postgresql+psycopg://analisador:${DB_PASSWORD}@db:5432/analisador_curriculos

# Redis
REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0

# Seguranca
SECRET_KEY=${SECRET_KEY}
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
ENABLE_PII_ENCRYPTION=true
RATE_LIMIT_PER_MINUTE=60

# CORS - Ajuste para seu dominio
CORS_ORIGINS=["https://${DOMAIN}"]

# Vector DB
VECTOR_DB_PROVIDER=pgvector

# Embeddings - Escolha: api (OpenAI) ou local (sentence-transformers)
EMBEDDING_MODE=local
EMBEDDING_MODEL_LOCAL=all-MiniLM-L6-v2

# OpenAI (necessario apenas se EMBEDDING_MODE=api)
# OPENAI_API_KEY=sk-...

# LLM
# LLM_MODEL=gpt-4o
# LLM_TEMPERATURE=0.7

# Upload
MAX_UPLOAD_SIZE_MB=20
STORAGE_BACKEND=local
STORAGE_PATH=/app/uploads

# OCR
OCR_LANGUAGES=por+eng
OCR_MIN_CONFIDENCE=30
EOF

    echo "  Arquivo .env criado com senhas seguras."
    echo ""
    echo "  ================================================="
    echo "  CREDENCIAIS GERADAS (SALVE EM LOCAL SEGURO!):"
    echo "  ================================================="
    echo "  DB_PASSWORD:      ${DB_PASSWORD}"
    echo "  REDIS_PASSWORD:   ${REDIS_PASSWORD}"
    echo "  GRAFANA_PASSWORD: ${GRAFANA_PASSWORD}"
    echo "  FLOWER_PASSWORD:  ${FLOWER_PASSWORD}"
    echo "  SECRET_KEY:       ${SECRET_KEY}"
    echo "  ================================================="
    echo ""

    # Create .env for docker-compose
    cat > "$APP_DIR/.env" <<EOF
DB_PASSWORD=${DB_PASSWORD}
REDIS_PASSWORD=${REDIS_PASSWORD}
GRAFANA_USER=admin
GRAFANA_PASSWORD=${GRAFANA_PASSWORD}
FLOWER_USER=admin
FLOWER_PASSWORD=${FLOWER_PASSWORD}
FRONTEND_API_URL=https://${DOMAIN}
FRONTEND_WS_URL=wss://${DOMAIN}
EOF

else
    echo "  Arquivo .env ja existe. Pulando geracao de senhas."
fi

# ---- 7. Install Nginx + Certbot (SSL) ----
echo ""
echo "[7/8] Configurando Nginx e SSL..."
sudo apt-get install -y nginx certbot python3-certbot-nginx

# Nginx reverse proxy config
sudo tee /etc/nginx/sites-available/analisador > /dev/null <<NGINX
server {
    listen 80;
    server_name ${DOMAIN};

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;

    server_tokens off;
    client_max_body_size 20M;

    # Frontend
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    # API proxy
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }

    # Monitoring (restricted access)
    location /grafana/ {
        proxy_pass http://127.0.0.1:3001/;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
    }
}
NGINX

sudo ln -sf /etc/nginx/sites-available/analisador /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx

echo "  Nginx configurado."
echo ""
echo "  Para configurar SSL, execute:"
echo "    sudo certbot --nginx -d ${DOMAIN}"
echo ""

# ---- 8. Build & Start Application ----
echo ""
echo "[8/8] Construindo e iniciando a aplicacao..."
cd "$APP_DIR"

docker compose -f docker-compose.prod.yml build --no-cache
docker compose -f docker-compose.prod.yml up -d

echo ""
echo "  Aguardando servicos iniciarem..."
sleep 15

# Check health
echo ""
echo "  Verificando saude dos servicos..."
docker compose -f docker-compose.prod.yml ps

echo ""
echo "============================================"
echo "  Deploy concluido com sucesso!"
echo "============================================"
echo ""
echo "  URLs:"
echo "    Frontend:   http://${DOMAIN}"
echo "    API:        http://${DOMAIN}/api/health"
echo "    Grafana:    http://${DOMAIN}/grafana/"
echo "    Flower:     http://127.0.0.1:5555 (acesso local)"
echo ""
echo "  Proximos passos:"
echo "    1. Configurar SSL: sudo certbot --nginx -d ${DOMAIN}"
echo "    2. Criar usuario admin via API: POST /api/v1/auth/register"
echo "    3. Verificar logs: docker compose -f docker-compose.prod.yml logs -f"
echo "    4. Monitoramento: http://${DOMAIN}/grafana/"
echo ""
echo "  Comandos uteis:"
echo "    docker compose -f docker-compose.prod.yml logs -f api"
echo "    docker compose -f docker-compose.prod.yml restart api"
echo "    docker compose -f docker-compose.prod.yml down"
echo "    docker compose -f docker-compose.prod.yml up -d"
echo ""
