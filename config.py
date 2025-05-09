import os
from datetime import timedelta


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'hard-to-guess-string'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Base directories
    UBRITE_ROOT = os.environ.get('UBRITE_ROOT') or os.path.join(os.path.expanduser('~'), 'UBRITE')
    DB_ROOT = os.environ.get('DB_ROOT') or os.path.join(os.path.expanduser('~'), 'DB')
    TEMP_ROOT = os.environ.get('TEMP_ROOT') or os.path.join(os.path.expanduser('~'), 'UBRITE_TEMP')

    # Subdirectories
    LOGS_DIR = os.path.join(TEMP_ROOT, 'logs')
    CACHE_DIR = os.path.join(TEMP_ROOT, 'cache')
    UPLOADS_DIR = os.path.join(TEMP_ROOT, 'uploads')

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


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dev.db')


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    ANALYTICS_ENABLED = False


class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ubrite.db')


config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
