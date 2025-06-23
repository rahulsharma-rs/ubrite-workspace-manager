from flask import Blueprint, render_template, request, jsonify, current_app
from models import Settings, Workspace
from extensions import db
from services.gitlab_service import GitLabService
from services.git_config_service import GitConfigService
from services.conda_service import CondaService
from services.ide_service import IDEService
from utils.encryption import generate_key, encrypt_data, decrypt_data
from utils.filesystem import get_directory_status, log_event
import logging
import json
import os

dashboard_bp = Blueprint('dashboard', __name__)
logger = logging.getLogger(__name__)


@dashboard_bp.route('/')
def index():
    """Dashboard home page."""
    return render_template('dashboard.html')


@dashboard_bp.route('/settings', methods=['GET'])
def get_settings():
    """Get current settings."""
    try:
        settings = Settings.query.first()

        response_data = {
            'has_gitlab_pat': False,
            'gitlab_url': 'https://gitlab.rc.uab.edu',  # Default GitLab URL
            'gitlab_status': None
        }

        if settings:
            response_data['has_gitlab_pat'] = bool(settings.gitlab_pat_encrypted)
            if hasattr(settings, 'gitlab_url') and settings.gitlab_url:
                # Remove /api/v4 for display
                display_url = settings.gitlab_url.replace('/api/v4', '')
                response_data['gitlab_url'] = display_url

            # Check token status if configured
            if settings.gitlab_pat_encrypted:
                try:
                    gitlab_service = GitLabService()
                    token_status = gitlab_service.check_token_status()
                    response_data['gitlab_status'] = token_status
                except Exception as e:
                    logger.error(f"Error checking GitLab status: {str(e)}")
                    response_data['gitlab_status'] = {
                        'configured': False,
                        'valid': False,
                        'message': f'Status check failed: {str(e)}',
                        'error_code': 'STATUS_ERROR'
                    }

        return jsonify(response_data)
    except Exception as e:
        logger.error(f"Error getting settings: {str(e)}")
        return jsonify({'error': True, 'message': str(e)}), 500


@dashboard_bp.route('/validate-gitlab-token', methods=['POST'])
def validate_gitlab_token():
    """Validate GitLab token before saving."""
    try:
        # Handle both JSON and form data
        if request.is_json:
            data = request.json or {}
        else:
            data = request.form.to_dict()

        token = data.get('token', '').strip()
        gitlab_url = data.get('gitlab_url', 'https://gitlab.rc.uab.edu').strip()

        logger.info(f"Validating GitLab token for URL: {gitlab_url}")

        if not token:
            return jsonify({
                'valid': False,
                'message': 'Token is required',
                'error_code': 'MISSING_TOKEN'
            }), 400

        # Ensure URL has correct format - always use external GitLab
        if not gitlab_url.startswith('http'):
            gitlab_url = 'https://gitlab.rc.uab.edu'

        # Remove any trailing slashes and ensure it doesn't have /api/v4
        gitlab_url = gitlab_url.rstrip('/')
        if gitlab_url.endswith('/api/v4'):
            gitlab_url = gitlab_url.replace('/api/v4', '')

        try:
            gitlab_service = GitLabService()
            validation_result = gitlab_service.validate_token(token, gitlab_url=gitlab_url)

            logger.info(f"Token validation result: {validation_result.get('valid', False)}")
            return jsonify(validation_result)
        except Exception as e:
            logger.error(f"GitLab service error: {str(e)}")
            return jsonify({
                'valid': False,
                'message': f'Service error: {str(e)}',
                'error_code': 'SERVICE_ERROR'
            }), 500

    except Exception as e:
        logger.error(f"Error validating GitLab token: {str(e)}")
        return jsonify({
            'valid': False,
            'message': f'Validation error: {str(e)}',
            'error_code': 'VALIDATION_ERROR'
        }), 500


