#!/usr/bin/env bash
set -e

# Функция запуска шага с индикатором и описанием
step() {
  local num=$1 total=$2 desc=$3
  shift 3
  printf "Step %d/%d: %s... " "$num" "$total" "$desc"
  "$@" >/dev/null 2>&1
  echo "done"
}

TOTAL=9
COUNTER=1

# 1. Обновление системы
step "$COUNTER" "$TOTAL" "Updating system packages" sudo apt-get update -y && sudo apt-get upgrade -y
((COUNTER++))

# 2. Проверка Python ≥3.10
step "$COUNTER" "$TOTAL" "Checking Python3 ≥ 3.10" bash -c '
  command -v python3 >/dev/null || exit 1
  V=$(python3 -c '"'"'import sys;print(f"{sys.version_info.major}.{sys.version_info.minor}")'"'"')
  maj=${V%%.*}; min=${V##*.}
  (( maj>3 || (maj==3 && min>=10) )) || exit 1
'
# Сохраняем для venv и service
PY_MAJOR=$(python3 -c 'import sys;print(sys.version_info.major)')
PY_MINOR=$(python3 -c 'import sys;print(sys.version_info.minor)')
export PY_MAJOR PY_MINOR
((COUNTER++))

# 3. Установка pip3 и venv
step "$COUNTER" "$TOTAL" "Installing pip3 and venv" bash -c '
  sudo apt-get install -y python3-pip
  if (( PY_MAJOR==3 && PY_MINOR>=12 )); then
    sudo apt-get install -y python3.${PY_MINOR}-venv
  else
    sudo apt-get install -y python3-venv
  fi
'
((COUNTER++))

# 4. Валидация .env
step "$COUNTER" "$TOTAL" "Validating .env" bash -c '
  [ -f .env ] || exit 1
  set -a; source .env; set +a
  for v in DB_USER DB_PASSWORD DB_NAME DB_HOST DB_PORT TOKEN; do
    [ -n "${!v}" ] || exit 1
  done
'
# Источник переменных для следующих шагов
set -a; source .env; set +a
((COUNTER++))

# 5. Установка PostgreSQL
step "$COUNTER" "$TOTAL" "Installing PostgreSQL" sudo apt-get install -y postgresql postgresql-contrib
((COUNTER++))

# 6. Конфигурация БД
step "$COUNTER" "$TOTAL" "Configuring PostgreSQL DB & user" bash -c '
  sudo systemctl enable --now postgresql
  sudo -u postgres psql -c "ALTER USER ${DB_USER} WITH PASSWORD '\''${DB_PASSWORD}'\'';"
  sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='\''${DB_NAME}'\''" | grep -q 1 \
    || sudo -u postgres createdb -O "${DB_USER}" "${DB_NAME}"
'
((COUNTER++))

# 7. Создание venv и установка зависимостей
step "$COUNTER" "$TOTAL" "Setting up virtualenv & dependencies" bash -c '
  [ -d venv ] || python3 -m venv venv
  source venv/bin/activate
  pip install --upgrade pip
  pip install -r requirements.txt
  deactivate
'
((COUNTER++))

# 8. Создание systemd-сервиса
step "$COUNTER" "$TOTAL" "Creating and starting systemd service" bash -c '
  PROJECT_DIR="$(pwd)"
  PY_BIN="venv/bin/python${PY_MAJOR}.${PY_MINOR}"
  [ -f "$PY_BIN" ] || PY_BIN="venv/bin/python"
  sudo tee /etc/systemd/system/autodialog.service >/dev/null <<EOF
[Unit]
Description=AutoDialog Bot
After=network.target

[Service]
User=root
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/$PY_BIN $PROJECT_DIR/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
  sudo systemctl daemon-reload
  sudo systemctl enable autodialog
  sudo systemctl restart autodialog
'
((COUNTER++))

# 9. Проверка статуса
step "$COUNTER" "$TOTAL" "Checking service status" bash -c '
  systemctl status autodialog --no-pager | head -n 10
'

echo
echo "All steps completed successfully!"
