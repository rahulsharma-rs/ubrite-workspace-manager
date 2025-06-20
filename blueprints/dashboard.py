from flask import Blueprint, render_template, request, jsonify, current_app
from models import Settings
from extensions import db
from utils.encryption import generate_key, encrypt_data
from services.gitlab_service import GitLabService
from services.conda_service import CondaService
from services.ide_service import IDEService
from utils.filesystem import ensure_directories, log_event, get_directory_status
import sqlalchemy
import logging
import requests
import os
import json
from services.git_config_service import GitConfigService

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
def index():
    """Render the dashboard page."""
    return render_template('dashboard.html')


@dashboard_bp.route('/settings', methods=['GET', 'POST'])
def settings():
    """Handle settings operations."""
    if request.method == 'POST':
        # Check if this is a JSON request (for conda path, jupyter path, or vscode path)
        if request.is_json:
            data = request.json
            conda_path = data.get('conda_path')
            jupyter_path = data.get('jupyter_path')
            vscode_path = data.get('vscode_path')

            config_dir = os.path.join(current_app.config['UBRITE_ROOT'], '.config')
            os.makedirs(config_dir, exist_ok=True)

            if conda_path is not None:
                # Update the conda path in the config
                current_app.config['CONDA_PATH'] = conda_path

                # Save to a config file for persistence
                config_file = os.path.join(config_dir, 'conda_config.json')
                with open(config_file, 'w') as f:
                    json.dump({'conda_path': conda_path}, f)

                return jsonify({'success': True})

            if jupyter_path is not None:
                # Update the jupyter path in the config
                current_app.config['JUPYTER_PATH'] = jupyter_path

                # Save to a config file for persistence
                config_file = os.path.join(config_dir, 'jupyter_config.json')
                with open(config_file, 'w') as f:
                    json.dump({'jupyter_path': jupyter_path}, f)

                # Update the IDE service's jupyter path
                ide_service = IDEService()
                ide_service._jupyter_path = jupyter_path

                return jsonify({'success': True})

            return jsonify({'success': False, 'message': 'No valid configuration provided'})

        # Otherwise, handle form data (for GitLab settings)
        gitlab_pat = request.form.get('gitlab_pat')
        gitlab_url = request.form.get('gitlab_url')

        # Use default GitLab URL if not provided
        if not gitlab_url:
            gitlab_url = 'https://gitlab.com/api/v4'
        elif not gitlab_url.endswith('/api/v4'):
            # Ensure URL ends with /api/v4
            gitlab_url = gitlab_url.rstrip('/') + '/api/v4'

        # Make sure the URL has a scheme
        if not gitlab_url.startswith(('http://', 'https://')):
            gitlab_url = 'https://' + gitlab_url

        logging.info(f"Setting GitLab URL to: {gitlab_url}")

        # Validate the GitLab PAT if provided
        if gitlab_pat:
            gitlab_service = GitLabService()
            if not gitlab_service.validate_token(gitlab_pat, api_url=gitlab_url):
                return jsonify({'success': False, 'message': 'Invalid GitLab PAT or URL'}), 400

            # Encrypt and store the PAT
            key = generate_key()
            encrypted_pat = encrypt_data(gitlab_pat, key)

            settings = Settings.query.first()
            if not settings:
                try:
                    settings = Settings(
                        gitlab_pat_encrypted=encrypted_pat,
                        gitlab_url=gitlab_url,
                        encryption_key=key
                    )
                    db.session.add(settings)
                except sqlalchemy.exc.OperationalError:
                    # If gitlab_url column doesn't exist yet
                    settings = Settings(
                        gitlab_pat_encrypted=encrypted_pat,
                        encryption_key=key
                    )
                    db.session.add(settings)
            else:
                settings.gitlab_pat_encrypted = encrypted_pat
                settings.encryption_key = key
                try:
                    settings.gitlab_url = gitlab_url
                except:
                    # If gitlab_url column doesn't exist yet, ignore
                    pass
        else:
            # Just update the GitLab URL if PAT is not provided
            settings = Settings.query.first()
            if settings:
                try:
                    settings.gitlab_url = gitlab_url
                except:
                    # If gitlab_url column doesn't exist yet, ignore
                    pass
            else:
                try:
                    settings = Settings(gitlab_url=gitlab_url)
                    db.session.add(settings)
                except sqlalchemy.exc.OperationalError:
                    # If gitlab_url column doesn't exist yet
                    pass

        db.session.commit()
        log_event(None, 'settings_updated', {'type': 'gitlab_settings'})

        return jsonify({'success': True})

    # GET request - return current settings status
    settings = Settings.query.first()
    has_gitlab_pat = settings is not None and settings.gitlab_pat_encrypted is not None

    # Try to get gitlab_url, but handle the case where the column might not exist yet
    gitlab_url = None
    if settings:
        try:
            gitlab_url = settings.gitlab_url
        except:
            # If gitlab_url column doesn't exist yet, ignore
            pass

    return jsonify({
        'has_gitlab_pat': has_gitlab_pat,
        'gitlab_url': gitlab_url
    })


