#!/bin/bash

echo "Ejecutando migraciones..."
python manage.py migrate

echo "Recolectando archivos estáticos..."
python manage.py collectstatic --noinput

# Crear superusuario solo si no existe
if [ "$CREATE_SUPERUSER" = "true" ]; then
    echo "Verificando si existe superusuario..."
    if python manage.py shell -c "from django.contrib.auth import get_user_model; User = get_user_model(); print('SUPERUSER_EXISTS' if User.objects.filter(username='$SUPERUSER_USERNAME').exists() else 'SUPERUSER_NOT_EXISTS')" | grep -q "SUPERUSER_NOT_EXISTS"; then
        echo "Creando superusuario..."
        python manage.py createsuperuser --noinput --username $SUPERUSER_USERNAME --email $SUPERUSER_EMAIL
        echo "Superusuario creado: $SUPERUSER_USERNAME"
    else
        echo "Superusuario ya existe, saltando creación..."
    fi
fi

# python manage.py crontab add

echo "Iniciando servidor..."
gunicorn -w 2 -b :8000 django_base.wsgi:application --timeout 120

# daphne -b 0.0.0.0 -p 8000 django_base.asgi:application