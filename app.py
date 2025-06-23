from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
from flask_wtf.csrf import CSRFProtect
from config import config
from extensions import db, socketio, cors
from utils.filesystem import ensure_directories
import os
import socket
import logging
import json
from datetime import datetime


def create_app(config_name=None):
    app = Flask(__name__)

    # Determine config name from environment if not provided
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'default')

    # Load configuration
    try:
        app.config.from_object(config[config_name])
    except KeyError:
        # Fallback to default config if specified config doesn't exist
        app.config.from_object(config['default'])

    # Set default values for missing config keys
    app.config.setdefault('ANALYTICS_ENABLED', True)
    app.config.setdefault('CORS_ORIGINS', ['*'])
    app.config.setdefault('CORS_METHODS', ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
    app.config.setdefault('CORS_ALLOW_HEADERS', ['Content-Type', 'Authorization', 'X-CSRFToken'])

    # Initialize CSRF protection
    csrf = CSRFProtect(app)

    # Load conda path from config file if it exists
    conda_config_file = os.path.join(app.config['UBRITE_ROOT'], '.config', 'conda_config.json')
    if os.path.exists(conda_config_file):
        try:
            with open(conda_config_file, 'r') as f:
                conda_config = json.load(f)
                if 'conda_path' in conda_config:
                    app.config['CONDA_PATH'] = conda_config['conda_path']
        except Exception as e:
            print(f"Error loading conda config: {str(e)}")

    # Load jupyter path from config file if it exists
    jupyter_config_file = os.path.join(app.config['UBRITE_ROOT'], '.config', 'jupyter_config.json')
    if os.path.exists(jupyter_config_file):
        try:
            with open(jupyter_config_file, 'r') as f:
                jupyter_config = json.load(f)
                if 'jupyter_path' in jupyter_config:
                    app.config['JUPYTER_PATH'] = jupyter_config['jupyter_path']
        except Exception as e:
            print(f"Error loading jupyter config: {str(e)}")

    # Configure logging
    try:
        os.makedirs(app.config['LOGS_DIR'], exist_ok=True)
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler(os.path.join(app.config['LOGS_DIR'], 'app.log'))
            ]
        )
    except Exception as e:
        print(f"Error setting up logging: {str(e)}")
        # Fallback to basic logging
        logging.basicConfig(level=logging.INFO)

    # Initialize extensions
    db.init_app(app)

    # Configure CORS
    cors.init_app(app,
                  origins=app.config['CORS_ORIGINS'],
                  methods=app.config['CORS_METHODS'],
                  allow_headers=app.config['CORS_ALLOW_HEADERS'],
                  supports_credentials=True)

    # Configure SocketIO with CORS
    socketio.init_app(app,
                      cors_allowed_origins=app.config['CORS_ORIGINS'],
                      async_mode='threading')

    # Import and register blueprints
    try:
        from blueprints.dashboard import dashboard_bp
        from blueprints.workspaces import workspaces_bp
        from blueprints.git import git_bp
        from blueprints.ide import ide_bp
        from blueprints.files import files_bp

        app.register_blueprint(dashboard_bp)
        app.register_blueprint(workspaces_bp, url_prefix='/workspaces')
        app.register_blueprint(git_bp, url_prefix='/git')
        app.register_blueprint(ide_bp, url_prefix='/ide')
        app.register_blueprint(files_bp, url_prefix='/files')
    except Exception as e:
        print(f"Error registering blueprints: {str(e)}")
        # Continue without blueprints for debugging

    # Add debug route to list all routes
    @app.route('/debug/routes')
    def list_routes():
        routes = []
        for rule in app.url_map.iter_rules():
            routes.append({
                'endpoint': rule.endpoint,
                'methods': list(rule.methods),
                'rule': str(rule)
            })
        return jsonify({'routes': routes})

    # Add simple health check
    @app.route('/health')
    def health_check():
        return jsonify({'status': 'healthy', 'timestamp': str(datetime.utcnow())})

    # Add basic status endpoint
    @app.route('/status')
    def basic_status():
        return jsonify({
            'app': 'UBRITE Workspace Manager',
            'status': 'running',
            'timestamp': str(datetime.utcnow())
        })

    # Error handlers with CORS support
    @app.errorhandler(404)
    def not_found(error):
        if request.is_json or 'application/json' in request.headers.get('Accept', ''):
            return jsonify({'error': 'Not found'}), 404
        return render_template('404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        if request.is_json or 'application/json' in request.headers.get('Accept', ''):
            return jsonify({'error': 'Internal server error'}), 500
        return render_template('500.html'), 500

    # CSRF error handler
    @app.errorhandler(400)
    def csrf_error(error):
        if request.is_json or 'application/json' in request.headers.get('Accept', ''):
            return jsonify({'error': 'CSRF token missing or invalid'}), 400
        return render_template('400.html'), 400

    # Template context processor to make config available in templates
    @app.context_processor
    def inject_config():
        return {'config': app.config}

    # Ensure required directories exist and database is set up
    with app.app_context():
        try:
            # Ensure directories exist first
            ensure_directories(log_initialization=True)

            # Create the database tables
            db.create_all()

            # Initialize default settings safely
            try:
                from models import Settings
                from utils.encryption import generate_key
                settings = Settings.query.first()
                if not settings:
                    settings = Settings()
                    settings.encryption_key = generate_key()
                    settings.gitlab_url = 'https://gitlab.rc.uab.edu/api/v4'
                    db.session.add(settings)
                    db.session.commit()
                    app.logger.info(f"Created default settings with GitLab URL: {settings.gitlab_url}")
            except Exception as e:
                app.logger.warning(f"Could not initialize default settings: {str(e)}")

        except Exception as e:
            print(f"Error during app initialization: {str(e)}")
            # Don't fail completely, just log the error

    return app


def find_available_port(start_port=5000, max_attempts=10):
    """Find an available port starting from start_port."""
    for port in range(start_port, start_port + max_attempts):
        try:
            # Try to create a socket with the port
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(('0.0.0.0', port))
            sock.close()
            return port
        except OSError:
            continue
    # If no ports are available, return a different port outside the range
    return 8080


if __name__ == '__main__':
    app = create_app()

    # Try to find an available port
    port = find_available_port()
    logging.info(f"Starting server on port {port}")

    try:
        socketio.run(app, debug=app.config['DEBUG'], host='0.0.0.0', port=port)
    except OSError as e:
        if "Address already in use" in str(e):
            # Try one more time with a different port
            port = find_available_port(start_port=8000)
            logging.info(f"Retrying with port {port}")
            socketio.run(app, debug=app.config['DEBUG'], host='0.0.0.0', port=port)
        else:
            raise
