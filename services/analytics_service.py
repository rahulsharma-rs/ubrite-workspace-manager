def get_app_status():
    """
    Get comprehensive application status.

    Returns:
        dict: Application status information
    """
    from utils.filesystem import get_directory_status
    from services.gitlab_service import GitLabService
    from services.conda_service import CondaService
    from services.ide_service import IDEService
    from extensions import db

    status = {}

    try:
        # Directory status
        status['directories'] = get_directory_status()

        # Database status
        try:
            db.session.execute('SELECT 1')
            status['database'] = True
        except:
            status['database'] = False

        # GitLab status
        try:
            gitlab_service = GitLabService()
            gitlab_status = gitlab_service.test_connection()
            status['gitlab'] = gitlab_status
        except Exception as e:
            status['gitlab'] = {
                'success': False,
                'message': f'GitLab service error: {str(e)}',
                'error_code': 'SERVICE_ERROR'
            }

        # Conda status
        try:
            conda_service = CondaService()
            conda_available = conda_service.is_conda_available()
            status['conda'] = {
                'available': conda_available,
                'path': conda_service.conda_path if conda_available else None
            }
        except Exception as e:
            status['conda'] = {
                'available': False,
                'path': None,
                'error': str(e)
            }

        # Jupyter status
        try:
            ide_service = IDEService()
            jupyter_available, jupyter_message = ide_service.check_jupyter_installation()
            status['jupyter'] = {
                'available': jupyter_available,
                'message': jupyter_message,
                'path': ide_service.jupyter_path
            }
        except Exception as e:
            status['jupyter'] = {
                'available': False,
                'message': f'IDE service error: {str(e)}',
                'path': None
            }

    except Exception as e:
        status['error'] = True
        status['message'] = str(e)

    return status
