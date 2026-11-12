#!/usr/bin/env bash
# Instala o actualiza Mente en Movimiento en una instancia EC2 con Ubuntu 24.04.
#
#   sudo git clone https://github.com/Jmosqueran2/MenteEnMovimiento.git /opt/mente
#   sudo chown -R ubuntu:ubuntu /opt/mente
#   cp /opt/mente/deploy/aws.env.ejemplo /opt/mente/deploy/aws.env   # y complétalo
#   bash /opt/mente/deploy/instalar.sh
#
# Se puede volver a ejecutar cuantas veces haga falta (después de un git pull o
# si cambió la IP pública): conserva la clave secreta y la base de datos.
set -euo pipefail

RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
USUARIO="$(id -un)"
cd "$RAIZ"

paso() { printf '\n\033[1;32m==> %s\033[0m\n' "$*"; }

# --- Configuración de AWS (bucket S3 y base RDS) -------------------------------
AWS_STORAGE_BUCKET_NAME=""
AWS_S3_REGION_NAME="us-east-1"
DATABASE_URL=""
DOMINIO=""
if [[ -f deploy/aws.env ]]; then
  # shellcheck disable=SC1091
  source deploy/aws.env
fi

# Dominio con HTTPS gratis: la IP pública con guiones + .sslip.io
if [[ -z "$DOMINIO" ]]; then
  TOKEN="$(curl -fsS -X PUT http://169.254.169.254/latest/api/token -H 'X-aws-ec2-metadata-token-ttl-seconds: 60')"
  IP="$(curl -fsS -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/public-ipv4)"
  DOMINIO="${IP//./-}.sslip.io"
fi
echo "Dominio: https://$DOMINIO"
[[ -n "$AWS_STORAGE_BUCKET_NAME" ]] && echo "S3:      $AWS_STORAGE_BUCKET_NAME" || echo "S3:      (sin bucket: archivos en el disco del servidor)"
[[ -n "$DATABASE_URL" ]] && echo "Base:    RDS PostgreSQL" || echo "Base:    (sin RDS: SQLite en el servidor)"

# --- Paquetes del sistema -----------------------------------------------------
paso "Paquetes del sistema"
sudo apt-get update -q
sudo apt-get install -y -q python3-venv python3-dev build-essential git curl \
  libgl1 libglib2.0-0 debian-keyring debian-archive-keyring apt-transport-https gnupg
if ! command -v node >/dev/null || [[ "$(node -v | cut -c2- | cut -d. -f1)" -lt 20 ]]; then
  curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
  sudo apt-get install -y -q nodejs
fi
if ! command -v caddy >/dev/null; then
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor --yes -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null
  sudo apt-get update -q
  sudo apt-get install -y -q caddy
fi

# --- Backend (Django + DRF + scikit-learn) ------------------------------------
paso "Backend"
cd "$RAIZ/backend"
[[ -d .venv ]] || python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt

# La clave secreta se genera una sola vez y se reutiliza en cada actualización.
SECRETO=""
if [[ -f .env ]]; then SECRETO="$(grep -E '^DJANGO_SECRET_KEY=' .env | cut -d= -f2- || true)"; fi
[[ -n "$SECRETO" ]] || SECRETO="$(.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(50))')"

cat > .env <<EOF
DJANGO_SECRET_KEY=$SECRETO
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=$DOMINIO,localhost,127.0.0.1
DJANGO_CORS_ORIGINS=https://$DOMINIO
DJANGO_CSRF_TRUSTED_ORIGINS=https://$DOMINIO
DATABASE_URL=$DATABASE_URL
AWS_STORAGE_BUCKET_NAME=$AWS_STORAGE_BUCKET_NAME
AWS_S3_REGION_NAME=$AWS_S3_REGION_NAME
DJANGO_REGISTRO_ABIERTO=${REGISTRO_ABIERTO:-true}
EOF
chmod 600 .env

.venv/bin/python manage.py migrate --noinput
.venv/bin/python manage.py cargar_datos --demo
.venv/bin/python manage.py entrenar_modelo
.venv/bin/python manage.py collectstatic --noinput -v 0
mkdir -p media

# --- Microservicio de visión (FastAPI + MediaPipe + YOLO) ---------------------
paso "Microservicio de visión"
cd "$RAIZ/vision_service"
[[ -d .venv ]] || python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt
.venv/bin/python arreglar_opencv.py
.venv/bin/python descargar_modelos.py
cat > .env <<EOF
VISION_JWT_SECRETO=$SECRETO
VISION_ORIGENES=https://$DOMINIO
VISION_POSE_CADA_N=2
VISION_TAMANO_POSE=320
VISION_DEMO=false
EOF
chmod 600 .env

# --- Frontend (React + Vite) ---------------------------------------------------
paso "Frontend"
cd "$RAIZ/frontend"
npm ci --no-audit --no-fund --loglevel=error
npm run build

# --- Servicios del sistema -----------------------------------------------------
paso "Servicios (systemd) y HTTPS (Caddy)"
sudo tee /etc/systemd/system/mente-backend.service >/dev/null <<EOF
[Unit]
Description=Mente en Movimiento - API Django
After=network-online.target
Wants=network-online.target

[Service]
User=$USUARIO
WorkingDirectory=$RAIZ/backend
ExecStart=$RAIZ/backend/.venv/bin/gunicorn config.wsgi:application --bind 127.0.0.1:8000 --workers 2 --timeout 60
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo tee /etc/systemd/system/mente-vision.service >/dev/null <<EOF
[Unit]
Description=Mente en Movimiento - microservicio de visión
After=network-online.target
Wants=network-online.target

[Service]
User=$USUARIO
WorkingDirectory=$RAIZ/vision_service
Environment=YOLO_CONFIG_DIR=/tmp/ultralytics
ExecStart=$RAIZ/vision_service/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8001 --env-file .env --proxy-headers
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sed -e "s|{DOMINIO}|$DOMINIO|g" -e "s|{RAIZ}|$RAIZ|g" "$RAIZ/deploy/Caddyfile.plantilla" | sudo tee /etc/caddy/Caddyfile >/dev/null

sudo systemctl daemon-reload
sudo systemctl enable --now mente-backend mente-vision
sudo systemctl restart mente-backend mente-vision
sudo systemctl enable caddy
sudo systemctl reload caddy || sudo systemctl restart caddy

# --- Verificación ------------------------------------------------------------
paso "Verificación"
sleep 5
curl -fsS http://127.0.0.1:8000/api/salud/ && echo "  ← API Django"
for _ in $(seq 1 30); do  # los modelos de visión tardan unos segundos en cargar
  if curl -fsS http://127.0.0.1:8001/salud 2>/dev/null; then echo "  ← visión"; break; fi
  sleep 2
done

cat <<EOF

Listo. Abre:  https://$DOMINIO
Usuario: cuidador · Clave: MenteEnMovimiento2026 (cámbiala en https://$DOMINIO/admin/)

Si la página no abre por HTTPS, revisa que el grupo de seguridad permita los
puertos 80 y 443 (Caddy pide el certificado por el puerto 80) y mira:
  sudo journalctl -u caddy -n 50
EOF