@dashboard_bp.route('/env-templates')
def env_templates():
    """Get available environment templates."""
    conda_service = CondaService()
    templates = conda_service.get_available_templates()

    return jsonify({
        'templates': [t['name'] for t in templates]
    })


@dashboard_bp.route('/app-status')
def app_status():
    """Get application status."""
    try:
        # Check directory status
        directory_status = get_directory_status()

        # Check database connection
        db_status = True
        try:
            db.session.execute(db.select(Settings))
            db_status = True
        except Exception as e:
            logging.error(f"Database check failed: {str(e)}")
            db_status = False

        # Check GitLab connection
        try:
            gitlab_service = GitLabService()
            gitlab_status = gitlab_service.test_connection()
        except Exception as e:
            logging.error(f"GitLab connection check failed: {str(e)}")
            gitlab_status = False

        # Check conda availability
        try:
            conda_service = CondaService()
            conda_available = conda_service.is_conda_available()
            conda_path = conda_service.conda_path
        except Exception as e:
            logging.error(f"Conda check failed: {str(e)}")
            conda_available = False
            conda_path = "Error: " + str(e)

        # Check JupyterLab availability
        try:
            ide_service = IDEService()
            jupyter_available, jupyter_message = ide_service.check_jupyter_installation()
            jupyter_path = ide_service.jupyter_path
        except Exception as e:
            logging.error(f"Jupyter check failed: {str(e)}")
            jupyter_available = False
            jupyter_message = f"Error checking Jupyter: {str(e)}"
            jupyter_path = "Unknown"

        return jsonify({
            'directories': directory_status,
            'database': db_status,
            'gitlab': gitlab_status,
            'conda': {
                'available': conda_available,
                'path': conda_path
            },
            'jupyter': {
                'available': jupyter_available,
                'message': jupyter_message,
                'path': jupyter_path
            }
        })
    except Exception as e:
        logging.error(f"Error in app_status: {str(e)}")
        return jsonify({
            'error': str(e),
            'message': 'Failed to check application status'
        }), 500


@dashboard_bp.route('/test-gitlab')
def test_gitlab():
    """Test the GitLab connection."""
    gitlab_service = GitLabService()
    return jsonify(gitlab_service.test_connection())


@dashboard_bp.route('/debug-gitlab')
def debug_gitlab():
    """Debug the GitLab connection."""
    settings = Settings.query.first()
    gitlab_url = None
    has_pat = False

    if settings:
        try:
            gitlab_url = settings.gitlab_url
        except:
            # If gitlab_url column doesn't exist yet
            pass

        has_pat = settings.gitlab_pat_encrypted is not None

    # Try a direct request to GitLab
    debug_info = {
        'has_pat': has_pat,
        'gitlab_url': gitlab_url or current_app.config['GITLAB_API_URL'],
        'direct_request': None
    }

    if has_pat:
        try:
            gitlab_service = GitLabService()
            url = debug_info['gitlab_url']

            # Make a direct request without parsing JSON
            response = requests.get(f"{url}/user", headers=gitlab_service.headers, timeout=10)

            debug_info['direct_request'] = {
                'status_code': response.status_code,
                'content_length': len(response.content),
                'content_type': response.headers.get('Content-Type', 'unknown'),
                'content_preview': str(response.content[:100]) if response.content else 'empty'
            }
        except Exception as e:
            debug_info['direct_request'] = {
                'error': str(e)
            }

    return jsonify(debug_info)


@dashboard_bp.route('/git-config', methods=['GET', 'POST'])
def git_config():
    """Handle git configuration operations."""
    git_service = GitConfigService()

    if request.method == 'POST':
        data = request.json if request.is_json else request.form

        user_name = data.get('git_user_name')
        user_email = data.get('git_user_email')
        ssh_key_path = data.get('git_ssh_key_path')
        signing_key = data.get('git_signing_key')
        default_branch = data.get('git_default_branch')

        # Validate configuration
        errors = git_service.validate_git_config(user_name, user_email)
        if errors:
            return jsonify({
                'success': False,
                'message': 'Validation failed',
                'errors': errors
            }), 400

        try:
            git_service.set_global_git_config(
                user_name=user_name,
                user_email=user_email,
                ssh_key_path=ssh_key_path,
                signing_key=signing_key,
                default_branch=default_branch
            )

            log_event(None, 'git_config_updated', {
                'user_name': user_name,
                'user_email': user_email
            })

            return jsonify({
                'success': True,
                'message': 'Git configuration saved successfully'
            })

        except Exception as e:
            logging.error(f"Error saving git configuration: {str(e)}")
            return jsonify({
                'success': False,
                'message': f'Failed to save git configuration: {str(e)}'
            }), 500

    # GET request - return current configuration
    try:
        config = git_service.get_global_git_config()
        return jsonify({
            'success': True,
            'config': config or {}
        })
    except Exception as e:
        logging.error(f"Error getting git configuration: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Failed to get git configuration: {str(e)}'
        }), 500
