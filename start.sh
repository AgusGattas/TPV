#!/bin/bash

echo "Ejecutando migraciones..."
python manage.py migrate

echo "Recolectando archivos estáticos..."
python manage.py collectstatic --noinput

echo "Iniciando servidor..."
gunicorn django_base.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120 --max-requests 1000 --max-requests-jitter 100 