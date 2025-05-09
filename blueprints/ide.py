from flask import Blueprint, render_template, request, jsonify, current_app
from models import Workspace
from extensions import db
from services.ide_service import IDEService
from utils.filesystem import log_event
from services.analytics_service import AnalyticsService
import time
import logging

ide_bp = Blueprint('ide', __name__)
ide_service = IDEService()
analytics_service = AnalyticsService()

@ide_bp.route('/<int:workspace_id>/launch/<ide_type>')
def launch_ide(workspace_id, ide_type):
    """Launch an IDE for a workspace."""
    try:
        workspace = Workspace.query.get_or_404(workspace_id)
        
        start_time = time.time()
        
        # Check if JupyterLab is installed before trying to launch it
        if ide_type == 'jupyter':
            jupyter_check, jupyter_message = ide_service.check_jupyter_installation()
            if not jupyter_check:
                log_event(workspace.id, 'ide_launch_failed', {
                    'ide_type': ide_type,
                    'error': jupyter_message
                })
                return jsonify({
                    'success': False,
                    'message': jupyter_message
                }), 500
        
        if ide_type == 'jupyter':
            success, result = ide_service.launch_jupyter(workspace.path)
        elif ide_type == 'vscode':
            success, result = ide_service.launch_vscode(workspace.path)
        else:
            return jsonify({
                'success': False,
                'message': f'Unknown IDE type: {ide_type}'
            }), 400
        
        if success:
            # Log the event
            duration_sec = time.time() - start_time
            log_event(workspace.id, 'ide_launched', {
                'ide_type': ide_type,
                'duration_sec': duration_sec
            })
            
            # Track analytics
            analytics_service.track_event('ide_session_started', {
                'ide_type': ide_type,
                'duration_sec': duration_sec
            })
            
            return jsonify({
                'success': True,
                'url': result
            })
        else:
            # Log the failure
            log_event(workspace.id, 'ide_launch_failed', {
                'ide_type': ide_type,
                'error': result
            })
            
            return jsonify({
                'success': False,
                'message': result
            }), 500
    except Exception as e:
        logging.exception(f"Unexpected error launching IDE: {str(e)}")
        return jsonify({
            'success': False,
            'message': f"An unexpected error occurred: {str(e)}"
        }), 500

@ide_bp.route('/<int:workspace_id>/stop/<ide_type>')
def stop_ide(workspace_id, ide_type):
    """Stop a running IDE."""
    try:
        workspace = Workspace.query.get_or_404(workspace_id)
        
        success, message = ide_service.stop_ide(workspace.name, ide_type)
        
        if success:
            # Log the event
            log_event(workspace.id, 'ide_stopped', {
                'ide_type': ide_type
            })
            
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'message': message
            }), 500
    except Exception as e:
        logging.exception(f"Unexpected error stopping IDE: {str(e)}")
        return jsonify({
            'success': False,
            'message': f"An unexpected error occurred: {str(e)}"
        }), 500

@ide_bp.route('/check-jupyter')
def check_jupyter():
    """Check if JupyterLab is installed and available."""
    success, message = ide_service.check_jupyter_installation()
    return jsonify({
        'success': success,
        'message': message
    })
