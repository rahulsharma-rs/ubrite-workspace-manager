import os
import json
import shutil
from flask import current_app
from models import AuditLog, Workspace
from extensions import db
import subprocess


def ensure_directories(log_initialization=True):
    """Ensure that all required directories exist."""
    # Main directories
    ubrite_root = current_app.config['UBRITE_ROOT']
    db_root = current_app.config['DB_ROOT']
    temp_root = current_app.config['TEMP_ROOT']

    # Subdirectories
    logs_dir = current_app.config['LOGS_DIR']
    cache_dir = current_app.config['CACHE_DIR']
    uploads_dir = current_app.config['UPLOADS_DIR']

    # Create all directories
    os.makedirs(ubrite_root, exist_ok=True)
    os.makedirs(db_root, exist_ok=True)
    os.makedirs(temp_root, exist_ok=True)
    os.makedirs(logs_dir, exist_ok=True)
    os.makedirs(cache_dir, exist_ok=True)
    os.makedirs(uploads_dir, exist_ok=True)

    # Create .gitkeep files to ensure directories are tracked in git
    for directory in [ubrite_root, db_root, temp_root, logs_dir, cache_dir, uploads_dir]:
        gitkeep_file = os.path.join(directory, '.gitkeep')
        if not os.path.exists(gitkeep_file):
            with open(gitkeep_file, 'w') as f:
                pass

    # Log the creation if it's the first time and logging is enabled
    if log_initialization and not os.path.exists(os.path.join(ubrite_root, '.initialized')):
        with open(os.path.join(ubrite_root, '.initialized'), 'w') as f:
            f.write(str(os.getpid()))
        try:
            log_event(None, 'system_initialized', {
                'ubrite_root': ubrite_root,
                'db_root': db_root,
                'temp_root': temp_root
            })
        except Exception as e:
            # If logging fails (e.g., table doesn't exist yet), just print a message
            print(f"Note: Could not log initialization event: {str(e)}")


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
    # Check if the table exists before trying to log
    try:
        audit_log = AuditLog(
            workspace_id=workspace_id,
            event_type=event_type,
            details=json.dumps(details)
        )
        db.session.add(audit_log)
        db.session.commit()
        return audit_log
    except Exception as e:
        print(f"Warning: Could not log event {event_type}: {str(e)}")
        return None


def get_directory_status():
    """Get the status of all required directories."""
    return {
        'ubrite_root': os.path.exists(current_app.config['UBRITE_ROOT']),
        'db_root': os.path.exists(current_app.config['DB_ROOT']),
        'temp_root': os.path.exists(current_app.config['TEMP_ROOT']),
        'logs_dir': os.path.exists(current_app.config['LOGS_DIR']),
        'cache_dir': os.path.exists(current_app.config['CACHE_DIR']),
        'uploads_dir': os.path.exists(current_app.config['UPLOADS_DIR'])
    }
