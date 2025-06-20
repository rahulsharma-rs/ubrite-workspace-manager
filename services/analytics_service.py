import json
import logging
from datetime import datetime


class AnalyticsService:
    """Service for tracking analytics and application events."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._enabled = None

    @property
    def enabled(self):
        if self._enabled is None:
            try:
                from flask import current_app
                self._enabled = current_app.config.get('ANALYTICS_ENABLED', True)
            except RuntimeError:
                # No app context available, default to True
                self._enabled = True
        return self._enabled

    def track_event(self, event_name, data=None):
        """Track an analytics event."""
        if not self.enabled:
            return

        try:
            # Log the event
            self.logger.info(f"Analytics event: {event_name} - {data}")

            # Store in audit log if workspace-related and we have app context
            try:
                from flask import current_app
                from models import AuditLog
                from extensions import db

                workspace_id = data.get('ws_id') if data else None
                if workspace_id:
                    audit_log = AuditLog(
                        workspace_id=workspace_id,
                        event_type=f"analytics_{event_name}",
                        details=json.dumps(data or {}),
                        timestamp=datetime.utcnow()
                    )
                    db.session.add(audit_log)
                    db.session.commit()
            except RuntimeError:
                # No app context, skip database operations
                pass
            except Exception as e:
                self.logger.error(f"Error storing analytics in database: {str(e)}")

        except Exception as e:
            self.logger.error(f"Error tracking analytics event: {str(e)}")


def get_app_status():
    """
    Get comprehensive application status.

    Returns:
        dict: Application status information
    """
    import logging

    status = {}
    logger = logging.getLogger(__name__)

    try:
        # Directory status
        try:
            from utils.filesystem import get_directory_status
            status['directories'] = get_directory_status()
        except Exception as e:
            logger.error(f"Error getting directory status: {str(e)}")
            status['directories'] = {'error': str(e)}

        # Database status
        try:
            from extensions import db
            db.session.execute('SELECT 1')
            status['database'] = True
        except Exception as e:
            logger.error(f"Error checking database status: {str(e)}")
            status['database'] = False

        # GitLab status
        try:
            from services.gitlab_service import GitLabService
            gitlab_service = GitLabService()
            gitlab_status = gitlab_service.test_connection()
            status['gitlab'] = gitlab_status
        except Exception as e:
            logger.error(f"Error checking GitLab status: {str(e)}")
            status['gitlab'] = {
                'success': False,
                'message': f'GitLab service error: {str(e)}',
                'error_code': 'SERVICE_ERROR'
            }

        # Conda status
        try:
            from services.conda_service import CondaService
            conda_service = CondaService()
            conda_available = conda_service.is_conda_available()
            status['conda'] = {
                'available': conda_available,
                'path': conda_service.conda_path if conda_available else None
            }
        except Exception as e:
            logger.error(f"Error checking Conda status: {str(e)}")
            status['conda'] = {
                'available': False,
                'path': None,
                'error': str(e)
            }

        # Jupyter status
        try:
            from services.ide_service import IDEService
            ide_service = IDEService()
            jupyter_available, jupyter_message = ide_service.check_jupyter_installation()
            status['jupyter'] = {
                'available': jupyter_available,
                'message': jupyter_message,
                'path': ide_service.jupyter_path
            }
        except Exception as e:
            logger.error(f"Error checking Jupyter status: {str(e)}")
            status['jupyter'] = {
                'available': False,
                'message': f'IDE service error: {str(e)}',
                'path': None
            }

    except Exception as e:
        logger.error(f"Error getting app status: {str(e)}")
        status['error'] = True
        status['message'] = str(e)

    return status
