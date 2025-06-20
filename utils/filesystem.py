import os
import json
import logging
import shutil
from datetime import datetime
from flask import current_app
from models import AuditLog, Workspace
from extensions import db
import subprocess


def ensure_directories():
    """Ensure all required directories exist."""
    directories = [
        current_app.config['UBRITE_ROOT'],
        current_app.config['DB_ROOT'],
        current_app.config['TEMP_ROOT'],
        current_app.config['LOGS_DIR'],
        current_app.config['CACHE_DIR'],
        current_app.config['UPLOADS_DIR']
    ]

    for directory in directories:
        try:
            os.makedirs(directory, exist_ok=True)
            logging.info(f"Ensured directory exists: {directory}")
        except Exception as e:
            logging.error(f"Failed to create directory {directory}: {str(e)}")
            raise


def create_workspace_directories(workspace_name):
    """Create the directory structure for a new workspace."""
    ubrite_root = current_app.config['UBRITE_ROOT']
    db_root = current_app.config['DB_ROOT']

    workspace_path = os.path.join(ubrite_root, workspace_name)
    db_path = os.path.join(db_root, f"{workspace_name}.db")

    # Create workspace directory
    os.makedirs(workspace_path, exist_ok=True)

    # Create workspace subdirectories
    os.makedirs(os.path.join(workspace_path, 'data'), exist_ok=True)
    os.makedirs(os.path.join(workspace_path, 'notebooks'), exist_ok=True)
    os.makedirs(os.path.join(workspace_path, 'scripts'), exist_ok=True)

    # Create an empty SQLite database file
    if not os.path.exists(db_path):
        with open(db_path, 'w') as f:
            pass

    return workspace_path, db_path


def create_workspace_directory(workspace_path):
    """Create a workspace directory with proper structure."""
    try:
        # Create main workspace directory
        os.makedirs(workspace_path, exist_ok=True)

        # Create subdirectories
        subdirs = ['data', 'notebooks', 'scripts', 'docs', 'output']
        for subdir in subdirs:
            os.makedirs(os.path.join(workspace_path, subdir), exist_ok=True)

        # Create .gitignore file
        gitignore_content = """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
ENV/
env.bak/
venv.bak/

# Jupyter Notebook
.ipynb_checkpoints

# Data files
*.csv
*.xlsx
*.json
*.pickle
*.pkl

# Output files
output/
*.log

# OS generated files
.DS_Store
.DS_Store?
._*
.Spotlight-V100
.Trashes
ehthumbs.db
Thumbs.db
"""

        with open(os.path.join(workspace_path, '.gitignore'), 'w') as f:
            f.write(gitignore_content)

        logging.info(f"Created workspace directory: {workspace_path}")
        return True

    except Exception as e:
        logging.error(f"Failed to create workspace directory {workspace_path}: {str(e)}")
        return False


def delete_workspace_directories(workspace):
    """Delete the directory structure for a workspace."""
    try:
        if os.path.exists(workspace.path):
            shutil.rmtree(workspace.path)

        if os.path.exists(workspace.db_path):
            os.remove(workspace.db_path)

        return True
    except Exception as e:
        log_event(workspace.id, 'workspace_delete_failed', {'error': str(e)})
        return False


def log_event(workspace_id, event_type, details):
    """Log an event to the audit log."""
    try:
        audit_log = AuditLog(
            workspace_id=workspace_id,
            event_type=event_type,
            details=json.dumps(details),
            timestamp=datetime.utcnow()
        )
        db.session.add(audit_log)
        db.session.commit()
        logging.info(f"Logged event: {event_type} for workspace {workspace_id}")
    except Exception as e:
        logging.error(f"Failed to log event: {str(e)}")


def get_directory_status():
    """Get the status of all required directories."""
    directories = {
        'ubrite_root': os.path.exists(current_app.config['UBRITE_ROOT']),
        'db_root': os.path.exists(current_app.config['DB_ROOT']),
        'temp_root': os.path.exists(current_app.config['TEMP_ROOT']),
        'logs_dir': os.path.exists(current_app.config['LOGS_DIR']),
        'cache_dir': os.path.exists(current_app.config['CACHE_DIR']),
        'uploads_dir': os.path.exists(current_app.config['UPLOADS_DIR'])
    }

    return directories


def get_workspace_size(workspace_path):
    """Get the total size of a workspace directory."""
    total_size = 0
    try:
        for dirpath, dirnames, filenames in os.walk(workspace_path):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                if os.path.exists(filepath):
                    total_size += os.path.getsize(filepath)
    except Exception as e:
        logging.error(f"Error calculating workspace size: {str(e)}")

    return total_size


def format_file_size(size_bytes):
    """Format file size in human readable format."""
    if size_bytes == 0:
        return "0 B"

    size_names = ["B", "KB", "MB", "GB", "TB"]
    import math
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_names[i]}"
