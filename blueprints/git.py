from flask import Blueprint, render_template, request, jsonify, current_app
from models import Workspace
from extensions import db, socketio
from services.gitlab_service import GitLabService
from utils.filesystem import log_event
from services.analytics_service import AnalyticsService
import subprocess
import os
import logging

git_bp = Blueprint('git', __name__)
analytics_service = AnalyticsService()
logger = logging.getLogger(__name__)


@git_bp.route('/<int:workspace_id>/init', methods=['POST'])
def git_init(workspace_id):
    """Initialize a Git repository in a workspace."""
    try:
        workspace = Workspace.query.get_or_404(workspace_id)

        # Check if workspace path exists
        if not os.path.exists(workspace.path):
            logger.error(f"Workspace path does not exist: {workspace.path}")
            return jsonify({
                'success': False,
                'message': f"Workspace path does not exist: {workspace.path}"
            }), 404

        # Check if .git directory already exists
        git_dir = os.path.join(workspace.path, '.git')
        if os.path.exists(git_dir):
            logger.warning(f"Git repository already exists in workspace: {workspace.path}")
            return jsonify({
                'success': False,
                'message': "Git repository already exists in this workspace"
            }), 400

        try:
            # Initialize Git repository
            init_result = subprocess.run(
                ['git', 'init'],
                cwd=workspace.path,
                capture_output=True,
                text=True,
                check=True
            )

            # Create initial commit
            with open(os.path.join(workspace.path, 'README.md'), 'w') as f:
                f.write(f"# {workspace.name}\n\nWorkspace created with UBRITE Workspace Manager.\n")

            # Stage README.md
            subprocess.run(
                ['git', 'add', 'README.md'],
                cwd=workspace.path,
                check=True
            )

            # Create initial commit
            commit_result = subprocess.run(
                ['git', 'commit', '-m', 'Initial commit'],
                cwd=workspace.path,
                capture_output=True,
                text=True,
                check=True
            )

            # Log the event
            log_event(workspace.id, 'git_initialized', {
                'message': 'Git repository initialized'
            })

            # Track analytics
            analytics_service.track_event('git_initialized', {
                'ws_id': workspace.id
            })

            return jsonify({
                'success': True,
                'message': 'Git repository initialized successfully'
            })
        except subprocess.CalledProcessError as e:
            logger.error(f"Git init command failed: {e.stderr}")
            return jsonify({
                'success': False,
                'message': e.stderr
            }), 500
        except Exception as e:
            logger.error(f"Unexpected error in git_init: {str(e)}")
            return jsonify({
                'success': False,
                'message': f"An unexpected error occurred: {str(e)}"
            }), 500
    except Exception as e:
        logger.error(f"Error in git_init: {str(e)}")
        return jsonify({
            'success': False,
            'message': f"An error occurred: {str(e)}"
        }), 500


@git_bp.route('/<int:workspace_id>/status')
def git_status(workspace_id):
    """Get Git status for a workspace."""
    try:
        workspace = Workspace.query.get_or_404(workspace_id)

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
            # Get current branch
            branch_result = subprocess.run(
                ['git', 'branch', '--show-current'],
                cwd=workspace.path,
                capture_output=True,
                text=True,
                check=True
            )
            current_branch = branch_result.stdout.strip()

            # Get all branches
            all_branches_result = subprocess.run(
                ['git', 'branch'],
                cwd=workspace.path,
                capture_output=True,
                text=True,
                check=True
            )

            branches = []
            for branch in all_branches_result.stdout.splitlines():
                branch_name = branch.strip()
                if branch_name.startswith('*'):
                    branch_name = branch_name[1:].strip()
                branches.append(branch_name)

            # Get status
            result = subprocess.run(
                ['git', 'status', '--porcelain'],
                cwd=workspace.path,
                capture_output=True,
                text=True,
                check=True
            )

            changes = []
            for line in result.stdout.splitlines():
                if line.strip():
                    status = line[:2].strip()
                    filename = line[3:].strip()
                    changes.append({
                        'status': status,
                        'filename': filename
                    })

            return jsonify({
                'success': True,
                'current_branch': current_branch,
                'branches': branches,
                'changes': changes
            })
        except subprocess.CalledProcessError as e:
            logger.error(f"Git status command failed: {e.stderr}")
            return jsonify({
                'success': False,
                'message': e.stderr
            }), 500
        except Exception as e:
            logger.error(f"Unexpected error in git_status: {str(e)}")
            return jsonify({
                'success': False,
                'message': f"An unexpected error occurred: {str(e)}"
            }), 500
    except Exception as e:
        logger.error(f"Error in git_status: {str(e)}")
        return jsonify({
            'success': False,
            'message': f"An error occurred: {str(e)}"
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
    """Create a Git commit."""
    try:
        workspace = Workspace.query.get_or_404(workspace_id)
        data = request.json

        message = data.get('message', 'Update')

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
            # Stage all changes
            subprocess.run(
                ['git', 'add', '.'],
                cwd=workspace.path,
                check=True
            )

            # Create commit
            result = subprocess.run(
                ['git', 'commit', '-m', message],
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
                    # Try to push to remote
                    push_result = subprocess.run(
                        ['git', 'push'],
                        cwd=workspace.path,
                        capture_output=True,
                        text=True,
                        check=True
                    )
                    push_message = "Changes committed and pushed to remote."
                except subprocess.CalledProcessError as e:
                    # If push fails, just log it but don't fail the whole operation
                    logger.warning(f"Failed to push commit to remote: {e.stderr}")
                    push_message = "Changes committed locally. Failed to push to remote."
            else:
                push_message = "Changes committed locally. No remote repository configured."

            # Log the event
            log_event(workspace.id, 'git_commit', {
                'message': message
            })

            # Track analytics
            analytics_service.track_event('git_commit', {
                'ws_id': workspace.id,
                'message': message
            })

            # Emit Socket.IO event
            socketio.emit('git_commit', {
                'workspace_id': workspace_id,
                'message': message
            })

            return jsonify({
                'success': True,
                'message': push_message
            })
        except subprocess.CalledProcessError as e:
            logger.error(f"Git commit command failed: {e.stderr}")
            return jsonify({
                'success': False,
                'message': e.stderr
            }), 500
        except Exception as e:
            logger.error(f"Unexpected error in git_commit: {str(e)}")
            return jsonify({
                'success': False,
                'message': f"An unexpected error occurred: {str(e)}"
            }), 500
    except Exception as e:
        logger.error(f"Error in git_commit: {str(e)}")
        return jsonify({
            'success': False,
            'message': f"An error occurred: {str(e)}"
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
            socketio.emit('git_branch_created', {
                'workspace_id': workspace_id,
                'branch_name': branch_name
            })

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
            socketio.emit('git_branch_checkout', {
                'workspace_id': workspace_id,
                'branch_name': branch_name
            })

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
