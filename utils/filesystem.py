import os
import shutil
import logging
from flask import current_app
from models import AuditLog
from extensions import db
import json
from datetime import datetime

logger = logging.getLogger(__name__)


def ensure_directories(log_initialization=False):
    """Ensure all required directories exist."""
    directories = [
        current_app.config['UBRITE_ROOT'],
        current_app.config['DB_ROOT'],
        current_app.config.get('LOGS_DIR', '/tmp/ubrite_logs'),
        current_app.config.get('UPLOAD_FOLDER', os.path.join(current_app.config['UBRITE_ROOT'], 'uploads')),
        os.path.join(current_app.config['UBRITE_ROOT'], '.config')
    ]

    created_dirs = []
    for directory in directories:
        if not os.path.exists(directory):
            try:
                os.makedirs(directory, exist_ok=True)
                created_dirs.append(directory)
                if log_initialization:
                    logger.info(f"Created directory: {directory}")
            except Exception as e:
                logger.error(f"Failed to create directory {directory}: {str(e)}")
                return False

    if log_initialization and created_dirs:
        logger.info(f"Initialized {len(created_dirs)} directories")

    return True


def get_directory_status():
    """Get the status of all required directories."""
    directories = {
        'ubrite_root': os.path.exists(current_app.config['UBRITE_ROOT']),
        'db_root': os.path.exists(current_app.config['DB_ROOT']),
        'logs_dir': os.path.exists(current_app.config.get('LOGS_DIR', '/tmp/ubrite_logs')),
        'temp_root': os.path.exists('/tmp')
    }

    return directories


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
        gitignore_content = """
# Python
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

# OS
.DS_Store
Thumbs.db

# IDE
.vscode/
.idea/
*.swp
*.swo
"""

        with open(os.path.join(workspace_path, '.gitignore'), 'w') as f:
            f.write(gitignore_content.strip())

        logger.info(f"Created workspace directory: {workspace_path}")
        return True

    except Exception as e:
        logger.error(f"Failed to create workspace directory {workspace_path}: {str(e)}")
        return False


def delete_workspace_directory(workspace_path):
    """Safely delete a workspace directory."""
    try:
        if os.path.exists(workspace_path):
            shutil.rmtree(workspace_path)
            logger.info(f"Deleted workspace directory: {workspace_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to delete workspace directory {workspace_path}: {str(e)}")
        return False


def log_event(workspace_id, event_type, details):
    """Log an event to the audit log."""
    try:
        audit_log = AuditLog(
            workspace_id=workspace_id,
            event_type=event_type,
            details=json.dumps(details) if details else None,
            timestamp=datetime.utcnow()
        )
        db.session.add(audit_log)
        db.session.commit()
        logger.info(f"Logged event: {event_type} for workspace {workspace_id}")
    except Exception as e:
        logger.error(f"Failed to log event {event_type}: {str(e)}")
        db.session.rollback()


def get_workspace_size(workspace_path):
    """Get the total size of a workspace directory."""
    try:
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(workspace_path):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                if os.path.exists(filepath):
                    total_size += os.path.getsize(filepath)
        return total_size
    except Exception as e:
        logger.error(f"Failed to calculate workspace size for {workspace_path}: {str(e)}")
        return 0


def cleanup_temp_files():
    """Clean up temporary files older than 24 hours."""
    try:
        temp_dir = '/tmp'
        current_time = datetime.now().timestamp()

        for filename in os.listdir(temp_dir):
            if filename.startswith('ubrite_'):
                filepath = os.path.join(temp_dir, filename)
                if os.path.isfile(filepath):
                    file_age = current_time - os.path.getmtime(filepath)
                    if file_age > 86400:  # 24 hours
                        os.remove(filepath)
                        logger.info(f"Cleaned up temp file: {filepath}")

        return True
    except Exception as e:
        logger.error(f"Failed to cleanup temp files: {str(e)}")
        return False


def backup_workspace(workspace_path, backup_path):
    """Create a backup of a workspace."""
    try:
        if os.path.exists(workspace_path):
            shutil.copytree(workspace_path, backup_path)
            logger.info(f"Created backup: {workspace_path} -> {backup_path}")
            return True
        return False
    except Exception as e:
        logger.error(f"Failed to backup workspace {workspace_path}: {str(e)}")
        return False


def restore_workspace(backup_path, workspace_path):
    """Restore a workspace from backup."""
    try:
        if os.path.exists(backup_path):
            if os.path.exists(workspace_path):
                shutil.rmtree(workspace_path)
            shutil.copytree(backup_path, workspace_path)
            logger.info(f"Restored workspace: {backup_path} -> {workspace_path}")
            return True
        return False
    except Exception as e:
        logger.error(f"Failed to restore workspace from {backup_path}: {str(e)}")
        return False
