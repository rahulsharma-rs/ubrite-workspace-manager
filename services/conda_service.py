import subprocess
import os
import logging
import yaml
from flask import current_app


class CondaService:
    """Service for managing Conda environments."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.conda_path = current_app.config.get('CONDA_PATH', 'conda')

    def is_conda_available(self):
        """Check if Conda is available."""
        try:
            result = subprocess.run([self.conda_path, '--version'],
                                    capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except Exception as e:
            self.logger.error(f"Error checking Conda availability: {str(e)}")
            return False

    def get_conda_info(self):
        """Get Conda information."""
        try:
            result = subprocess.run([self.conda_path, 'info', '--json'],
                                    capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                import json
                return json.loads(result.stdout)
            return None
        except Exception as e:
            self.logger.error(f"Error getting Conda info: {str(e)}")
            return None

    def list_environments(self):
        """List all Conda environments."""
        try:
            result = subprocess.run([self.conda_path, 'env', 'list', '--json'],
                                    capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                import json
                return json.loads(result.stdout)
            return {'envs': []}
        except Exception as e:
            self.logger.error(f"Error listing Conda environments: {str(e)}")
            return {'envs': []}

    def create_environment(self, env_path, template_name=None):
        """Create a new Conda environment."""
        try:
            if template_name:
                # Use template file
                template_path = os.path.join(
                    current_app.config['ENV_TEMPLATES_PATH'],
                    f"{template_name}.yml"
                )
                if os.path.exists(template_path):
                    cmd = [self.conda_path, 'env', 'create', '-p', env_path, '-f', template_path]
                else:
                    self.logger.warning(f"Template {template_name} not found, creating basic environment")
                    cmd = [self.conda_path, 'create', '-p', env_path, 'python=3.9', '-y']
            else:
                # Create basic environment
                cmd = [self.conda_path, 'create', '-p', env_path, 'python=3.9', '-y']

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            if result.returncode == 0:
                self.logger.info(f"Conda environment created successfully at {env_path}")
                return True, "Environment created successfully"
            else:
                error_msg = result.stderr or result.stdout
                self.logger.error(f"Failed to create Conda environment: {error_msg}")
                return False, f"Failed to create environment: {error_msg}"

        except subprocess.TimeoutExpired:
            return False, "Environment creation timed out"
        except Exception as e:
            self.logger.error(f"Error creating Conda environment: {str(e)}")
            return False, f"Error creating environment: {str(e)}"

    def delete_environment(self, env_path):
        """Delete a Conda environment."""
        try:
            if os.path.exists(env_path):
                result = subprocess.run([self.conda_path, 'env', 'remove', '-p', env_path, '-y'],
                                        capture_output=True, text=True, timeout=60)
                if result.returncode == 0:
                    self.logger.info(f"Conda environment deleted: {env_path}")
                    return True
                else:
                    self.logger.error(f"Failed to delete Conda environment: {result.stderr}")
            return True  # Consider it successful if path doesn't exist
        except Exception as e:
            self.logger.error(f"Error deleting Conda environment: {str(e)}")
            return False

    def get_available_templates(self):
        """Get available environment templates."""
        templates = []
        templates_dir = current_app.config.get('ENV_TEMPLATES_PATH')

        if templates_dir and os.path.exists(templates_dir):
            for file in os.listdir(templates_dir):
                if file.endswith('.yml') or file.endswith('.yaml'):
                    template_name = file.replace('.yml', '').replace('.yaml', '')
                    templates.append(template_name)

        return sorted(templates)

    def get_python_environments(self):
        """Get all Python environments (Conda + system)."""
        environments = []

        # Get Conda environments
        try:
            conda_envs = self.list_environments()
            for env_path in conda_envs.get('envs', []):
                try:
                    # Get Python version
                    python_path = os.path.join(env_path, 'bin', 'python')
                    if os.path.exists(python_path):
                        result = subprocess.run([python_path, '--version'],
                                                capture_output=True, text=True, timeout=10)
                        version = result.stdout.strip() if result.returncode == 0 else 'Unknown'

                        environments.append({
                            'name': os.path.basename(env_path),
                            'type': 'conda',
                            'path': env_path,
                            'version': version
                        })
                except Exception as e:
                    self.logger.warning(f"Error getting info for environment {env_path}: {str(e)}")
        except Exception as e:
            self.logger.error(f"Error getting Conda environments: {str(e)}")

        # Get system Python
        try:
            result = subprocess.run(['python3', '--version'],
                                    capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                version = result.stdout.strip()
                python_path = subprocess.run(['which', 'python3'],
                                             capture_output=True, text=True, timeout=10)
                path = python_path.stdout.strip() if python_path.returncode == 0 else 'python3'

                environments.append({
                    'name': 'system',
                    'type': 'system',
                    'path': path,
                    'version': version
                })
        except Exception as e:
            self.logger.warning(f"Error getting system Python info: {str(e)}")

        return environments
