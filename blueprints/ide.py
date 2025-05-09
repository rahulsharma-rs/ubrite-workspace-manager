from flask import Blueprint, render_template, request, redirect, url_for, jsonify, current_app, Response, \
    stream_with_context
import os
import json
import logging
from services.ide_service import IDEService

ide_bp = Blueprint('ide', __name__, url_prefix='/ide')
ide_service = IDEService()


@ide_bp.route('/jupyter/<workspace_name>')
def jupyter_proxy(workspace_name):
    """Proxy requests to JupyterLab."""
    # Get the token for this workspace
    token = ide_service.tokens.get(workspace_name)
    port = ide_service.ports.get(workspace_name)

    if not token or not port:
        return "JupyterLab is not running for this workspace. Please launch it first.", 404

    # Redirect to JupyterLab
    return redirect(f"http://localhost:{port}/lab?token={token}")


@ide_bp.route('/launch/jupyter', methods=['POST'])
def launch_jupyter():
    """Launch JupyterLab for a workspace."""
    data = request.get_json()
    workspace_path = data.get('workspace_path')

    if not workspace_path:
        return jsonify({'success': False, 'message': 'Workspace path is required'})

    success, message = ide_service.launch_jupyter(workspace_path)

    if success:
        # Extract the workspace name from the path
        workspace_name = os.path.basename(workspace_path)

        # Return both the direct URL and the Flask proxy URL
        direct_url = message  # This is now the direct URL with token

        return jsonify({
            'success': True,
            'url': direct_url,
            'message': 'JupyterLab launched successfully'
        })
    else:
        return jsonify({'success': False, 'message': message})


@ide_bp.route('/stop/jupyter/<workspace_name>', methods=['POST'])
def stop_jupyter(workspace_name):
    """Stop JupyterLab for a workspace."""
    success, message = ide_service.stop_ide(workspace_name, 'jupyter')
    return jsonify({'success': success, 'message': message})


@ide_bp.route('/check/jupyter')
def check_jupyter():
    """Check if JupyterLab is installed."""
    success, message = ide_service.check_jupyter_installation()
    return jsonify({'success': success, 'message': message})
