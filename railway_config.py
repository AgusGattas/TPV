"""
Configuraciones específicas para Railway
"""
import os

# Configuraciones para Railway
def get_railway_config():
    config = {}
    
    # Puerto dinámico de Railway
    if 'PORT' in os.environ:
        config['PORT'] = os.environ['PORT']
    
    # Base de datos PostgreSQL de Railway
    if 'DATABASE_URL' in os.environ:
        config['DATABASE_URL'] = os.environ['DATABASE_URL']
    
    # Variables de entorno de Railway
    if 'RAILWAY_STATIC_URL' in os.environ:
        config['STATIC_URL'] = os.environ['RAILWAY_STATIC_URL']
    
    return config

# Configuraciones recomendadas para Railway
RAILWAY_RECOMMENDATIONS = {
    'DEBUG': False,
    'IS_PRODUCTION': True,
    'DB_ENGINE': 'postgresql',
    'USE_S3': True,  # Para archivos estáticos
    'EMAIL_PROVIDER': 'smtp',  # Configurar email real
} 