from flask import Blueprint, render_template, request, jsonify, current_app
from models import Settings, Workspace
from extensions import db
from services.gitlab_service import GitLabService
from services.git_config_service import GitConfigService
from services.conda_service import CondaService
from utils.encryption import encrypt_data, generate_key
from utils.filesystem import get_directory_status
import os
import json
import logging

dashboard_bp = Blueprint('dashboard', __name__)


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
            'gitlab_url': None
        }

        if settings:
            response_data['has_gitlab_pat'] = bool(settings.gitlab_pat_encrypted)
            if hasattr(settings, 'gitlab_url') and settings.gitlab_url:
                response_data['gitlab_url'] = settings.gitlab_url

        return jsonify(response_data)
    except Exception as e:
        logging.error(f"Error getting settings: {str(e)}")
        return jsonify({'error': True, 'message': str(e)}), 500


@dashboard_bp.route('/settings', methods=['POST'])
def save_settings():
    """Save application settings."""
    try:
        # Get or create settings record
        settings = Settings.query.first()
        if not settings:
            settings = Settings()
            db.session.add(settings)

        # Handle form data
        if request.content_type and 'application/json' in request.content_type:
            data = request.json
        else:
            data = request.form.to_dict()

        # Handle GitLab PAT
        gitlab_pat = data.get('gitlab_pat')
        if gitlab_pat:
            if not settings.encryption_key:
                settings.encryption_key = generate_key()
            settings.gitlab_pat_encrypted = encrypt_data(gitlab_pat, settings.encryption_key)

        # Handle GitLab URL
        gitlab_url = data.get('gitlab_url')
        if gitlab_url:
            # Ensure URL ends with /api/v4
            if not gitlab_url.endswith('/api/v4'):
                gitlab_url = gitlab_url.rstrip('/') + '/api/v4'
            settings.gitlab_url = gitlab_url

        # Handle other configuration
        conda_path = data.get('conda_path')
        if conda_path is not None:
            # Save conda path to config file
            config_dir = os.path.join(current_app.config['UBRITE_ROOT'], '.config')
            os.makedirs(config_dir, exist_ok=True)
            conda_config_file = os.path.join(config_dir, 'conda_config.json')
            with open(conda_config_file, 'w') as f:
                json.dump({'conda_path': conda_path}, f)

        jupyter_path = data.get('jupyter_path')
        if jupyter_path is not None:
            # Save jupyter path to config file
            config_dir = os.path.join(current_app.config['UBRITE_ROOT'], '.config')
            os.makedirs(config_dir, exist_ok=True)
            jupyter_config_file = os.path.join(config_dir, 'jupyter_config.json')
            with open(jupyter_config_file, 'w') as f:
                json.dump({'jupyter_path': jupyter_path}, f)

        db.session.commit()

        return jsonify({'success': True, 'message': 'Settings saved successfully'})

    except Exception as e:
        logging.error(f"Error saving settings: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@dashboard_bp.route('/test-gitlab')
def test_gitlab():
    """Test GitLab connection."""
    try:
        gitlab_service = GitLabService()
        result = gitlab_service.test_connection()
        return jsonify(result)
    except Exception as e:
        logging.error(f"Error testing GitLab connection: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Connection test failed',
            'details': str(e)
        }), 500


@dashboard_bp.route('/debug-gitlab')
def debug_gitlab():
    """Debug GitLab connection."""
    try:
        settings = Settings.query.first()
        gitlab_service = GitLabService()

        debug_info = {
            'gitlab_url': gitlab_service.api_url,
            'has_pat': bool(settings and settings.gitlab_pat_encrypted),
            'direct_request': None
        }

        # Try a direct request to get more debug info
        if settings and settings.gitlab_pat_encrypted:
            try:
                import requests
                headers = gitlab_service.headers
                api_url = gitlab_service.api_url

                response = requests.get(f"{api_url}/user", headers=headers, timeout=10)
                debug_info['direct_request'] = {
                    'status_code': response.status_code,
                    'content_type': response.headers.get('content-type', 'unknown'),
                    'content_length': len(response.content),
                    'content_preview': str(response.content[:100])
                }
            except Exception as e:
                debug_info['direct_request'] = {
                    'error': str(e)
                }

        return jsonify(debug_info)

    except Exception as e:
        logging.error(f"Error debugging GitLab: {str(e)}")
        return jsonify({'error': str(e)}), 500


@dashboard_bp.route('/git-config', methods=['GET'])
def get_git_config():
    """Get git configuration."""
    try:
        git_service = GitConfigService()
        config = git_service.get_global_git_config()

        return jsonify({
            'success': True,
            'config': config or {}
        })
    except Exception as e:
        logging.error(f"Error getting git config: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@dashboard_bp.route('/git-config', methods=['POST'])
def save_git_config():
    """Save git configuration."""
    try:
        data = request.json
        git_service = GitConfigService()

        # Validate input
        errors = git_service.validate_git_config(
            user_name=data.get('git_user_name'),
            user_email=data.get('git_user_email')
        )

        if errors:
            return jsonify({
                'success': False,
                'message': 'Validation failed',
                'errors': errors
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
        logging.error(f"Error saving git config: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@dashboard_bp.route('/env-templates')
def get_env_templates():
    """Get available environment templates."""
    try:
        templates_dir = current_app.config.get('ENV_TEMPLATES_PATH')
        templates = []

        if templates_dir and os.path.exists(templates_dir):
            for file in os.listdir(templates_dir):
                if file.endswith('.yml') or file.endswith('.yaml'):
                    template_name = file.replace('.yml', '').replace('.yaml', '')
                    templates.append(template_name)

        return jsonify({
            'success': True,
            'templates': sorted(templates)
        })

    except Exception as e:
        logging.error(f"Error getting environment templates: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e),
            'templates': []
        })


@dashboard_bp.route('/app-status')
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
        except:
            gitlab_status = {'success': False, 'message': 'GitLab service error'}

        # Conda status
        try:
            conda_service = CondaService()
            conda_available = conda_service.is_conda_available()
            conda_status = {
                'available': conda_available,
                'path': conda_service.conda_path if conda_available else None
            }
        except:
            conda_status = {'available': False, 'path': None}

        # Jupyter status
        try:
            from services.ide_service import IDEService
            ide_service = IDEService()
            jupyter_status = ide_service.check_jupyter_availability()
        except:
            jupyter_status = {'available': False, 'message': 'IDE service error'}

        return jsonify({
            'directories': directories,
            'database': database_status,
            'gitlab': gitlab_status,
            'conda': conda_status,
            'jupyter': jupyter_status
        })

    except Exception as e:
        logging.error(f"Error getting app status: {str(e)}")
        return jsonify({
            'error': True,
            'message': str(e)
        }), 500
