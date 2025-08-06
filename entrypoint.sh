#!/bin/bash

python manage.py migrate

python manage.py collectstatic --noinput

# python manage.py crontab add

gunicorn -w 2 -b :8000 django_base.wsgi:application --timeout 120

# daphne -b 0.0.0.0 -p 8000 django_base.asgi:application