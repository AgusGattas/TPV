#!/bin/bash

echo "Ejecutando migraciones..."
python manage.py migrate

echo "Recolectando archivos estáticos..."
python manage.py collectstatic --noinput

# Crear o actualizar superusuario
if [ "$CREATE_SUPERUSER" = "true" ]; then
    echo "Verificando superusuario..."
    if python manage.py shell -c "from django.contrib.auth import get_user_model; User = get_user_model(); print('SUPERUSER_EXISTS' if User.objects.filter(username='$SUPERUSER_USERNAME').exists() else 'SUPERUSER_NOT_EXISTS')" | grep -q "SUPERUSER_NOT_EXISTS"; then
        echo "Creando superusuario..."
        python manage.py createsuperuser --noinput --username $SUPERUSER_USERNAME --email $SUPERUSER_EMAIL
    else
        echo "Superusuario ya existe, actualizando contraseña..."
    fi
    
    # Usar contraseña de variable de entorno o generar una aleatoria
    if [ -n "$SUPERUSER_PASSWORD" ]; then
        PASSWORD="$SUPERUSER_PASSWORD"
        echo "Usando contraseña de variable de entorno"
    else
        PASSWORD=$(python -c "import secrets; import string; print(''.join(secrets.choice(string.ascii_letters + string.digits + '!@#$%^&*') for _ in range(12)))")
        echo "Generando contraseña aleatoria"
    fi
    
    # Siempre actualizar la contraseña
    echo "Actualizando contraseña del superusuario..."
    python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
user = User.objects.get(username='$SUPERUSER_USERNAME')
user.set_password('$PASSWORD')
user.save()
print('Contraseña actualizada correctamente')
"
    echo "=========================================="
    echo "SUPERUSUARIO CREADO/ACTUALIZADO:"
    echo "Usuario: $SUPERUSER_USERNAME"
    echo "Email: $SUPERUSER_EMAIL"
    echo "Contraseña: $PASSWORD"
    echo "=========================================="
fi

# python manage.py crontab add

echo "Iniciando servidor..."
gunicorn -w 2 -b :8000 django_base.wsgi:application --timeout 120

# daphne -b 0.0.0.0 -p 8000 django_base.asgi:application