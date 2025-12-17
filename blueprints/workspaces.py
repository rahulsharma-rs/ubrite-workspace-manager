from flask import Blueprint, render_template, request, jsonify, current_app, abort
from models import Workspace
from extensions import db, socketio
from utils.filesystem import create_workspace_directories, delete_workspace_directories, log_event
from services.gitlab_service import GitLabService
from services.conda_service import CondaService
from services.python_env_service import PythonEnvService
from services.analytics_service import AnalyticsService
import os
import time
import json
import logging

workspaces_bp = Blueprint('workspaces', __name__)
analytics_service = AnalyticsService()

@workspaces_bp.route('/')
def list_workspaces():
    """List all workspaces."""
    workspaces = Workspace.query.all()
    return render_template('workspaces/list.html', workspaces=workspaces)

@workspaces_bp.route('/api/list')
def api_list_workspaces():
    """API endpoint to list all workspaces."""
    workspaces = Workspace.query.all()
    return jsonify({
        'workspaces': [w.to_dict() for w in workspaces]
    })

@workspaces_bp.route('/create', methods=['GET', 'POST'])
def create_workspace():
    """Create a new workspace."""
    if request.method == 'POST':
        data = request.json
        name = data.get('name')
        env_type = data.get('env_type', 'custom')
        git_visibility = data.get('git_visibility', 'private')
        skip_conda = data.get('skip_conda', False)
        python_env = data.get('python_env')
        
        # Validate input
        if not name:
            return jsonify({'success': False, 'message': 'Workspace name is required'}), 400
        
        # Check if workspace already exists
        existing = Workspace.query.filter_by(name=name).first()
        if existing:
            return jsonify({'success': False, 'message': 'Workspace with this name already exists'}), 400

        # GitLab configuration is required for repository creation.
        # Fail fast with a clear 4xx error instead of raising later.
        gitlab_service = GitLabService()
        if 'PRIVATE-TOKEN' not in gitlab_service.headers:
            return jsonify({
                'success': False,
                'message': 'GitLab Personal Access Token is not configured. Configure it in Dashboard → GitLab Configuration, then retry.'
            }), 400
        
        start_time = time.time()
        
        # Create workspace directories
        workspace_path, db_path = create_workspace_directories(name)
        
        # Create GitLab repository
        repo = gitlab_service.create_repository(name, visibility=git_visibility)
        
        if not repo:
            # Clean up directories if GitLab repo creation fails
            delete_workspace_directories(workspace_path, db_path)

            # If we have a concrete GitLab API error, surface it to the UI.
            if gitlab_service.last_error:
                err = gitlab_service.last_error
                hint = None
                try:
                    message = err.get('error', {}).get('message', {})
                    if isinstance(message, dict) and message.get('namespace') == ["is not valid"]:
                        hint = (
                            "GitLab rejected the target namespace. This is usually caused by either: "
                            "(1) using a Group/Project Access Token instead of a Personal Access Token, or "
                            "(2) needing to set a valid Group/Namespace ID in Dashboard → GitLab Configuration → "
                            "GitLab Namespace ID."
                        )
                except Exception:
                    hint = None
                return jsonify({
                    'success': False,
                    'message': 'Failed to create GitLab repository.',
                    'details': err
                    , 'hint': hint
                }), 400
            
            # Test GitLab connection to get more details
            connection_status = gitlab_service.test_connection()
            
            if not connection_status['success']:
                return jsonify({
                    'success': False, 
                    'message': f'Failed to create GitLab repository: {connection_status["message"]}',
                    'details': connection_status['details']
                }), 500
            else:
                return jsonify({
                    'success': False, 
                    'message': 'Failed to create GitLab repository. GitLab connection is working, but repository creation failed.'
                }), 500
        
        # Handle environment setup
        env_success = True
        env_message = "Environment setup completed"
        
        # If using an existing Python environment
        if python_env:
            python_env_service = PythonEnvService()
            env_success, env_message = python_env_service.create_symlink_to_environment(python_env, workspace_path)
            
            # Set env_type to the Python environment name
            env_type = f"existing:{python_env.get('name', 'unknown')}"
        
        # Otherwise, create a new Conda environment if not skipped
        elif not skip_conda:
            conda_service = CondaService()
            
            # Check if conda is available
            try:
                if not conda_service.is_conda_available():
                    logging.warning("Conda not available. Skipping environment creation.")
                    env_success = False
                    env_message = "Conda not found. Environment creation skipped."
                else:
                    env_success, env_message = conda_service.create_environment(workspace_path, env_type)
            except Exception as e:
                logging.error(f"Error checking Conda availability: {str(e)}")
                env_success = False
                env_message = f"Error checking Conda: {str(e)}. Environment creation skipped."
        else:
            env_message = "Environment creation skipped"
        
        # If environment setup failed but we want to continue anyway
        if not env_success and not python_env:
            # Create a placeholder directory for the environment
            os.makedirs(os.path.join(workspace_path, 'env'), exist_ok=True)
            
            # Log the warning
            logging.warning(f"Environment setup failed: {env_message}")
        
        # Create workspace record
        workspace = Workspace(
            name=name,
            path=workspace_path,
            db_path=db_path,
            gitlab_repo_id=repo['id'],
            gitlab_repo_url=repo['web_url'],
            env_type=env_type
        )
        
        db.session.add(workspace)
        db.session.commit()
        
        # Log the event
        duration_ms = int((time.time() - start_time) * 1000)
        log_event(workspace.id, 'workspace_created', {
            'name': name,
            'env_type': env_type,
            'duration_ms': duration_ms,
            'env_success': env_success,
            'python_env': python_env is not None
        })
        
        # Track analytics
        analytics_service.track_event('workspace_created', {
            'ws_id': workspace.id,
            'env_type': env_type,
            'duration_ms': duration_ms,
            'env_success': env_success,
            'python_env': python_env is not None
        })
        
        # Emit Socket.IO event
        socketio.emit('workspace_created', workspace.to_dict())
        
        response = {
            'success': True,
            'workspace': workspace.to_dict(),
            'duration_ms': duration_ms
        }
        
        # Add warning if needed
        if not env_success:
            response['warning'] = {
                'type': 'environment',
                'message': env_message
            }
        
        return jsonify(response)
    
    # GET request - render the create form
    return render_template('workspaces/create.html')

