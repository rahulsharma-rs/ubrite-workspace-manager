import subprocess
import os
import logging
from models import Settings, Workspace
from extensions import db


class GitConfigService:
    """Service for managing Git configuration across workspaces."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def get_global_git_config(self):
        """Get the global git configuration from the database."""
        settings = Settings.query.first()
        if not settings:
            return None

        return {
            'user_name': settings.git_user_name,
            'user_email': settings.git_user_email,
            'ssh_key_path': settings.git_ssh_key_path,
            'signing_key': settings.git_signing_key,
            'default_branch': settings.git_default_branch or 'main'
        }

    def set_global_git_config(self, user_name=None, user_email=None, ssh_key_path=None,
                              signing_key=None, default_branch=None):
        """Set the global git configuration in the database."""
        settings = Settings.query.first()
        if not settings:
            settings = Settings()
            db.session.add(settings)

        if user_name is not None:
            settings.git_user_name = user_name
        if user_email is not None:
            settings.git_user_email = user_email
        if ssh_key_path is not None:
            settings.git_ssh_key_path = ssh_key_path
        if signing_key is not None:
            settings.git_signing_key = signing_key
        if default_branch is not None:
            settings.git_default_branch = default_branch

        db.session.commit()
        self.logger.info("Global git configuration updated")

    def get_workspace_git_config(self, workspace_id):
        """Get the effective git configuration for a workspace."""
        workspace = Workspace.query.get(workspace_id)
        if not workspace:
            return None

        global_config = self.get_global_git_config() or {}

        # Use workspace overrides if available, otherwise fall back to global config
        return {
            'user_name': workspace.git_user_name_override or global_config.get('user_name'),
            'user_email': workspace.git_user_email_override or global_config.get('user_email'),
            'ssh_key_path': global_config.get('ssh_key_path'),
            'signing_key': global_config.get('signing_key'),
            'default_branch': global_config.get('default_branch', 'main')
        }

    def set_workspace_git_config(self, workspace_id, user_name=None, user_email=None):
        """Set workspace-specific git configuration overrides."""
        workspace = Workspace.query.get(workspace_id)
        if not workspace:
            raise ValueError(f"Workspace {workspace_id} not found")

        if user_name is not None:
            workspace.git_user_name_override = user_name
        if user_email is not None:
            workspace.git_user_email_override = user_email

        db.session.commit()
        self.logger.info(f"Workspace {workspace_id} git configuration updated")

    def apply_git_config_to_repository(self, workspace_path, config=None):
        """Apply git configuration to a specific repository."""
        if not os.path.exists(workspace_path):
            raise ValueError(f"Workspace path does not exist: {workspace_path}")

        git_dir = os.path.join(workspace_path, '.git')
        if not os.path.exists(git_dir):
            self.logger.warning(f"No git repository found at {workspace_path}")
            return False

        if config is None:
            # Try to get workspace config, fall back to global
            workspace = Workspace.query.filter_by(path=workspace_path).first()
            if workspace:
                config = self.get_workspace_git_config(workspace.id)
            else:
                config = self.get_global_git_config()

        if not config:
            self.logger.warning("No git configuration available")
            return False

        try:
            # Set user name
            if config.get('user_name'):
                subprocess.run([
                    'git', 'config', 'user.name', config['user_name']
                ], cwd=workspace_path, check=True)
                self.logger.info(f"Set git user.name to {config['user_name']} for {workspace_path}")

            # Set user email
            if config.get('user_email'):
                subprocess.run([
                    'git', 'config', 'user.email', config['user_email']
                ], cwd=workspace_path, check=True)
                self.logger.info(f"Set git user.email to {config['user_email']} for {workspace_path}")

            # Set default branch
            if config.get('default_branch'):
                try:
                    subprocess.run([
                        'git', 'config', 'init.defaultBranch', config['default_branch']
                    ], cwd=workspace_path, check=True)
                    self.logger.info(f"Set git init.defaultBranch to {config['default_branch']} for {workspace_path}")
                except subprocess.CalledProcessError:
                    # Older git versions might not support this
                    pass

            # Set signing key if provided
            if config.get('signing_key'):
                subprocess.run([
                    'git', 'config', 'user.signingkey', config['signing_key']
                ], cwd=workspace_path, check=True)
                subprocess.run([
                    'git', 'config', 'commit.gpgsign', 'true'
                ], cwd=workspace_path, check=True)
                self.logger.info(f"Set git signing key for {workspace_path}")

            return True

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to apply git config to {workspace_path}: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error applying git config to {workspace_path}: {e}")
            return False

    def get_current_git_config_from_repo(self, workspace_path):
        """Get the current git configuration from a repository."""
        if not os.path.exists(workspace_path):
            return None

        git_dir = os.path.join(workspace_path, '.git')
        if not os.path.exists(git_dir):
            return None

        try:
            config = {}

            # Get user name
            result = subprocess.run([
                'git', 'config', 'user.name'
            ], cwd=workspace_path, capture_output=True, text=True)
            if result.returncode == 0:
                config['user_name'] = result.stdout.strip()

            # Get user email
            result = subprocess.run([
                'git', 'config', 'user.email'
            ], cwd=workspace_path, capture_output=True, text=True)
            if result.returncode == 0:
                config['user_email'] = result.stdout.strip()

            # Get signing key
            result = subprocess.run([
                'git', 'config', 'user.signingkey'
            ], cwd=workspace_path, capture_output=True, text=True)
            if result.returncode == 0:
                config['signing_key'] = result.stdout.strip()

            # Get default branch
            result = subprocess.run([
                'git', 'config', 'init.defaultBranch'
            ], cwd=workspace_path, capture_output=True, text=True)
            if result.returncode == 0:
                config['default_branch'] = result.stdout.strip()

            return config

        except Exception as e:
            self.logger.error(f"Error getting git config from {workspace_path}: {e}")
            return None

    def validate_git_config(self, user_name=None, user_email=None):
        """Validate git configuration values."""
        errors = []

        if user_name is not None:
            if not user_name.strip():
                errors.append("Git user name cannot be empty")
            elif len(user_name) > 255:
                errors.append("Git user name is too long (max 255 characters)")

        if user_email is not None:
            if not user_email.strip():
                errors.append("Git user email cannot be empty")
            elif '@' not in user_email:
                errors.append("Git user email must be a valid email address")
            elif len(user_email) > 255:
                errors.append("Git user email is too long (max 255 characters)")

        return errors
