from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from models import Workspace
from extensions import db

frontend_bp = Blueprint('frontend', __name__)


@frontend_bp.route('/')
def index():
    """Render the dashboard as the main page."""
    return render_template('dashboard.html')


@frontend_bp.route('/dashboard')
def dashboard_redirect():
    """Redirect legacy dashboard links to main page."""
    return redirect(url_for('frontend.index'))


@frontend_bp.route('/workspaces')
def workspaces():
    """Render the workspaces page."""
    return render_template('workspaces.html')


@frontend_bp.route('/workspaces/<int:workspace_id>')
def workspace_detail(workspace_id):
    """Render workspace detail page."""
    workspace = Workspace.query.get_or_404(workspace_id)
    return render_template('workspace_detail.html', workspace=workspace)


@frontend_bp.route('/workspaces/create')
def create_workspace():
    """Render workspace creation page."""
    return render_template('create_workspace.html')


@frontend_bp.route('/workspaces/<int:workspace_id>/files')
def workspace_files(workspace_id):
    """Render file explorer page."""
    workspace = Workspace.query.get_or_404(workspace_id)
    return render_template('file_explorer.html', workspace=workspace)


@frontend_bp.route('/save_url', methods=['POST'])
def save_url():
    """Handle URL saving functionality."""
    try:
        data = request.get_json()
        url = data.get('url')

        if not url:
            return jsonify({'success': False, 'message': 'URL is required'}), 400

        # Add your URL saving logic here
        # For now, just return success
        return jsonify({'success': True, 'message': 'URL saved successfully'})

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
