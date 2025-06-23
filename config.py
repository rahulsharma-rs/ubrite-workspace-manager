import os
from datetime import timedelta

# Get the current user from environment
USER = os.environ.get('USER', 'default_user')
BASE_PATH = f'/data/user/{USER}/ondemand'


class Config:
    """Base configuration class."""

    # Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'

    # Database settings
    UBRITE_ROOT = os.path.join(BASE_PATH, 'ubrite_workspaces')
    DB_ROOT = os.path.join(BASE_PATH, 'ubrite_databases')
    SQLALCHEMY_DATABASE_URI = f'sqlite:///{os.path.join(DB_ROOT, "ubrite.db")}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # File upload settings
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB max file size
    UPLOAD_FOLDER = os.path.join(UBRITE_ROOT, 'uploads')

    # Session settings
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
    SESSION_COOKIE_SECURE = False  # Set to True in production with HTTPS
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

    # CSRF settings
    WTF_CSRF_TIME_LIMIT = None
    WTF_CSRF_SSL_STRICT = False

    # Logging
    LOGS_DIR = os.path.join(BASE_PATH, 'logs')

    # Analytics
    ANALYTICS_ENABLED = True

    # CORS settings for OnDemand
    CORS_ORIGINS = ['*']  # Adjust as needed for security
    CORS_METHODS = ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS']
    CORS_ALLOW_HEADERS = ['Content-Type', 'Authorization', 'X-CSRFToken']

    # API settings
    API_BASE_URL = f'/pun/dev/rc_workspace'  # OnDemand path

    # External service settings - GitLab is EXTERNAL, not through OnDemand
    GITLAB_URL = os.environ.get('GITLAB_URL', 'https://gitlab.rc.uab.edu')
    GITLAB_API_URL = os.environ.get('GITLAB_API_URL', 'https://gitlab.rc.uab.edu/api/v4')
    GITLAB_TOKEN = os.environ.get('GITLAB_TOKEN', '')

    # Conda settings
    CONDA_PATH = os.environ.get('CONDA_PATH', '/opt/miniconda3/bin/conda')

    # Jupyter settings
    JUPYTER_PATH = os.environ.get('JUPYTER_PATH', '/opt/miniconda3/bin/jupyter')

    # Git settings
    GIT_USER_NAME = os.environ.get('GIT_USER_NAME', '')
    GIT_USER_EMAIL = os.environ.get('GIT_USER_EMAIL', '')


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    TESTING = False


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True  # Enable in production with HTTPS


class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'


# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
