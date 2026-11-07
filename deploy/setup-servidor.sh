#!/usr/bin/env bash
# =====================================================================
# Prepara un servidor Ubuntu 24.04 (p. ej. AWS EC2) para Bogotá Vial.
# Se puede correr varias veces: lo que ya está hecho se salta.
#
# Uso (conectado por SSH como el usuario "ubuntu", NO como root):
#   bash setup-servidor.sh
#
# Hace:
#   1. Actualiza el sistema y activa actualizaciones de seguridad automáticas
#   2. Instala Docker (y limita el tamaño de los logs)
#   3. Crea 2 GB de swap (el build del frontend necesita memoria)
#   4. Crea la llave para que el servidor lea el repo de GitHub (deploy key)
#   5. Crea la llave con la que GitHub Actions entrará a desplegar
#   6. Clona el repo en /opt/bogota-vial
#   7. Programa la copia de seguridad diaria de la base (3:00 a. m.)
# =====================================================================
set -euo pipefail

REPO_HTTPS="https://github.com/LauraDanielaa/bogota-vial.git"
REPO_SSH="git@github.com:LauraDanielaa/bogota-vial.git"
APP_DIR="/opt/bogota-vial"
BACKUP_DIR="/opt/bogota-vial-backups"
USUARIO="$(whoami)"

paso() { printf '\n\033[1;32m==> %s\033[0m\n' "$*"; }
aviso() { printf '\033[1;33m%s\033[0m\n' "$*"; }

if [[ $EUID -eq 0 ]]; then
  echo "Ejecuta este script como el usuario normal (ubuntu), no como root."
  exit 1
fi

# ---------------------------------------------------------------------
paso "1/7 Actualizando el sistema"
sudo apt-get update -y
sudo DEBIAN_FRONTEND=noninteractive apt-get upgrade -y
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y ca-certificates curl git unattended-upgrades
sudo dpkg-reconfigure -f noninteractive unattended-upgrades

# ---------------------------------------------------------------------
paso "2/7 Instalando Docker"
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sudo sh
fi
sudo usermod -aG docker "$USUARIO"
if [[ ! -f /etc/docker/daemon.json ]]; then
  echo '{ "log-driver": "json-file", "log-opts": { "max-size": "10m", "max-file": "3" } }' |
    sudo tee /etc/docker/daemon.json >/dev/null
  sudo systemctl restart docker
fi
sudo systemctl enable docker >/dev/null

# ---------------------------------------------------------------------
paso "3/7 Memoria swap de 2 GB"
if ! swapon --show | grep -q '/swapfile'; then
  sudo fallocate -l 2G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile >/dev/null
  sudo swapon /swapfile
  grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
  echo 'vm.swappiness=10' | sudo tee /etc/sysctl.d/99-swappiness.conf >/dev/null
  sudo sysctl -p /etc/sysctl.d/99-swappiness.conf >/dev/null
else
  echo "Ya existe."
fi

# ---------------------------------------------------------------------
paso "4/7 Llave para leer el repo de GitHub (deploy key)"
mkdir -p ~/.ssh && chmod 700 ~/.ssh
if [[ ! -f ~/.ssh/github_deploy ]]; then
  ssh-keygen -q -t ed25519 -N "" -C "bogota-vial-servidor" -f ~/.ssh/github_deploy
fi
if ! grep -q 'IdentityFile ~/.ssh/github_deploy' ~/.ssh/config 2>/dev/null; then
  printf 'Host github.com\n  IdentityFile ~/.ssh/github_deploy\n  IdentitiesOnly yes\n' >>~/.ssh/config
  chmod 600 ~/.ssh/config
fi
ssh-keyscan -t ed25519 github.com 2>/dev/null >>~/.ssh/known_hosts
sort -u ~/.ssh/known_hosts -o ~/.ssh/known_hosts

# ---------------------------------------------------------------------
paso "5/7 Llave para GitHub Actions"
if [[ ! -f ~/.ssh/github_actions ]]; then
  ssh-keygen -q -t ed25519 -N "" -C "github-actions-bogota-vial" -f ~/.ssh/github_actions
fi
touch ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys
grep -qF "$(cat ~/.ssh/github_actions.pub)" ~/.ssh/authorized_keys || cat ~/.ssh/github_actions.pub >>~/.ssh/authorized_keys

# ---------------------------------------------------------------------
paso "6/7 Descargando el código en $APP_DIR"
sudo mkdir -p "$APP_DIR" "$BACKUP_DIR"
sudo chown "$USUARIO":"$USUARIO" "$APP_DIR" "$BACKUP_DIR"
REPO_LISTO=false
if [[ -d "$APP_DIR/.git" ]]; then
  echo "El repo ya estaba clonado."
  REPO_LISTO=true
elif git clone -q "$REPO_HTTPS" "$APP_DIR" 2>/dev/null; then
  echo "Clonado (repo público)."
  REPO_LISTO=true
elif git clone -q "$REPO_SSH" "$APP_DIR" 2>/dev/null; then
  echo "Clonado con la deploy key (repo privado)."
  REPO_LISTO=true
fi

# ---------------------------------------------------------------------
paso "7/7 Copia de seguridad diaria"
if $REPO_LISTO; then
  LINEA="0 3 * * * bash $APP_DIR/deploy/backup.sh >> $BACKUP_DIR/backup.log 2>&1"
  (crontab -l 2>/dev/null | grep -vF "deploy/backup.sh"; echo "$LINEA") | crontab -
  echo "Programada todos los días a las 3:00 a. m. en $BACKUP_DIR"
else
  echo "Pendiente: se programa al volver a correr el script con el repo clonado."
fi

# ---------------------------------------------------------------------
echo
echo "====================================================================="
if ! $REPO_LISTO; then
  aviso "El repo es privado y el servidor todavía no tiene permiso para leerlo."
  echo "Agrega esta llave en GitHub -> repo -> Settings -> Deploy keys -> Add deploy key"
  echo "(título: servidor, SIN marcar 'Allow write access'):"
  echo
  cat ~/.ssh/github_deploy.pub
  echo
  echo "Después vuelve a correr:  bash setup-servidor.sh"
  echo "====================================================================="
  exit 0
fi

aviso "Llave PRIVADA para GitHub Actions (secret VPS_SSH_KEY). Cópiala completa,"
aviso "incluidas las líneas BEGIN y END, y no la compartas con nadie:"
echo
cat ~/.ssh/github_actions
echo
echo "====================================================================="
echo "Siguientes pasos:"
echo "  1. Cierra la sesión SSH y vuelve a entrar (para poder usar docker sin sudo)."
echo "  2. Crea $APP_DIR/.env  (ver .env.example)."
echo "  3. Sube la carpeta data/ desde tu PC con scp."
echo "  4. cd $APP_DIR && docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build"
echo "  5. docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm etl"
echo "====================================================================="
