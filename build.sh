#!/usr/bin/env bash
# build.sh — Script de build para Render (Web Service)
# Configurar como Build Command en Render: ./build.sh

set -o errexit  # Salir si cualquier comando falla

echo "=== Instalando dependencias ==="
pip install --upgrade pip
pip install -r requirements.txt

echo "=== Collectstatic ==="
cd api
python manage.py collectstatic --no-input

echo "=== Migraciones ==="
python manage.py migrate --no-input

echo "=== Creando/actualizando superuser ==="
python manage.py crear_superuser

echo "=== Build completado ==="
