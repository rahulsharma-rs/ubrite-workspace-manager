import json
import logging
from datetime import datetime
from flask import current_app
from models import AuditLog
from extensions import db


class AnalyticsService:
    """Service for tracking analytics and application events."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.enabled = current_app.config.get('ANALYTICS_ENABLED', True)

    def track_event(self, event_name, data=None):
        """Track an analytics event."""
        if not self.enabled:
            return

        try:
            # Log the event
            self.logger.info(f"Analytics event: {event_name} - {data}")

            # Store in audit log if workspace-related
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

        except Exception as e:
            self.logger.error(f"Error tracking analytics event: {str(e)}")


def get_app_status():
    """Get comprehensive application status."""
    from utils.filesystem import get_directory_status
    from services.gitlab_service import GitLabService
    from services.conda_service import CondaService

    try:
        # Directory status
        directories = get_directory_status()

        # Database status
        try:
            db.session.execute('SELECT 1')
            database_status = True
        except:
            database_status = False

        # GitLab status
        try:
            gitlab_service = GitLabService()
            gitlab_status = gitlab_service.test_connection()
        except Exception as e:
            gitlab_status = {'success': False, 'message': f'GitLab service error: {str(e)}'}

        # Conda status
        try:
            conda_service = CondaService()
            conda_available = conda_service.is_conda_available()
            conda_status = {
                'available': conda_available,
                'path': conda_service.conda_path if conda_available else None
            }
        except Exception as e:
            conda_status = {'available': False, 'path': None, 'error': str(e)}

        # Jupyter status
        try:
            from services.ide_service import IDEService
            ide_service = IDEService()
            jupyter_status = ide_service.check_jupyter_availability()
        except Exception as e:
            jupyter_status = {'available': False, 'message': f'IDE service error: {str(e)}'}

        return {
            'directories': directories,
            'database': database_status,
            'gitlab': gitlab_status,
            'conda': conda_status,
            'jupyter': jupyter_status
        }

    except Exception as e:
        logging.error(f"Error getting app status: {str(e)}")
        return {
            'error': True,
            'message': str(e)
        }
