import subprocess
import os
import logging
import yaml
from flask import current_app

logger = logging.getLogger(__name__)


class CondaService:
    """Service for managing Conda environments."""

    def __init__(self):
        self._conda_path = None
        self._available = None

    @property
    def conda_path(self):
        if self._conda_path is None:
            # Try to get from config first
            self._conda_path = current_app.config.get('CONDA_PATH', 'conda')

            # If not found, try common locations
            if not self.is_conda_available():
                common_paths = [
                    '/opt/miniconda3/bin/conda',
                    '/opt/anaconda3/bin/conda',
                    '/usr/local/bin/conda',
                    '/home/conda/miniconda3/bin/conda'
                ]

                for path in common_paths:
                    if os.path.exists(path):
                        self._conda_path = path
                        break

        return self._conda_path

    def is_conda_available(self):
        """Check if Conda is available on the system."""
        if self._available is None:
            try:
                result = subprocess.run([self.conda_path, '--version'],
                                        capture_output=True, text=True, timeout=10)
                self._available = result.returncode == 0
            except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
                self._available = False

        return self._available

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

    def get_available_templates(self):
        """Get available environment templates."""
        templates = {}

        try:
            templates_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'env_templates')

            if os.path.exists(templates_dir):
                for filename in os.listdir(templates_dir):
                    if filename.endswith('.yml') or filename.endswith('.yaml'):
                        template_name = filename.replace('.yml', '').replace('.yaml', '')
                        template_path = os.path.join(templates_dir, filename)

                        try:
                            with open(template_path, 'r') as f:
                                template_data = yaml.safe_load(f)
                                templates[template_name] = {
                                    'name': template_name.replace('-', ' ').title(),
                                    'description': template_data.get('description', f'{template_name} environment'),
                                    'dependencies': template_data.get('dependencies', [])
                                }
                        except Exception as e:
                            logger.warning(f"Error reading template {filename}: {str(e)}")

            # Add default templates if none found
            if not templates:
                templates = {
                    'data-science': {
                        'name': 'Data Science',
                        'description': 'Python environment with pandas, numpy, matplotlib, jupyter',
                        'dependencies': ['python=3.9', 'pandas', 'numpy', 'matplotlib', 'jupyter']
                    },
                    'machine-learning': {
                        'name': 'Machine Learning',
                        'description': 'Python environment with scikit-learn, tensorflow, pytorch',
                        'dependencies': ['python=3.9', 'scikit-learn', 'tensorflow', 'pytorch']
                    }
                }

        except Exception as e:
            logger.error(f"Error getting available templates: {str(e)}")
            templates = {}

        return templates

    def create_environment(self, env_path, template_name):
        """Create a new Conda environment."""
        if not self.is_conda_available():
            return False, "Conda is not available"

        try:
            # Get template
            templates = self.get_available_templates()
            if template_name not in templates:
                return False, f"Template {template_name} not found"

            template = templates[template_name]
            dependencies = template.get('dependencies', [])

            # Create environment
            cmd = [self.conda_path, 'create', '-p', env_path, '-y'] + dependencies

            logger.info(f"Creating conda environment: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            if result.returncode == 0:
                logger.info(f"Successfully created conda environment at {env_path}")
                return True, "Environment created successfully"
            else:
                logger.error(f"Failed to create conda environment: {result.stderr}")
                return False, f"Failed to create environment: {result.stderr}"

        except subprocess.TimeoutExpired:
            return False, "Environment creation timed out"
        except Exception as e:
            logger.error(f"Error creating conda environment: {str(e)}")
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

    def get_python_environments(self):
        """Get list of available Python environments."""
        environments = []

        if not self.is_conda_available():
            return environments

        try:
            result = subprocess.run([self.conda_path, 'env', 'list', '--json'],
                                    capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                import json
                env_data = json.loads(result.stdout)

                for env_path in env_data.get('envs', []):
                    env_name = os.path.basename(env_path)
                    environments.append({
                        'name': env_name,
                        'path': env_path,
                        'type': 'conda'
                    })

        except Exception as e:
            logger.error(f"Error getting Python environments: {str(e)}")

        return environments