@workspaces_bp.route('/<int:workspace_id>')
def workspace_detail(workspace_id):
    """Show workspace details."""
    workspace = Workspace.query.get_or_404(workspace_id)
    return render_template('workspaces/detail.html', workspace=workspace)

@workspaces_bp.route('/api/<int:workspace_id>')
def api_workspace_detail(workspace_id):
    """API endpoint to get workspace details."""
    workspace = Workspace.query.get_or_404(workspace_id)
    
    # Update last accessed timestamp
    workspace.last_accessed = db.func.now()
    db.session.commit()
    
    return jsonify({
        'workspace': workspace.to_dict()
    })

@workspaces_bp.route('/<int:workspace_id>/delete', methods=['POST'])
def delete_workspace(workspace_id):
    """Delete a workspace."""
    workspace = Workspace.query.get_or_404(workspace_id)
    
    # Delete GitLab repository
    gitlab_service = GitLabService()
    gitlab_service.delete_repository(workspace.gitlab_repo_id)
    
    # Delete Conda environment
    conda_service = CondaService()
    conda_service.delete_environment(workspace.path)
    
    # Delete workspace directories
    delete_workspace_directories(workspace)
    
    # Log the event
    log_event(workspace.id, 'workspace_deleted', {
        'name': workspace.name
    })
    
    # Delete workspace record
    db.session.delete(workspace)
    db.session.commit()
    
    # Emit Socket.IO event
    socketio.emit('workspace_deleted', {'id': workspace_id})
    
    return jsonify({'success': True})

@workspaces_bp.route('/<int:workspace_id>/audit-log')
def audit_log(workspace_id):
    """Get the audit log for a workspace."""
    workspace = Workspace.query.get_or_404(workspace_id)
    
    logs = [log.to_dict() for log in workspace.audit_logs]
    
    return jsonify({
        'logs': logs
    })

@workspaces_bp.route('/<int:workspace_id>/export-audit-log')
def export_audit_log(workspace_id):
    """Export the audit log for a workspace as CSV."""
    workspace = Workspace.query.get_or_404(workspace_id)
    
    logs = [log.to_dict() for log in workspace.audit_logs]
    
    # Convert to CSV
    import csv
    from io import StringIO
    
    output = StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['ID', 'Event Type', 'Timestamp', 'Details'])
    
    # Write data
    for log in logs:
        writer.writerow([
            log['id'],
            log['event_type'],
            log['timestamp'],
            json.dumps(log['details'])
        ])
    
    # Return CSV file
    from flask import Response
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename=audit_log_{workspace.name}.csv'
        }
    )

@workspaces_bp.route('/check-conda')
def check_conda():
    """Check if conda is available."""
    try:
        conda_service = CondaService()
        is_available = conda_service.is_conda_available()
        
        return jsonify({
            'available': is_available,
            'path': conda_service.conda_path
        })
    except Exception as e:
        logging.error(f"Error checking Conda availability: {str(e)}")
        return jsonify({
            'available': False,
            'path': 'Error: ' + str(e),
            'error': str(e)
        }), 500

@workspaces_bp.route('/python-environments')
def python_environments():
    """Get available Python environments."""
    python_env_service = PythonEnvService()
    environments = python_env_service.get_all_environments()
    
    return jsonify({
        'environments': environments
    })