@dashboard_bp.route('/settings', methods=['POST'])
def save_settings():
    """Save application settings - handles both form and JSON data."""
    try:
        # Handle both JSON and form data for backward compatibility
        if request.is_json:
            data = request.json or {}
        else:
            data = request.form.to_dict()
            # Handle form data from old templates
            if 'gitlab_pat' in data:
                data['gitlab_token'] = data.pop('gitlab_pat')

        logger.info(f"Saving settings: {list(data.keys())}")

        # Get or create settings record
        settings = Settings.query.first()
        if not settings:
            settings = Settings()
            settings.encryption_key = generate_key()
            db.session.add(settings)

        # Handle GitLab settings
        gitlab_url = data.get('gitlab_url', 'https://gitlab.rc.uab.edu').strip()
        gitlab_token = (data.get('gitlab_token') or data.get('gitlab_pat', '')).strip()

        # Always ensure we have a proper GitLab URL
        if not gitlab_url.startswith('http'):
            gitlab_url = 'https://gitlab.rc.uab.edu'

        # Clean up the URL
        gitlab_url = gitlab_url.rstrip('/')
        if gitlab_url.endswith('/api/v4'):
            gitlab_url = gitlab_url.replace('/api/v4', '')

        # Save the API URL format for internal use
        api_url = f"{gitlab_url}/api/v4"
        settings.gitlab_url = api_url

        logger.info(f"Setting GitLab URL to: {api_url}")

        if gitlab_token:
            # For backward compatibility, if validation is not explicitly requested, just save
            validate_token = data.get('validate_token', True)

            if validate_token:
                # Validate token before saving
                try:
                    gitlab_service = GitLabService()
                    validation_result = gitlab_service.validate_token(gitlab_token, gitlab_url=gitlab_url)

                    if not validation_result.get('valid', False):
                        return jsonify({
                            'success': False,
                            'message': validation_result.get('message', 'Token validation failed'),
                            'error_code': validation_result.get('error_code'),
                            'validation_result': validation_result
                        }), 400
                except Exception as e:
                    logger.error(f"Token validation failed: {str(e)}")
                    return jsonify({
                        'success': False,
                        'message': f'Token validation failed: {str(e)}',
                        'error_code': 'VALIDATION_ERROR'
                    }), 500
            else:
                # Legacy mode - just save without validation
                validation_result = {'valid': True, 'message': 'Token saved without validation'}

            # Token is valid or validation skipped, encrypt and save
            if not settings.encryption_key:
                settings.encryption_key = generate_key()
            settings.gitlab_pat_encrypted = encrypt_data(gitlab_token, settings.encryption_key)

            logger.info(f"GitLab token encrypted and saved")

            # Log the configuration
            try:
                log_event(None, 'gitlab_token_configured', {
                    'validated': validate_token,
                    'gitlab_url': gitlab_url,
                    'user': validation_result.get('user_info', {}).get('username') if validate_token else 'unknown'
                })
            except Exception as e:
                logger.warning(f"Failed to log event: {str(e)}")

        # Handle other configuration options
        conda_path = data.get('conda_path')
        if conda_path is not None:
            try:
                config_dir = os.path.join(current_app.config['UBRITE_ROOT'], '.config')
                os.makedirs(config_dir, exist_ok=True)
                with open(os.path.join(config_dir, 'conda_config.json'), 'w') as f:
                    json.dump({'conda_path': conda_path}, f)
            except Exception as e:
                logger.warning(f"Failed to save conda config: {str(e)}")

        jupyter_path = data.get('jupyter_path')
        if jupyter_path is not None:
            try:
                config_dir = os.path.join(current_app.config['UBRITE_ROOT'], '.config')
                os.makedirs(config_dir, exist_ok=True)
                with open(os.path.join(config_dir, 'jupyter_config.json'), 'w') as f:
                    json.dump({'jupyter_path': jupyter_path}, f)
            except Exception as e:
                logger.warning(f"Failed to save jupyter config: {str(e)}")

        db.session.commit()
        logger.info("Settings saved successfully to database")

        return jsonify({
            'success': True,
            'message': 'Settings saved successfully',
            'gitlab_url': gitlab_url,
            'validation_result': validation_result if gitlab_token else None
        })

    except Exception as e:
        logger.error(f"Error saving settings: {str(e)}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error saving settings: {str(e)}'
        }), 500


@dashboard_bp.route('/test-gitlab', methods=['GET'])
def test_gitlab():
    """Test GitLab connection."""
    try:
        gitlab_service = GitLabService()
        result = gitlab_service.test_connection()
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error testing GitLab connection: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Connection test failed: {str(e)}',
            'error_code': 'TEST_ERROR'
        }), 500


@dashboard_bp.route('/gitlab-status', methods=['GET'])
def gitlab_status():
    """Get current GitLab token status."""
    try:
        gitlab_service = GitLabService()
        status = gitlab_service.check_token_status()
        return jsonify(status)
    except Exception as e:
        logger.error(f"Error checking GitLab status: {str(e)}")
        return jsonify({
            'configured': False,
            'valid': False,
            'message': f'Status check failed: {str(e)}',
            'error_code': 'STATUS_ERROR'
        }), 500


