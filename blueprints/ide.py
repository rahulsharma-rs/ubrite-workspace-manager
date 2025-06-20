from flask import Blueprint, request, jsonify, current_app
from models import Workspace
from services.ide_service import IDEService
from utils.filesystem import log_event
import logging

ide_bp = Blueprint('ide', __name__)
logger = logging.getLogger(__name__)


def get_analytics_service():
    """Get analytics service instance."""
    try:
        from services.analytics_service import AnalyticsService
        return AnalyticsService()
    except ImportError:
        logger.warning("AnalyticsService not available")
        return None


@ide_bp.route('/<int:workspace_id>/launch/<ide_type>')
def launch_ide(workspace_id, ide_type):
    """Launch an IDE for a workspace."""
    try:
        workspace = Workspace.query.get_or_404(workspace_id)
        ide_service = IDEService()

        if ide_type.lower() == 'jupyter':
            success, result = ide_service.launch_jupyter(workspace.path)

            if success:
                # Log the event
                log_event(workspace_id, 'ide_launched', {
                    'ide_type': ide_type,
                    'url': result.get('url')
                })

                # Track analytics
                analytics = get_analytics_service()
                if analytics:
                    analytics.track_event('ide_launched', {
                        'ws_id': workspace_id,
                        'ide_type': ide_type
                    })

                return jsonify({
                    'success': True,
                    'message': 'IDE launched successfully',
                    'url': result.get('url'),
                    'port': result.get('port')
                })
            else:
                return jsonify({
                    'success': False,
                    'message': result.get('message', 'Failed to launch IDE')
                }), 500
        else:
            return jsonify({
                'success': False,
                'message': f'Unsupported IDE type: {ide_type}'
            }), 400

    except Exception as e:
        logger.error(f"Error launching IDE: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@ide_bp.route('/<int:workspace_id>/status')
def ide_status(workspace_id):
    """Get IDE status for a workspace."""
    try:
        workspace = Workspace.query.get_or_404(workspace_id)
        ide_service = IDEService()

        # Check Jupyter availability
        jupyter_available, jupyter_message = ide_service.check_jupyter_installation()

        # Check if Jupyter is running for this workspace
        jupyter_running = ide_service.is_jupyter_running(workspace.path)

        # Track analytics
        analytics = get_analytics_service()
        if analytics:
            analytics.track_event('ide_status_checked', {
                'ws_id': workspace_id,
                'jupyter_available': jupyter_available,
                'jupyter_running': jupyter_running
            })

        return jsonify({
            'success': True,
            'jupyter_available': jupyter_available,
            'jupyter_message': jupyter_message,
            'jupyter_running': jupyter_running,
            'jupyter_path': ide_service.jupyter_path
        })

    except Exception as e:
        logger.error(f"Error getting IDE status: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@ide_bp.route('/<int:workspace_id>/stop/<ide_type>', methods=['POST'])
def stop_ide(workspace_id, ide_type):
    """Stop an IDE for a workspace."""
    try:
        workspace = Workspace.query.get_or_404(workspace_id)
        ide_service = IDEService()

        if ide_type.lower() == 'jupyter':
            success, message = ide_service.stop_jupyter(workspace.path)

            if success:
                # Log the event
                log_event(workspace_id, 'ide_stopped', {
                    'ide_type': ide_type
                })

                # Track analytics
                analytics = get_analytics_service()
                if analytics:
                    analytics.track_event('ide_stopped', {
                        'ws_id': workspace_id,
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
        else:
            return jsonify({
                'success': False,
                'message': f'Unsupported IDE type: {ide_type}'
            }), 400

    except Exception as e:
        logger.error(f"Error stopping IDE: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@ide_bp.route('/<int:workspace_id>/install-jupyter', methods=['POST'])
def install_jupyter(workspace_id):
    """Install Jupyter in workspace environment."""
    try:
        workspace = Workspace.query.get_or_404(workspace_id)
        ide_service = IDEService()

        success, message = ide_service.install_jupyter_in_workspace(workspace.path)

        if success:
            # Log the event
            log_event(workspace_id, 'jupyter_installed', {})

            # Track analytics
            analytics = get_analytics_service()
            if analytics:
                analytics.track_event('jupyter_installed', {
                    'ws_id': workspace_id
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
        logger.error(f"Error installing Jupyter: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@ide_bp.route('/check-jupyter')
def check_jupyter():
    """Check global Jupyter installation."""
    try:
        ide_service = IDEService()
        available, message = ide_service.check_jupyter_installation()

        return jsonify({
            'success': True,
            'available': available,
            'message': message,
            'path': ide_service.jupyter_path
        })

    except Exception as e:
        logger.error(f"Error checking Jupyter: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500
