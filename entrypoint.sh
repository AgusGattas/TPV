#!/bin/bash

echo "Ejecutando migraciones..."
python manage.py migrate

echo "Recolectando archivos estáticos..."
python manage.py collectstatic --noinput

# python manage.py crontab add

echo "Iniciando servidor..."
gunicorn -w 2 -b :8000 django_base.wsgi:application --timeout 120

# daphne -b 0.0.0.0 -p 8000 django_base.asgi:application