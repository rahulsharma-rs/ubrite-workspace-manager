import os
from datetime import timedelta


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'hard-to-guess-string'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Get username from environment
    user = os.environ.get('USER') or 'default_user'

    # Base path for all application data
    BASE_PATH = f'/data/user/{user}/ondemand/dev'

    # Base directories
    UBRITE_ROOT = os.environ.get('UBRITE_ROOT') or os.path.join(BASE_PATH, 'UBRITE')
    DB_ROOT = os.environ.get('DB_ROOT') or os.path.join(BASE_PATH, 'DB')
    TEMP_ROOT = os.environ.get('TEMP_ROOT') or os.path.join(BASE_PATH, 'UBRITE_TEMP')

    # Subdirectories
    LOGS_DIR = os.path.join(TEMP_ROOT, 'logs')
    CACHE_DIR = os.path.join(TEMP_ROOT, 'cache')
    UPLOADS_DIR = os.path.join(TEMP_ROOT, 'uploads')

    # CORS Configuration
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*').split(',')
    CORS_METHODS = ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS']
    CORS_ALLOW_HEADERS = ['Content-Type', 'Authorization', 'X-Requested-With']

    # API Configuration
    API_BASE_URL = os.environ.get('API_BASE_URL') or 'http://localhost:5000'
    FRONTEND_URL = os.environ.get('FRONTEND_URL') or 'http://localhost:3000'

    # GitLab configuration
    GITLAB_API_URL = os.environ.get('GITLAB_API_URL') or 'https://gitlab.com/api/v4'

    # Tool paths
    CONDA_PATH = os.environ.get('CONDA_PATH') or 'conda'
    JUPYTER_PATH = os.environ.get('JUPYTER_PATH') or 'jupyter'
    VSCODE_PATH = os.environ.get('VSCODE_PATH') or 'code-server'

    # Templates
    ENV_TEMPLATES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'env_templates')

    # Features
    ANALYTICS_ENABLED = True

    @staticmethod
    def init_app(app):
        """Initialize application-specific configuration."""
        # Ensure all directories exist
        directories = [
            Config.UBRITE_ROOT,
            Config.DB_ROOT,
            Config.TEMP_ROOT,
            Config.LOGS_DIR,
            Config.CACHE_DIR,
            Config.UPLOADS_DIR
        ]

        for directory in directories:
            os.makedirs(directory, exist_ok=True)


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or f'sqlite:///{os.path.join(Config.BASE_PATH, "dev.db")}'
    # Allow all origins in development
    CORS_ORIGINS = ['*']


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    ANALYTICS_ENABLED = False
    CORS_ORIGINS = ['*']


class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL') or f'sqlite:///{os.path.join(Config.BASE_PATH, "ubrite.db")}'
    # Restrict origins in production
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', 'https://yourdomain.com').split(',')


config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
