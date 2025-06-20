from flask import Blueprint, render_template, request, jsonify, current_app, redirect, url_for
from models import Workspace, AuditLog
from extensions import db, socketio
from services.conda_service import CondaService
from services.gitlab_service import GitLabService
from services.git_config_service import GitConfigService
from utils.filesystem import create_workspace_directory, log_event
from services.analytics_service import AnalyticsService
import os
import logging
import subprocess
import json
from datetime import datetime

workspaces_bp = Blueprint('workspaces', __name__)
analytics_service = AnalyticsService()
logger = logging.getLogger(__name__)


@workspaces_bp.route('/')
def list_workspaces():
    """List all workspaces."""
    workspaces = Workspace.query.order_by(Workspace.last_accessed.desc()).all()
    return render_template('workspaces/list.html', workspaces=workspaces)


@workspaces_bp.route('/create')
def create_workspace():
    """Show the create workspace form."""
    template = request.args.get('template')
    conda_service = CondaService()
    templates = conda_service.get_available_templates()

    return render_template('workspaces/create.html',
                           templates=templates,
                           selected_template=template)


@workspaces_bp.route('/create', methods=['POST'])
def create_workspace_post():
    """Create a new workspace."""
    try:
        data = request.json
        name = data.get('name')
        env_type = data.get('env_type')
        create_gitlab_repo = data.get('create_gitlab_repo', False)

        if not name:
            return jsonify({'success': False, 'message': 'Workspace name is required'}), 400

        # Check if workspace already exists
        existing = Workspace.query.filter_by(name=name).first()
        if existing:
            return jsonify({'success': False, 'message': 'Workspace with this name already exists'}), 400

        # Create workspace directory
        workspace_path = os.path.join(current_app.config['UBRITE_ROOT'], name)
        db_path = os.path.join(current_app.config['DB_ROOT'], f"{name}.db")

        if not create_workspace_directory(workspace_path):
            return jsonify({'success': False, 'message': 'Failed to create workspace directory'}), 500

        # Create conda environment if env_type is specified
        conda_service = CondaService()
        if env_type and conda_service.is_conda_available():
            try:
                env_path = os.path.join(workspace_path, 'env')
                success, message = conda_service.create_environment(env_path, env_type)
                if not success:
                    logger.warning(f"Failed to create conda environment: {message}")
            except Exception as e:
                logger.warning(f"Error creating conda environment: {str(e)}")

        # Create workspace record
        workspace = Workspace(
            name=name,
            path=workspace_path,
            db_path=db_path,
            env_type=env_type
        )

        # Create GitLab repository if requested
        gitlab_repo_id = None
        gitlab_repo_url = None
        if create_gitlab_repo:
            try:
                gitlab_service = GitLabService()
                repo_data = gitlab_service.create_repository(name, f"UBRITE workspace: {name}")
                if repo_data:
                    gitlab_repo_id = repo_data.get('id')
                    gitlab_repo_url = repo_data.get('web_url')
                    workspace.gitlab_repo_id = gitlab_repo_id
                    workspace.gitlab_repo_url = gitlab_repo_url
            except Exception as e:
                logger.warning(f"Failed to create GitLab repository: {str(e)}")

        db.session.add(workspace)
        db.session.commit()

        # Initialize git repository if GitLab repo was created
        if gitlab_repo_id:
            try:
                git_config_service = GitConfigService()

                # Initialize git repository
                subprocess.run(['git', 'init'], cwd=workspace_path, check=True)

                # Apply git configuration
                git_config_service.apply_git_config_to_repository(workspace_path)

                # Create initial README
                with open(os.path.join(workspace_path, 'README.md'), 'w') as f:
                    f.write(f"# {name}\n\nUBRITE workspace created with {env_type or 'custom'} environment.\n")

                # Add remote origin
                subprocess.run([
                    'git', 'remote', 'add', 'origin', gitlab_repo_url
                ], cwd=workspace_path, check=True)

                # Stage and commit initial files
                subprocess.run(['git', 'add', '.'], cwd=workspace_path, check=True)
                subprocess.run([
                    'git', 'commit', '-m', 'Initial commit'
                ], cwd=workspace_path, check=True)

                # Push to GitLab
                subprocess.run([
                    'git', 'push', '-u', 'origin', 'main'
                ], cwd=workspace_path, check=True)

            except subprocess.CalledProcessError as e:
                logger.warning(f"Git operations failed: {str(e)}")
            except Exception as e:
                logger.warning(f"Error setting up git repository: {str(e)}")

        # Log the event
        log_event(workspace.id, 'workspace_created', {
            'name': name,
            'env_type': env_type,
            'gitlab_repo_created': gitlab_repo_id is not None
        })

        # Track analytics
        analytics_service.track_event('workspace_created', {
            'ws_id': workspace.id,
            'env_type': env_type,
            'gitlab_repo': gitlab_repo_id is not None
        })

        # Emit Socket.IO event
        socketio.emit('workspace_created', {
            'workspace_id': workspace.id,
            'name': name
        })

        return jsonify({
            'success': True,
            'workspace_id': workspace.id,
            'message': 'Workspace created successfully'
        })

    except Exception as e:
        logger.error(f"Error creating workspace: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Failed to create workspace: {str(e)}'
        }), 500


@workspaces_bp.route('/<int:workspace_id>')
def workspace_detail(workspace_id):
    """Show workspace details."""
    workspace = Workspace.query.get_or_404(workspace_id)

    # Update last accessed time
    workspace.last_accessed = datetime.utcnow()
    db.session.commit()

    # Get recent audit logs
    recent_logs = AuditLog.query.filter_by(workspace_id=workspace_id) \
        .order_by(AuditLog.timestamp.desc()) \
        .limit(10).all()

    return render_template('workspaces/detail.html',
                           workspace=workspace,
                           recent_logs=recent_logs)


@workspaces_bp.route('/api/list')
def api_list_workspaces():
    """API endpoint to list all workspaces."""
    workspaces = Workspace.query.all()
    return jsonify({
        'workspaces': [w.to_dict() for w in workspaces]
    })


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
    try:
        workspace = Workspace.query.get_or_404(workspace_id)

        # Delete workspace directory
        import shutil
        if os.path.exists(workspace.path):
            shutil.rmtree(workspace.path)

        # Delete database file if it exists
        if os.path.exists(workspace.db_path):
            os.remove(workspace.db_path)

        # Delete from database
        db.session.delete(workspace)
        db.session.commit()

        # Track analytics
        analytics_service.track_event('workspace_deleted', {
            'ws_id': workspace_id
        })

        return jsonify({'success': True, 'message': 'Workspace deleted successfully'})

    except Exception as e:
        logger.error(f"Error deleting workspace: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Failed to delete workspace: {str(e)}'
        }), 500


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
    """Check if Conda is available."""
    conda_service = CondaService()
    available = conda_service.is_conda_available()

    return jsonify({
        'available': available,
        'path': conda_service.conda_path if available else None
    })


@workspaces_bp.route('/python-environments')
def python_environments():
    """Get available Python environments."""
    try:
        conda_service = CondaService()
        environments = conda_service.get_python_environments()

        return jsonify({
            'success': True,
            'environments': environments
        })
    except Exception as e:
        logger.error(f"Error getting Python environments: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e),
            'environments': []
        })
