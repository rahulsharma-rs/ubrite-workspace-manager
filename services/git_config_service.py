import subprocess
import logging

logger = logging.getLogger(__name__)


class GitConfigService:
    """
    Service for managing Git configuration.
    """

    def __init__(self):
        pass

    def validate_git_config(self, user_name=None, user_email=None, **kwargs):
        """
        Validate git configuration parameters.

        Returns:
            list: List of validation errors (empty if valid)
        """
        errors = []

        if not user_name or not user_name.strip():
            errors.append("Git user name is required")

        if not user_email or not user_email.strip():
            errors.append("Git user email is required")
        elif '@' not in user_email:
            errors.append("Git user email must be a valid email address")

        return errors

    def set_global_git_config(self, user_name=None, user_email=None, ssh_key_path=None,
                              signing_key=None, default_branch=None):
        """
        Set global git configuration.

        Args:
            user_name (str): Git user name
            user_email (str): Git user email
            ssh_key_path (str): Path to SSH key
            signing_key (str): GPG signing key
            default_branch (str): Default branch name
        """
        try:
            if user_name:
                subprocess.run(['git', 'config', '--global', 'user.name', user_name], check=True)

            if user_email:
                subprocess.run(['git', 'config', '--global', 'user.email', user_email], check=True)

            if ssh_key_path:
                subprocess.run(['git', 'config', '--global', 'core.sshCommand', f'ssh -i {ssh_key_path}'], check=True)

            if signing_key:
                subprocess.run(['git', 'config', '--global', 'user.signingkey', signing_key], check=True)
                subprocess.run(['git', 'config', '--global', 'commit.gpgsign', 'true'], check=True)

            if default_branch:
                subprocess.run(['git', 'config', '--global', 'init.defaultBranch', default_branch], check=True)

            logger.info("Global git configuration updated successfully")

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to set git config: {str(e)}")
            raise Exception(f"Failed to set git configuration: {str(e)}")
