import subprocess
import logging
import os
import re
from typing import Dict, List, Optional


class GitConfigService:
    """Service for managing Git configuration."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def get_global_git_config(self) -> Dict[str, str]:
        """Get global Git configuration."""
        try:
            config = {}

            # Get user name
            try:
                result = subprocess.run(['git', 'config', '--global', 'user.name'],
                                        capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    config['user.name'] = result.stdout.strip()
            except Exception as e:
                self.logger.warning(f"Could not get git user.name: {str(e)}")

            # Get user email
            try:
                result = subprocess.run(['git', 'config', '--global', 'user.email'],
                                        capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    config['user.email'] = result.stdout.strip()
            except Exception as e:
                self.logger.warning(f"Could not get git user.email: {str(e)}")

            # Get default branch
            try:
                result = subprocess.run(['git', 'config', '--global', 'init.defaultBranch'],
                                        capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    config['init.defaultBranch'] = result.stdout.strip()
            except Exception as e:
                self.logger.warning(f"Could not get git init.defaultBranch: {str(e)}")

            return config

        except Exception as e:
            self.logger.error(f"Error getting Git config: {str(e)}")
            return {}

    def set_global_git_config(self, user_name: str = None, user_email: str = None,
                              ssh_key_path: str = None, signing_key: str = None,
                              default_branch: str = None) -> bool:
        """Set global Git configuration."""
        try:
            success = True

            if user_name:
                try:
                    result = subprocess.run(['git', 'config', '--global', 'user.name', user_name],
                                            capture_output=True, text=True, timeout=10)
                    if result.returncode != 0:
                        self.logger.error(f"Failed to set git user.name: {result.stderr}")
                        success = False
                except Exception as e:
                    self.logger.error(f"Error setting git user.name: {str(e)}")
                    success = False

            if user_email:
                try:
                    result = subprocess.run(['git', 'config', '--global', 'user.email', user_email],
                                            capture_output=True, text=True, timeout=10)
                    if result.returncode != 0:
                        self.logger.error(f"Failed to set git user.email: {result.stderr}")
                        success = False
                except Exception as e:
                    self.logger.error(f"Error setting git user.email: {str(e)}")
                    success = False

            if default_branch:
                try:
                    result = subprocess.run(['git', 'config', '--global', 'init.defaultBranch', default_branch],
                                            capture_output=True, text=True, timeout=10)
                    if result.returncode != 0:
                        self.logger.error(f"Failed to set git init.defaultBranch: {result.stderr}")
                        success = False
                except Exception as e:
                    self.logger.error(f"Error setting git init.defaultBranch: {str(e)}")
                    success = False

            return success

        except Exception as e:
            self.logger.error(f"Error setting Git config: {str(e)}")
            return False

    def validate_git_config(self, user_name: str = None, user_email: str = None) -> List[str]:
        """Validate Git configuration."""
        errors = []

        if not user_name or not user_name.strip():
            errors.append("Git user name is required")

        if not user_email or not user_email.strip():
            errors.append("Git user email is required")
        elif user_email and not self._is_valid_email(user_email):
            errors.append("Git user email format is invalid")

        return errors

    def _is_valid_email(self, email: str) -> bool:
        """Validate email format."""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None

    def test_git_installation(self) -> tuple[bool, str]:
        """Test if Git is installed and accessible."""
        try:
            result = subprocess.run(['git', '--version'],
                                    capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                return True, result.stdout.strip()
            else:
                return False, "Git command failed"
        except FileNotFoundError:
            return False, "Git is not installed or not in PATH"
        except Exception as e:
            return False, f"Error testing Git: {str(e)}"
