from flask import Flask
from flask_socketio import SocketIO
from config import config
from extensions import db, socketio
from blueprints.dashboard import dashboard_bp
from blueprints.workspaces import workspaces_bp
from blueprints.git import git_bp
from blueprints.ide import ide_bp
from blueprints.files import files_bp
from utils.filesystem import ensure_directories
from utils.db_migrations import run_migrations
import os
import socket
import logging
import json

def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
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
    os.makedirs(app.config['LOGS_DIR'], exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(os.path.join(app.config['LOGS_DIR'], 'app.log'))
        ]
    )
    
    # Initialize extensions
    db.init_app(app)
    socketio.init_app(app, cors_allowed_origins="*")
    
    # Register blueprints
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(workspaces_bp, url_prefix='/workspaces')
    app.register_blueprint(git_bp, url_prefix='/git')
    app.register_blueprint(ide_bp, url_prefix='/ide')
    app.register_blueprint(files_bp, url_prefix='/files')
    
    # Ensure required directories exist and database is set up
    with app.app_context():
        # First create the database tables
        db.create_all()
        
        # Run database migrations
        run_migrations()
        
        # Then ensure directories exist (with logging enabled)
        ensure_directories(log_initialization=True)
    
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
