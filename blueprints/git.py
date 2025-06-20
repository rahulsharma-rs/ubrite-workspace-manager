from flask import Blueprint, request, jsonify, current_app
from models import Workspace
from services.git_config_service import GitConfigService
from services.gitlab_service import GitLabService
from utils.filesystem import log_event
import os
import subprocess
import logging

git_bp = Blueprint('git', __name__)
logger = logging.getLogger(__name__)


def get_analytics_service():
    """Get analytics service instance."""
    try:
        from services.analytics_service import AnalyticsService
        return AnalyticsService()
    except ImportError:
        logger.warning("AnalyticsService not available")
        return None


@git_bp.route('/<int:workspace_id>/status')
def git_status(workspace_id):
    """Get git status for a workspace."""
    try:
        workspace = Workspace.query.get_or_404(workspace_id)

        if not os.path.exists(workspace.path):
            return jsonify({
                'success': False,
                'message': 'Workspace directory does not exist'
            }), 404

        # Check if it's a git repository
        git_dir = os.path.join(workspace.path, '.git')
        if not os.path.exists(git_dir):
            return jsonify({
                'success': True,
                'is_git_repo': False,
                'message': 'Not a git repository'
            })

        # Get git status
        try:
            result = subprocess.run(
                ['git', 'status', '--porcelain'],
                cwd=workspace.path,
                capture_output=True,
                text=True,
                check=True
            )

            # Parse status output
            changes = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    status = line[:2]
                    filename = line[3:]
                    changes.append({
                        'status': status,
                        'filename': filename
                    })

            # Get current branch
            branch_result = subprocess.run(
                ['git', 'branch', '--show-current'],
                cwd=workspace.path,
                capture_output=True,
                text=True,
                check=True
            )
            current_branch = branch_result.stdout.strip()

            # Track analytics
            analytics = get_analytics_service()
            if analytics:
                analytics.track_event('git_status_checked', {
                    'ws_id': workspace_id,
                    'has_changes': len(changes) > 0,
                    'branch': current_branch
                })

            return jsonify({
                'success': True,
                'is_git_repo': True,
                'current_branch': current_branch,
                'changes': changes,
                'has_changes': len(changes) > 0
            })

        except subprocess.CalledProcessError as e:
            logger.error(f"Git status failed: {str(e)}")
            return jsonify({
                'success': False,
                'message': f'Git status failed: {e.stderr}'
            }), 500

    except Exception as e:
        logger.error(f"Error getting git status: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@git_bp.route('/<int:workspace_id>/commits')
def git_commits(workspace_id):
    """Get Git commits for a workspace."""
    try:
        workspace = Workspace.query.get_or_404(workspace_id)

        # Check if workspace has a GitLab repo ID
        if not workspace.gitlab_repo_id:
            logger.warning(f"Workspace {workspace_id} has no GitLab repo ID")
            return jsonify({
                'success': True,
                'commits': []
            })

        gitlab_service = GitLabService()
        try:
            commits = gitlab_service.get_commits(workspace.gitlab_repo_id)

            return jsonify({
                'success': True,
                'commits': commits
            })
        except Exception as e:
            logger.error(f"Error getting commits from GitLab: {str(e)}")
            return jsonify({
                'success': False,
                'message': f"Failed to get commits: {str(e)}"
            }), 500
    except Exception as e:
        logger.error(f"Error in git_commits: {str(e)}")
        return jsonify({
            'success': False,
            'message': f"An error occurred: {str(e)}"
        }), 500


@git_bp.route('/<int:workspace_id>/commit', methods=['POST'])
def git_commit(workspace_id):
    """Commit changes in a workspace."""
    try:
        workspace = Workspace.query.get_or_404(workspace_id)
        data = request.json

        commit_message = data.get('message', 'Auto-commit from UBRITE')
        add_all = data.get('add_all', True)

        if not os.path.exists(workspace.path):
            return jsonify({
                'success': False,
                'message': 'Workspace directory does not exist'
            }), 404

        # Check if it's a git repository
        git_dir = os.path.join(workspace.path, '.git')
        if not os.path.exists(git_dir):
            return jsonify({
                'success': False,
                'message': 'Not a git repository'
            }), 400

        try:
            # Add files if requested
            if add_all:
                subprocess.run(
                    ['git', 'add', '.'],
                    cwd=workspace.path,
                    check=True
                )

            # Commit changes
            result = subprocess.run(
                ['git', 'commit', '-m', commit_message],
                cwd=workspace.path,
                capture_output=True,
                text=True,
                check=True
            )

            # Log the event
            log_event(workspace_id, 'git_commit', {
                'message': commit_message,
                'add_all': add_all
            })

            # Track analytics
            analytics = get_analytics_service()
            if analytics:
                analytics.track_event('git_commit', {
                    'ws_id': workspace_id,
                    'add_all': add_all
                })

            return jsonify({
                'success': True,
                'message': 'Changes committed successfully',
                'output': result.stdout
            })

        except subprocess.CalledProcessError as e:
            if 'nothing to commit' in e.stdout:
                return jsonify({
                    'success': True,
                    'message': 'No changes to commit',
                    'output': e.stdout
                })
            else:
                logger.error(f"Git commit failed: {str(e)}")
                return jsonify({
                    'success': False,
                    'message': f'Git commit failed: {e.stderr or e.stdout}'
                }), 500

    except Exception as e:
        logger.error(f"Error committing changes: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@git_bp.route('/<int:workspace_id>/push', methods=['POST'])
def git_push(workspace_id):
    """Push changes to remote repository."""
    try:
        workspace = Workspace.query.get_or_404(workspace_id)

        if not os.path.exists(workspace.path):
            return jsonify({
                'success': False,
                'message': 'Workspace directory does not exist'
            }), 404

        # Check if it's a git repository
        git_dir = os.path.join(workspace.path, '.git')
        if not os.path.exists(git_dir):
            return jsonify({
                'success': False,
                'message': 'Not a git repository'
            }), 400

        try:
            # Push to origin
            result = subprocess.run(
                ['git', 'push'],
                cwd=workspace.path,
                capture_output=True,
                text=True,
                check=True
            )

            # Log the event
            log_event(workspace_id, 'git_push', {})

            # Track analytics
            analytics = get_analytics_service()
            if analytics:
                analytics.track_event('git_push', {
                    'ws_id': workspace_id
                })

            return jsonify({
                'success': True,
                'message': 'Changes pushed successfully',
                'output': result.stdout
            })

        except subprocess.CalledProcessError as e:
            logger.error(f"Git push failed: {str(e)}")
            return jsonify({
                'success': False,
                'message': f'Git push failed: {e.stderr or e.stdout}'
            }), 500

    except Exception as e:
        logger.error(f"Error pushing changes: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@git_bp.route('/<int:workspace_id>/pull', methods=['POST'])
def git_pull(workspace_id):
    """Pull changes from remote repository."""
    try:
        workspace = Workspace.query.get_or_404(workspace_id)

        if not os.path.exists(workspace.path):
            return jsonify({
                'success': False,
                'message': 'Workspace directory does not exist'
            }), 404

        # Check if it's a git repository
        git_dir = os.path.join(workspace.path, '.git')
        if not os.path.exists(git_dir):
            return jsonify({
                'success': False,
                'message': 'Not a git repository'
            }), 400

        try:
            # Pull from origin
            result = subprocess.run(
                ['git', 'pull'],
                cwd=workspace.path,
                capture_output=True,
                text=True,
                check=True
            )

            # Log the event
            log_event(workspace_id, 'git_pull', {})

            # Track analytics
            analytics = get_analytics_service()
            if analytics:
                analytics.track_event('git_pull', {
                    'ws_id': workspace_id
                })

            return jsonify({
                'success': True,
                'message': 'Changes pulled successfully',
                'output': result.stdout
            })

        except subprocess.CalledProcessError as e:
            logger.error(f"Git pull failed: {str(e)}")
            return jsonify({
                'success': False,
                'message': f'Git pull failed: {e.stderr or e.stdout}'
            }), 500

    except Exception as e:
        logger.error(f"Error pulling changes: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@git_bp.route('/<int:workspace_id>/init', methods=['POST'])
def git_init(workspace_id):
    """Initialize git repository in workspace."""
    try:
        workspace = Workspace.query.get_or_404(workspace_id)

        if not os.path.exists(workspace.path):
            return jsonify({
                'success': False,
                'message': 'Workspace directory does not exist'
            }), 404

        # Check if already a git repository
        git_dir = os.path.join(workspace.path, '.git')
        if os.path.exists(git_dir):
            return jsonify({
                'success': False,
                'message': 'Already a git repository'
            }), 400

        try:
            # Initialize git repository
            subprocess.run(
                ['git', 'init'],
                cwd=workspace.path,
                check=True
            )

            # Apply git configuration
            git_config_service = GitConfigService()
            git_config_service.apply_git_config_to_repository(workspace.path)

            # Log the event
            log_event(workspace_id, 'git_init', {})

            # Track analytics
            analytics = get_analytics_service()
            if analytics:
                analytics.track_event('git_init', {
                    'ws_id': workspace_id
                })

            return jsonify({
                'success': True,
                'message': 'Git repository initialized successfully'
            })

        except subprocess.CalledProcessError as e:
            logger.error(f"Git init failed: {str(e)}")
            return jsonify({
                'success': False,
                'message': f'Git init failed: {e.stderr}'
            }), 500

    except Exception as e:
        logger.error(f"Error initializing git repository: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@git_bp.route('/<int:workspace_id>/clone', methods=['POST'])
def git_clone(workspace_id):
    """Clone a repository into workspace."""
    try:
        workspace = Workspace.query.get_or_404(workspace_id)
        data = request.json

        repo_url = data.get('repo_url')
        if not repo_url:
            return jsonify({
                'success': False,
                'message': 'Repository URL is required'
            }), 400

        if not os.path.exists(workspace.path):
            return jsonify({
                'success': False,
                'message': 'Workspace directory does not exist'
            }), 404

        # Check if directory is empty
        if os.listdir(workspace.path):
            return jsonify({
                'success': False,
                'message': 'Workspace directory is not empty'
            }), 400

        try:
            # Clone repository
            result = subprocess.run(
                ['git', 'clone', repo_url, '.'],
                cwd=workspace.path,
                capture_output=True,
                text=True,
                check=True
            )

            # Apply git configuration
            git_config_service = GitConfigService()
            git_config_service.apply_git_config_to_repository(workspace.path)

            # Log the event
            log_event(workspace_id, 'git_clone', {
                'repo_url': repo_url
            })

            # Track analytics
            analytics = get_analytics_service()
            if analytics:
                analytics.track_event('git_clone', {
                    'ws_id': workspace_id
                })

            return jsonify({
                'success': True,
                'message': 'Repository cloned successfully',
                'output': result.stdout
            })

        except subprocess.CalledProcessError as e:
            logger.error(f"Git clone failed: {str(e)}")
            return jsonify({
                'success': False,
                'message': f'Git clone failed: {e.stderr}'
            }), 500

    except Exception as e:
        logger.error(f"Error cloning repository: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@git_bp.route('/<int:workspace_id>/branch', methods=['POST'])
def git_branch(workspace_id):
    """Create a new Git branch."""
    try:
        workspace = Workspace.query.get_or_404(workspace_id)
        data = request.json

        branch_name = data.get('branch_name')

        if not branch_name:
            return jsonify({
                'success': False,
                'message': 'Branch name is required'
            }), 400

        # Check if workspace path exists
        if not os.path.exists(workspace.path):
            logger.error(f"Workspace path does not exist: {workspace.path}")
            return jsonify({
                'success': False,
                'message': f"Workspace path does not exist: {workspace.path}"
            }), 404

        # Check if .git directory exists
        git_dir = os.path.join(workspace.path, '.git')
        if not os.path.exists(git_dir):
            logger.error(f"Git repository not found in workspace: {workspace.path}")
            return jsonify({
                'success': False,
                'message': "Git repository not initialized in this workspace"
            }), 404

        try:
            # Create branch
            result = subprocess.run(
                ['git', 'checkout', '-b', branch_name],
                cwd=workspace.path,
                capture_output=True,
                text=True,
                check=True
            )

            # Check if remote exists before pushing
            remote_check = subprocess.run(
                ['git', 'remote'],
                cwd=workspace.path,
                capture_output=True,
                text=True
            )

            push_message = ""
            if 'origin' in remote_check.stdout.split():
                try:
                    # Try to push to GitLab
                    push_result = subprocess.run(
                        ['git', 'push', '--set-upstream', 'origin', branch_name],
                        cwd=workspace.path,
                        capture_output=True,
                        text=True,
                        check=True
                    )
                    push_message = "Branch created and pushed to remote."
                except subprocess.CalledProcessError as e:
                    # If push fails, just log it but don't fail the whole operation
                    logger.warning(f"Failed to push branch to remote: {e.stderr}")
                    push_message = "Branch created locally. Failed to push to remote."
            else:
                push_message = "Branch created locally. No remote repository configured."

            # Log the event
            log_event(workspace.id, 'git_branch_created', {
                'branch_name': branch_name
            })

            # Emit Socket.IO event
            # socketio.emit('git_branch_created', {
            #     'workspace_id': workspace_id,
            #     'branch_name': branch_name
            # })

            return jsonify({
                'success': True,
                'message': push_message
            })
        except subprocess.CalledProcessError as e:
            logger.error(f"Git branch command failed: {e.stderr}")
            return jsonify({
                'success': False,
                'message': e.stderr
            }), 500
        except Exception as e:
            logger.error(f"Unexpected error in git_branch: {str(e)}")
            return jsonify({
                'success': False,
                'message': f"An unexpected error occurred: {str(e)}"
            }), 500
    except Exception as e:
        logger.error(f"Error in git_branch: {str(e)}")
        return jsonify({
            'success': False,
            'message': f"An error occurred: {str(e)}"
        }), 500


@git_bp.route('/<int:workspace_id>/checkout', methods=['POST'])
def git_checkout(workspace_id):
    """Switch to a different branch."""
    try:
        workspace = Workspace.query.get_or_404(workspace_id)
        data = request.json

        branch_name = data.get('branch_name')

        if not branch_name:
            return jsonify({
                'success': False,
                'message': 'Branch name is required'
            }), 400

        # Check if workspace path exists
        if not os.path.exists(workspace.path):
            logger.error(f"Workspace path does not exist: {workspace.path}")
            return jsonify({
                'success': False,
                'message': f"Workspace path does not exist: {workspace.path}"
            }), 404

        # Check if .git directory exists
        git_dir = os.path.join(workspace.path, '.git')
        if not os.path.exists(git_dir):
            logger.error(f"Git repository not found in workspace: {workspace.path}")
            return jsonify({
                'success': False,
                'message': "Git repository not initialized in this workspace"
            }), 404

        try:
            # Check if there are uncommitted changes
            status_result = subprocess.run(
                ['git', 'status', '--porcelain'],
                cwd=workspace.path,
                capture_output=True,
                text=True,
                check=True
            )

            if status_result.stdout.strip() and not data.get('force', False):
                return jsonify({
                    'success': False,
                    'message': "You have uncommitted changes. Commit or stash them before switching branches.",
                    'has_changes': True
                }), 400

            # Switch branch
            checkout_command = ['git', 'checkout', branch_name]
            if data.get('force', False):
                checkout_command = ['git', 'checkout', '-f', branch_name]

            result = subprocess.run(
                checkout_command,
                cwd=workspace.path,
                capture_output=True,
                text=True,
                check=True
            )

            # Log the event
            log_event(workspace.id, 'git_branch_checkout', {
                'branch_name': branch_name,
                'force': data.get('force', False)
            })

            # Emit Socket.IO event
            # socketio.emit('git_branch_checkout', {
            #     'workspace_id': workspace_id,
            #     'branch_name': branch_name
            # })

            return jsonify({
                'success': True,
                'message': f"Switched to branch '{branch_name}'."
            })
        except subprocess.CalledProcessError as e:
            logger.error(f"Git checkout command failed: {e.stderr}")
            return jsonify({
                'success': False,
                'message': e.stderr
            }), 500
        except Exception as e:
            logger.error(f"Unexpected error in git_checkout: {str(e)}")
            return jsonify({
                'success': False,
                'message': f"An unexpected error occurred: {str(e)}"
            }), 500
    except Exception as e:
        logger.error(f"Error in git_checkout: {str(e)}")
        return jsonify({
            'success': False,
            'message': f"An error occurred: {str(e)}"
        }), 500


@git_bp.route('/<int:workspace_id>/config')
def git_config_info(workspace_id):
    """Get git configuration for a workspace."""
    try:
        workspace = Workspace.query.get_or_404(workspace_id)
        git_config_service = GitConfigService()

        # Get effective configuration for this workspace
        effective_config = git_config_service.get_workspace_git_config(workspace_id)

        # Get current configuration from the repository
        current_config = git_config_service.get_current_git_config_from_repo(workspace.path)

        return jsonify({
            'success': True,
            'effective_config': effective_config,
            'current_repo_config': current_config,
            'workspace_overrides': {
                'user_name': workspace.git_user_name_override,
                'user_email': workspace.git_user_email_override
            }
        })
    except Exception as e:
        logger.error(f"Error getting git config for workspace {workspace_id}: {str(e)}")
        return jsonify({
            'success': False,
            'message': f"An error occurred: {str(e)}"
        }), 500


@git_bp.route('/<int:workspace_id>/config', methods=['POST'])
def set_workspace_git_config(workspace_id):
    """Set workspace-specific git configuration."""
    try:
        workspace = Workspace.query.get_or_404(workspace_id)
        git_config_service = GitConfigService()
        data = request.json

        user_name = data.get('user_name')
        user_email = data.get('user_email')

        # Validate configuration
        errors = git_config_service.validate_git_config(user_name, user_email)
        if errors:
            return jsonify({
                'success': False,
                'message': 'Validation failed',
                'errors': errors
            }), 400

        # Set workspace-specific configuration
        git_config_service.set_workspace_git_config(workspace_id, user_name, user_email)

        # Apply configuration to the repository if it exists
        if os.path.exists(os.path.join(workspace.path, '.git')):
            git_config_service.apply_git_config_to_repository(workspace.path)

        # Log the event
        log_event(workspace.id, 'workspace_git_config_updated', {
            'user_name': user_name,
            'user_email': user_email
        })

        return jsonify({
            'success': True,
            'message': 'Workspace git configuration updated successfully'
        })

    except Exception as e:
        logger.error(f"Error setting git config for workspace {workspace_id}: {str(e)}")
        return jsonify({
            'success': False,
            'message': f"An error occurred: {str(e)}"
        }), 500