@dashboard_bp.route('/debug-gitlab', methods=['GET'])
def debug_gitlab():
    """Debug GitLab configuration."""
    try:
        settings = Settings.query.first()

        debug_info = {
            'settings_exist': settings is not None,
            'gitlab_url': settings.gitlab_url if settings else None,
            'has_token': bool(settings and settings.gitlab_pat_encrypted),
            'has_encryption_key': bool(settings and settings.encryption_key),
            'default_gitlab_url': 'https://gitlab.rc.uab.edu'
        }

        if settings and settings.gitlab_pat_encrypted:
            try:
                gitlab_service = GitLabService()
                token_status = gitlab_service.check_token_status()
                debug_info['token_status'] = token_status
            except Exception as e:
                debug_info['token_status_error'] = str(e)

        return jsonify(debug_info)

    except Exception as e:
        logger.error(f"Error debugging GitLab: {str(e)}")
        return jsonify({
            'error': True,
            'message': str(e)
        })


@dashboard_bp.route('/git-config', methods=['GET'])
def get_git_config():
    """Get Git configuration."""
    try:
        git_service = GitConfigService()
        config = git_service.get_global_git_config()
        return jsonify({
            'success': True,
            'config': config or {}
        })
    except Exception as e:
        logger.error(f"Error getting Git config: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@dashboard_bp.route('/git-config', methods=['POST'])
def save_git_config():
    """Save Git configuration."""
    try:
        if request.is_json:
            data = request.json or {}
        else:
            data = request.form.to_dict()

        git_service = GitConfigService()

        # Validate configuration
        validation_errors = git_service.validate_git_config(
            user_name=data.get('git_user_name'),
            user_email=data.get('git_user_email')
        )

        if validation_errors:
            return jsonify({
                'success': False,
                'message': 'Validation failed',
                'errors': validation_errors
            }), 400

        # Save configuration
        git_service.set_global_git_config(
            user_name=data.get('git_user_name'),
            user_email=data.get('git_user_email'),
            ssh_key_path=data.get('git_ssh_key_path'),
            signing_key=data.get('git_signing_key'),
            default_branch=data.get('git_default_branch')
        )

        return jsonify({
            'success': True,
            'message': 'Git configuration saved successfully'
        })

    except Exception as e:
        logger.error(f"Error saving Git config: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@dashboard_bp.route('/test-git-config', methods=['GET'])
def test_git_config():
    """Test Git configuration."""
    try:
        git_service = GitConfigService()
        config = git_service.get_global_git_config()

        if not config or not config.get('user.name') or not config.get('user.email'):
            return jsonify({
                'success': False,
                'message': 'Git user name and email are required'
            })

        return jsonify({
            'success': True,
            'message': 'Git configuration is valid',
            'config': config
        })

    except Exception as e:
        logger.error(f"Error testing Git config: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@dashboard_bp.route('/env-templates', methods=['GET'])
def get_env_templates():
    """Get available environment templates."""
    try:
        conda_service = CondaService()
        templates = conda_service.get_available_templates()

        return jsonify({
            'success': True,
            'templates': [t['name'] for t in templates] if templates else []
        })

    except Exception as e:
        logger.error(f"Error getting environment templates: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e),
            'templates': []
        })


@dashboard_bp.route('/app-status', methods=['GET'])
def app_status():
    """Get application status."""
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
            gitlab_status = {
                'success': False,
                'message': f'GitLab service error: {str(e)}',
                'error_code': 'SERVICE_ERROR'
            }

        # Conda status
        try:
            conda_service = CondaService()
            conda_available = conda_service.is_conda_available()
            conda_status = {
                'available': conda_available,
                'path': conda_service.conda_path if conda_available else None
            }
        except Exception as e:
            conda_status = {
                'available': False,
                'path': None,
                'error': str(e)
            }

        # Jupyter status
        try:
            ide_service = IDEService()
            jupyter_available, jupyter_message = ide_service.check_jupyter_installation()
            jupyter_status = {
                'available': jupyter_available,
                'message': jupyter_message,
                'path': ide_service.jupyter_path
            }
        except Exception as e:
            jupyter_status = {
                'available': False,
                'message': f'IDE service error: {str(e)}',
                'path': None
            }

        return jsonify({
            'directories': directories,
            'database': database_status,
            'gitlab': gitlab_status,
            'conda': conda_status,
            'jupyter': jupyter_status
        })

    except Exception as e:
        logger.error(f"Error getting app status: {str(e)}")
        return jsonify({
            'error': True,
            'message': str(e)
        }), 500
